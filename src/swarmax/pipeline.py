"""Ingest→evaluate pipeline: synthetic fleet → SQLite → §4.2 fact evaluation.

Time-sensitive facts use deterministic Python-side windows anchored at each agent's
latest event (never wall-clock), so synthetic historical days evaluate exactly like
production would. Volume facts are SQL-free by design at F0 scale.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from .evidence import append_evidence
from .metrics.apd import Alarm, FleetApd
from .metrics.classifier import PRESEEN_CLASSES
from .metrics.loop_breaker import LoopBreaker  # noqa: F401  (re-exported for harnesses)
from .privacy.store import bind_subject_event, seal_subject_erasure  # noqa: F401


def _utcnow() -> datetime:
    """Naive UTC now (matches stored naive timestamps) without utcnow() deprecation."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_ts(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


class Pipeline:
    def __init__(self, conn: sqlite3.Connection, apd: FleetApd | None = None) -> None:
        self.conn = conn
        self.apd = apd or FleetApd()
        self._known_agents: set[str] = set()
        self._persisted: set[tuple[str, str, str]] = set()
        # D1: restore durable calibration windows (§3.3) from migration 004 state
        for row in self.conn.execute(
                "SELECT agent_id, closed FROM agent_calibration").fetchall():
            window = self.apd.window_for(row["agent_id"], synthetic=False)
            window.closed = bool(row["closed"])
            self._known_agents.add(row["agent_id"])
        # per-agent fact hits recorded at ingest time (sequence metrics)
        self.loop_hits: dict[str, set[str]] = {}       # agent_id -> {task_id}
        self.new_class_hits: set[str] = set()          # agent_ids with a first-seen class

    # ---------------------------------------------------------------- ingest
    def _register_agent(self, agent_id: str, *, synthetic: bool) -> None:
        """First sight of an agent from ANY event stream (task or guard).
        Synthetic fleets are pre-closed (§3.3, R10/§7.3); production agents open
        the real 14-day window, persisted so it survives restarts (D1)."""
        if agent_id in self._known_agents:
            return
        self.conn.execute(
            "INSERT OR IGNORE INTO fleet_agents (agent_id, fleet_name, role)"
            " VALUES (?, 'synthetic-fleet', 'worker')", (agent_id,))
        self._known_agents.add(agent_id)
        closed = 1 if synthetic else 0
        self.conn.execute(
            "INSERT OR IGNORE INTO agent_calibration"
            " (agent_id, calibration_until, closed) VALUES (?, ?, ?)",
            (agent_id,
             (_utcnow() + timedelta(days=14)).isoformat(sep=" "), closed))
        # keep the in-memory window in lockstep with the persisted row
        self.apd.window_for(agent_id, synthetic=False).closed = bool(closed)
        # production agents have seen the mechanical classes before; only
        # genuinely novel signatures may trip the sentinel (§3.1)
        self.apd.classifier_for(agent_id).seen |= PRESEEN_CLASSES

    def ingest(self, events: list[dict], guards: list[dict] | None = None) -> None:
        guards = guards or []
        for e in events:
            self._register_agent(e["agent_id"], synthetic=bool(e.get("synthetic")))
        for g in guards:
            self._register_agent(g["agent_id"], synthetic=bool(g.get("synthetic")))

        # idempotent ingest (§4.3 spirit): retransmitted spans/events dedupe on PK
        self.conn.executemany(
            "INSERT OR IGNORE INTO agent_task_events (event_id, agent_id, task_id,"
            " session_id, model_name, input_tokens, output_tokens, cost_usd, latency_ms,"
            " error_class, status, synthetic, ts, retry_count, ttft_s,"
            " task_template, end_state_json) VALUES"
            " (:event_id, :agent_id, :task_id, :session_id, :model_name,"
            " :input_tokens, :output_tokens, :cost_usd, :latency_ms,"
            " :error_class, :status, :synthetic, :ts, :retry_count, :ttft_s,"
            " :task_template, :end_state_json)",
            events)
        # B2 (§10.3): optional data-subject binding — spans may carry a privacy
        # subject id; the event link is anchored in the evidence ledger so
        # Art. 17 erasure scope is provable (per-subject crypto-shred).
        for e in events:
            ds = e.get("data_subject_id")
            if ds:
                bind_subject_event(self.conn, str(ds), e["event_id"])
                e.pop("data_subject_id", None)
        self.conn.executemany(
            "INSERT OR IGNORE INTO guard_events (event_id, agent_id, task_id,"
            " event_type, decision, tool_name, arguments_json, synthetic, ts) VALUES"
            " (:event_id, :agent_id, :task_id, :event_type, :decision,"
            " :tool_name, :arguments_json, :synthetic, :ts)",
            guards)

        # sequence metrics
        for g in guards:
            if g["event_type"] == "tool_call":
                if self.apd.fact_loop(g["task_id"], g["tool_name"], g["arguments_json"]):
                    self.loop_hits.setdefault(g["agent_id"], set()).add(g["task_id"])
        for e in events:
            if e.get("error_class"):
                loop_detected = e.get("status") == "quarantined"
                _, is_new = self.apd.fact_error_class(
                    e["agent_id"], e["error_class"], loop_detected=loop_detected)
                if is_new:
                    self.new_class_hits.add(e["agent_id"])
            if e.get("task_template") and e.get("end_state_json"):
                self.apd.fact_output_quality(
                    e["task_template"], _parse_json(e["end_state_json"]))
        self.conn.commit()

    def open_escalation(self, *, escalation_id: str, agent_id: str, task_id: str,
                        reason: str, created_at: datetime) -> None:
        """Directly inject an open HITL ticket (S6 ticket-aging scenario)."""
        self.conn.execute(
            "INSERT INTO hitl_escalations (escalation_id, agent_id, task_id,"
            " trigger_metric, trigger_value, reason, evidence_ref, sla_deadline,"
            " status, created_at) VALUES (?, ?, ?, 'manual', 0.0, ?, 'harness',"
            " ?, 'open', ?)",
            (escalation_id, agent_id, task_id, reason,
             (created_at + timedelta(hours=4)).isoformat(sep=" "),
             created_at.isoformat(sep=" ")))
        self.conn.commit()

    # ---------------------------------------------------------------- facts
    def _latest_ts(self, table: str, agent_id: str) -> datetime | None:
        if table == "guard_events_permission":
            sql = ("SELECT MAX(ts) AS m FROM guard_events"
                   " WHERE agent_id=? AND event_type='permission_decision'")
        else:
            sql = f"SELECT MAX(ts) AS m FROM {table} WHERE agent_id=?"
        row = self.conn.execute(sql, (agent_id,)).fetchone()
        return _parse_ts(row["m"]) if row and row["m"] else None

    def fact_error_rate(self, agent_id: str, *, window_s: int = 24) -> bool:
        """§4.2 error.rate > 20% inside the latest 24s activity window."""
        latest = self._latest_ts("agent_task_events", agent_id)
        if latest is None:
            return False
        rows = self.conn.execute(
            "SELECT status, ts FROM agent_task_events"
            " WHERE agent_id=? AND status IN ('error','ok')", (agent_id,)).fetchall()
        window = [r for r in rows
                  if latest - _parse_ts(r["ts"]) <= timedelta(seconds=window_s)]
        if not window:
            return False
        rate = sum(1 for r in window if r["status"] == "error") / len(window)
        return rate > 0.20

    def fact_deny_ratio(self, agent_id: str, *, window_s: int = 1) -> bool:
        """§4.2 permission.deny > 20% inside the latest 1s decision window.
        Anchored at the latest permission_decision (not the latest guard event)."""
        latest = self._latest_ts("guard_events_permission", agent_id)
        if latest is None:
            return False
        rows = self.conn.execute(
            "SELECT decision, ts FROM guard_events"
            " WHERE agent_id=? AND event_type='permission_decision'",
            (agent_id,)).fetchall()
        window = [r for r in rows
                  if latest - _parse_ts(r["ts"]) <= timedelta(seconds=window_s)]
        if not window:
            return False
        rate = sum(1 for r in window if r["decision"] == "deny") / len(window)
        return rate > 0.20

    def fact_retry(self, agent_id: str) -> bool:
        """§4.2 latency.retry_count >= 3 within the same task."""
        row = self.conn.execute(
            "SELECT MAX(retry_count) AS m FROM agent_task_events WHERE agent_id=?",
            (agent_id,)).fetchone()
        return bool(row["m"] and row["m"] >= 3)

    def fact_ticket_aging(self, *, limit_h: float = 24.0) -> bool:
        """§4.2 escalation.age_max > 24h → self-escalation (R14 tracks open time)."""
        rows = self.conn.execute(
            "SELECT created_at FROM hitl_escalations WHERE status='open'").fetchall()
        now = _utcnow()
        return any(
            (now - _parse_ts(r["created_at"])) > timedelta(hours=limit_h)
            for r in rows if r["created_at"])

    def fact_tool_drift(self, agent_id: str) -> bool:
        """§3.2-2 JSD(P7d ∥ Q24h) > 0.40 — P = prior 7d reference, Q = latest 24h."""
        latest = self._latest_ts("guard_events", agent_id)
        if latest is None:
            return False
        q_from = latest - timedelta(hours=24)
        p_from = q_from - timedelta(hours=24 * 7)
        p = self._tool_counts(agent_id, p_from, q_from)
        q = self._tool_counts(agent_id, q_from, latest)
        return self.apd.fact_tool_drift(p, q)

    def _tool_counts(self, agent_id: str, start: datetime, end: datetime) -> dict[str, float]:
        rows = self.conn.execute(
            "SELECT tool_name, ts FROM guard_events"
            " WHERE agent_id=? AND event_type='tool_call'", (agent_id,)).fetchall()
        counts: dict[str, float] = {}
        for r in rows:
            ts = _parse_ts(r["ts"])
            if start < ts <= end:
                counts[r["tool_name"]] = counts.get(r["tool_name"], 0.0) + 1.0
        return counts

    # ---------------------------------------------------------------- alarms (F1)
    def _persist_alarm(self, alarm: Alarm, agent_id: str) -> None:
        """Persist one alarm to the SLA queue + seal it into the evidence ledger
        (§4.1 escalation path; §12.1 append-only chain). Idempotent per signal burst.
        """
        now = _utcnow()
        key = (agent_id, alarm.signal, now.strftime("%Y%m%d%H"))
        if key in self._persisted:
            return
        self._persisted.add(key)
        alarm_id = f"alm_{abs(hash(key)) % 10**16:016x}"
        seq = append_evidence(self.conn, f"{alarm.event_type}_created", {
            "alarm_id": alarm_id, "agent_id": agent_id, "signal": alarm.signal,
            "severity": alarm.severity, "sla_hours": alarm.sla_hours,
            "protection": alarm.protection, "ts": now.isoformat(sep=" "),
        })
        self.conn.execute(
            "INSERT INTO alarms (alarm_id, agent_id, task_id, signal, event_type, reason,"
            " severity, sla_hours, sla_deadline, trigger_value, protection, status,"
            " created_at, evidence_seq)"
            " VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, NULL, ?, 'open', ?, ?)",
            (alarm_id, agent_id, alarm.signal, alarm.event_type, alarm.reason,
             alarm.severity, alarm.sla_hours,
             (now + timedelta(hours=alarm.sla_hours)).isoformat(sep=" "),
             alarm.protection, now.isoformat(sep=" "), seq))
        # v1.1 (§9.2): every alarm is born with an auditable attribution
        # suggestion — the operator confirms or rejects it (never autonomous).
        self._attach_attribution(alarm_id, agent_id, alarm.signal)

    def _attach_attribution(self, alarm_id: str, agent_id: str, signal: str) -> None:
        from . import attribution
        try:
            row = self.conn.execute(
                "SELECT * FROM alarms WHERE alarm_id=?", (alarm_id,)).fetchone()
            sug = attribution.suggest_for_alarm(self.conn, row)
            self.conn.execute(
                "INSERT OR IGNORE INTO attribution_suggestions"
                " (alarm_id, suggested_agent_id, suggested_step, confidence,"
                "  method, note) VALUES (?, ?, ?, ?, ?, ?)",
                (alarm_id, sug["suggested_agent_id"], sug["suggested_step"],
                 sug["confidence"], sug["method"], sug["note"]))
        except Exception as exc:  # advisory layer: never block the alarm path
            # (visible, not silent — suggestions can be regenerated from the trace)
            print(f"swarmax: attribution suggestion failed for {alarm_id}: {exc}",
                  file=sys.stderr)

    def resolve_alarm(self, alarm_id: str, resolved_by: str) -> int:
        """Resolve an open alarm, anchoring the resolution in the evidence
        ledger (B4: alarms.evidence_seq_resolved). Returns the number of rows
        affected so callers can distinguish a real triage from an unknown/stale
        alarm id; unknown/stale ids write NO evidence (fail-closed, D2)."""
        cur = self.conn.execute(
            "UPDATE alarms SET status='resolved', resolved_by=?, resolved_at=?"
            " WHERE alarm_id=? AND status='open'",
            (resolved_by, _utcnow().isoformat(sep=" "), alarm_id))
        if cur.rowcount == 0:
            self.conn.commit()
            return 0
        seq = append_evidence(self.conn, "alarm_resolved", {
            "alarm_id": alarm_id, "resolved_by": resolved_by,
            "ts": _utcnow().isoformat(sep=" ")})
        self.conn.execute(
            "UPDATE alarms SET evidence_seq_resolved=? WHERE alarm_id=?",
            (seq, alarm_id))
        self.conn.commit()
        return cur.rowcount

    def open_alarms(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM alarms WHERE status='open' ORDER BY sla_deadline").fetchall()

    def record_baseline_audit(self, note: str, payload: dict) -> None:
        """§3.3 baseline_audit ledger (threshold changes, oracle budget overruns)."""
        append_evidence(self.conn, "baseline_audit", {"note": note, **payload})

    # ---------------------------------------------------------------- evaluate
    def evaluate_agent(self, agent_id: str, *,
                       daily_cost: float | None = None) -> list[Alarm]:
        """Evaluate every §4.2 fact for one agent, map onto the SLA table and
        persist non-suppressed alarms to the SLA queue + evidence ledger."""
        facts: dict[str, bool] = {
            "error.rate>0.20": self.fact_error_rate(agent_id),
            "permission.deny>0.20": self.fact_deny_ratio(agent_id),
            "latency.retry>=3": self.fact_retry(agent_id),
            "escalation.age_max>24": self.fact_ticket_aging(),
            "drift.tool_distribution>0.40": self.fact_tool_drift(agent_id),
            "loop>=2": bool(self.loop_hits.get(agent_id)),
            "error.new_class_seen": agent_id in self.new_class_hits,
        }
        if daily_cost is not None:
            calibrated = self.apd.window_for(agent_id, synthetic=True).closed
            facts["cost.daily>2x_ewma"] = self.apd.fact_cost_spike(
                agent_id, daily_cost, calibrated=calibrated)
        alarms = self.apd.evaluate(facts, agent_id)
        for alarm in alarms:
            if not alarm.suppressed and alarm.event_type in ("escalation", "report_item"):
                self._persist_alarm(alarm, agent_id)
        self.conn.commit()
        return alarms

    def calibration_state(self) -> list[sqlite3.Row]:
        """D1: per-agent calibration rows for the console (§3.3 visible)."""
        return self.conn.execute(
            "SELECT agent_id, calibration_until, closed FROM agent_calibration"
            " ORDER BY agent_id").fetchall()


def _parse_json(value: object) -> dict:
    import json
    return json.loads(value) if isinstance(value, str) else dict(value)  # type: ignore[arg-type]
