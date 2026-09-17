"""v1.1 attribution suggestions — §9.2 (E14 Who&When, E15 SOTA calibration).

For every persisted alarm, produce a *suggestion* of the responsible agent and
the critical step, using a transparent heuristic ladder over the stored event
trace. Design constraints straight from the paper:

  - the suggestion is ALWAYS human-confirmed (autonomous closure is forbidden);
    the field SOTA (TraceElephant, arXiv:2604.22708) sits at 65.9% step accuracy,
    so a heuristic without operator confirmation would be over-claiming;
  - every suggestion records its method and evidence note so the operator can
    audit *why* the hint was produced;
  - confirmation outcomes are stored per-alarm and sealed into the evidence
    ledger, giving the §9.2 acceptance metric (>= 70% operator approval).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

METHOD = "swarmax.heuristic.v1 (Who&When-aligned, E14/E15)"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


def suggest_for_alarm(conn: sqlite3.Connection, alarm: sqlite3.Row) -> dict:
    """Compute the attribution suggestion for one alarm row.

    Returns {suggested_agent_id, suggested_step, confidence, method, note}.
    The ladder is deterministic and auditable — no LLM judge, no black box.
    """
    agent_id = alarm["agent_id"]
    signal = alarm["signal"]
    window_start = (_utcnow() - timedelta(hours=24)).isoformat(sep=" ")

    if signal == "loop>=2":
        # the repeated tool triple IS the critical step
        row = conn.execute(
            "SELECT tool_name, arguments_json, ts FROM guard_events"
            " WHERE agent_id=? AND event_type='tool_call'"
            " ORDER BY ts DESC LIMIT 1", (agent_id,)).fetchone()
        if row:
            return {"suggested_agent_id": agent_id,
                    "suggested_step": f"repeated call {row['tool_name']}"
                                      f" (last at {str(row['ts'])[:19]})",
                    "confidence": 0.90, "method": METHOD,
                    "note": "3-identical-call loop breaker fired on this tool"}
        return _fallback(agent_id, "loop breaker fired; no tool trace in window")

    if signal in ("error.new_class_seen", "error.rate>0.20"):
        # first error of the burst = likely critical step (Who&When's "when")
        row = conn.execute(
            "SELECT task_id, error_class, ts, session_id FROM agent_task_events"
            " WHERE agent_id=? AND status='error' AND ts >= ?"
            " ORDER BY ts ASC LIMIT 1", (agent_id, window_start)).fetchone()
        if row:
            note = (f"first error '{row['error_class']}' on task {row['task_id']}")
            partner = conn.execute(
                "SELECT DISTINCT agent_id FROM agent_task_events"
                " WHERE session_id=? AND agent_id<>? LIMIT 1",
                (row["session_id"], agent_id)).fetchone()
            if partner:
                note += f"; same-session partner: {partner['agent_id']}"
            return {"suggested_agent_id": agent_id,
                    "suggested_step": f"{row['error_class']} on {row['task_id']}"
                                      f" ({str(row['ts'])[:19]})",
                    "confidence": 0.75, "method": METHOD, "note": note}
        return _fallback(agent_id, "error burst detected; no error rows in window")

    if signal == "permission.deny>0.20":
        # the most-denied tool is the critical step
        row = conn.execute(
            "SELECT tool_name, COUNT(*) c FROM guard_events"
            " WHERE agent_id=? AND event_type='permission_decision'"
            " AND decision='deny' AND ts >= ?"
            " GROUP BY tool_name ORDER BY c DESC LIMIT 1",
            (agent_id, window_start)).fetchone()
        if row:
            return {"suggested_agent_id": agent_id,
                    "suggested_step": f"denied tool '{row['tool_name']}'"
                                      f" ({row['c']}x in 24h)",
                    "confidence": 0.80, "method": METHOD,
                    "note": "highest deny count inside the alarm window"}
        return _fallback(agent_id, "deny storm detected; no deny rows in window")

    if signal == "drift.tool_distribution>0.40":
        # tool with the largest mass in 24h window = the pivot
        row = conn.execute(
            "SELECT tool_name, COUNT(*) c FROM guard_events"
            " WHERE agent_id=? AND event_type='tool_call' AND ts >= ?"
            " GROUP BY tool_name ORDER BY c DESC LIMIT 1",
            (agent_id, window_start)).fetchone()
        if row:
            return {"suggested_agent_id": agent_id,
                    "suggested_step": f"pivot onto '{row['tool_name']}'"
                                      f" ({row['c']}x in 24h)",
                    "confidence": 0.70, "method": METHOD,
                    "note": "JSD drift alarm; dominant 24h tool differs from 7d prior"}
        return _fallback(agent_id, "drift alarm; no tool calls in window")

    if signal == "cost.daily>2x_ewma":
        # most expensive task of the last day is the driver
        row = conn.execute(
            "SELECT task_id, cost_usd, model_name, ts FROM agent_task_events"
            " WHERE agent_id=? AND ts >= ? ORDER BY cost_usd DESC LIMIT 1",
            (agent_id, window_start)).fetchone()
        if row:
            return {"suggested_agent_id": agent_id,
                    "suggested_step": f"task {row['task_id']} on"
                                      f" {row['model_name']} (${row['cost_usd']:.2f})",
                    "confidence": 0.65, "method": METHOD,
                    "note": "largest single-task cost in the alarm day"}
        return _fallback(agent_id, "cost spike; no task rows in window")

    if signal == "escalation.age_max>24":
        # the oldest open ticket is itself the critical step
        row = conn.execute(
            "SELECT agent_id, task_id, created_at FROM hitl_escalations"
            " WHERE status='open' ORDER BY created_at ASC LIMIT 1").fetchone()
        if row:
            age_h = (_utcnow() - _parse(row["created_at"])).total_seconds() / 3600
            return {"suggested_agent_id": row["agent_id"],
                    "suggested_step": f"open ticket {row['task_id']}"
                                      f" ({age_h:.0f}h, opened {str(row['created_at'])[:19]})",
                    "confidence": 0.60, "method": METHOD,
                    "note": "oldest open escalation in the fleet"}
        return _fallback(agent_id, "aging alarm; no open ticket found")

    return _fallback(agent_id, f"signal {signal} has no dedicated ladder rung")


def _fallback(agent_id: str, note: str) -> dict:
    return {"suggested_agent_id": agent_id, "suggested_step": "insufficient trace",
            "confidence": 0.30, "method": METHOD, "note": note}


def confirm_attribution(conn: sqlite3.Connection, alarm_id: str,
                        accepted: bool, operator: str) -> bool:
    """Operator verdict on a suggestion (§9.2 human-confirm gate). Returns True
    if a pending suggestion was updated; the verdict is sealed into the ledger."""
    from .evidence import append_evidence
    cur = conn.execute(
        "UPDATE attribution_suggestions"
        " SET confirmed=?, confirmed_by=?, confirmed_at=?"
        " WHERE alarm_id=? AND confirmed IS NULL",
        (1 if accepted else 0, operator,
         _utcnow().isoformat(sep=" "), alarm_id))
    if cur.rowcount == 0:
        return False
    append_evidence(conn, "attribution_confirmed", {
        "alarm_id": alarm_id, "accepted": accepted, "operator": operator,
        "ts": _utcnow().isoformat(sep=" ")})
    conn.commit()
    return True


def approval_rate(conn: sqlite3.Connection) -> dict:
    """§9.2 acceptance metric: operator-approval ratio over decided suggestions."""
    row = conn.execute(
        "SELECT COUNT(*) total,"
        " SUM(confirmed=1) accepted, SUM(confirmed=0) rejected"
        " FROM attribution_suggestions WHERE confirmed IS NOT NULL").fetchone()
    total = row["total"] or 0
    accepted = row["accepted"] or 0
    return {"decided": total, "accepted": accepted, "rejected": row["rejected"] or 0,
            "rate": (accepted / total) if total else None}
