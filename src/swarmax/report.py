"""Weekly fleet report — paper §4.2 weekly path: drift report_items become a
markdown digest; plus escalation/SLA summary, cost ranking and first-seen classes.

Pure stdlib; reads only committed store state so it works on any replica.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _h(hours: float) -> str:
    return f"{hours:.1f}h"


class WeeklyReport:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---------------------------------------------------------------- sections
    def drift_items(self, *, since_days: int = 7) -> list[sqlite3.Row]:
        since = (_utcnow() - timedelta(days=since_days)).isoformat(sep=" ")
        return self.conn.execute(
            "SELECT * FROM alarms WHERE event_type='report_item'"
            " AND created_at >= ? ORDER BY created_at DESC", (since,)).fetchall()

    def sla_summary(self) -> dict:
        rows = self.conn.execute(
            "SELECT severity, COUNT(*) AS n, SUM(status='open') AS open,"
            " SUM(status='open' AND sla_deadline < ?) AS breached"
            " FROM alarms GROUP BY severity", (_utcnow().isoformat(sep=" "),)).fetchall()
        return {r["severity"]: {"count": r["n"], "open": r["open"],
                                "breached": r["breached"]} for r in rows}

    def cost_ranking(self, *, days: int = 7, top: int = 5) -> list[sqlite3.Row]:
        since = (_utcnow() - timedelta(days=days)).isoformat(sep=" ")
        return self.conn.execute(
            "SELECT agent_id, ROUND(SUM(cost_usd), 4) AS cost_usd,"
            " COUNT(*) AS tasks, ROUND(AVG(latency_ms), 0) AS avg_latency_ms"
            " FROM agent_task_events WHERE ts >= ?"
            " GROUP BY agent_id ORDER BY cost_usd DESC LIMIT ?",
            (since, top)).fetchall()

    def first_seen_classes(self, *, days: int = 7) -> list[sqlite3.Row]:
        since = (_utcnow() - timedelta(days=days)).isoformat(sep=" ")
        return self.conn.execute(
            "SELECT DISTINCT error_class, MIN(ts) AS first_ts"
            " FROM agent_task_events"
            " WHERE error_class IS NOT NULL AND ts >= ?"
            " GROUP BY error_class ORDER BY first_ts DESC", (since,)).fetchall()

    def render(self, *, since_days: int = 7) -> str:
        now = _utcnow()
        lines: list[str] = []
        lines.append(f"# Swarmax Weekly Fleet Report — {now:%Y-%m-%d %H:%M} UTC")
        lines.append("")
        lines.append(f"Window: last {since_days} days · store: SQLite (§12.1)")

        # 1. drift report_items (§4.2 weekly path)
        lines.append("")
        lines.append("## 1. Behavioral drift (report_items)")
        drift = self.drift_items(since_days=since_days)
        if not drift:
            lines.append("- no drift report_items in window")
        for d in drift:
            lines.append(
                f"- `{d['signal']}` on **{d['agent_id']}** — severity {d['severity']},"
                f" raised {str(d['created_at'])[:16]} (JSD>0.40 band / metamorphic)"
                + (f", evidence: ledger#{d['evidence_seq']}"
                   if d["evidence_seq"] is not None else ""))

        # 2. escalation SLA summary
        lines.append("")
        lines.append("## 2. Escalations & SLA")
        sla = self.sla_summary()
        if not sla:
            lines.append("- no alarms recorded")
        for sev in ("Emergency", "Critical", "High", "Medium", "Low", "Info"):
            if sev in sla:
                s = sla[sev]
                lines.append(f"- **{sev}**: {s['count']} total, {s['open']} open,"
                             f" {s['breached']} SLA-breached")

        # 2b. evidence anchors per alarm (B4: AI-Act Art. 12(3) traceability —
        # every report line about an alarm is linkable to the hash-chained ledger)
        since = (_utcnow() - timedelta(days=since_days)).isoformat(sep=" ")
        anchors = self.conn.execute(
            "SELECT alarm_id, severity, signal, evidence_seq,"
            " evidence_seq_resolved FROM alarms WHERE created_at >= ?"
            " ORDER BY created_at DESC LIMIT 50", (since,)).fetchall()
        if anchors:
            lines.append("")
            lines.append("### Evidence anchors (raise → resolve)")
            for a in anchors:
                if a["evidence_seq"] is None:
                    continue
                resolve_ref = (f"ledger#{a['evidence_seq_resolved']}"
                               if a["evidence_seq_resolved"] is not None else "—")
                lines.append(f"- `{a['alarm_id']}` ({a['severity']} {a['signal']}):"
                             f" raise ledger#{a['evidence_seq']} →"
                             f" resolve {resolve_ref}")

        # 3. cost ranking
        lines.append("")
        lines.append("## 3. Cost ranking (top 5, 7d)")
        for r in self.cost_ranking():
            lines.append(f"- {r['agent_id']}: ${r['cost_usd']:.2f}"
                         f" ({r['tasks']} tasks, avg {int(r['avg_latency_ms'])} ms)")

        # 4. first-seen error classes
        lines.append("")
        lines.append("## 4. First-seen error classes (7d)")
        rows = self.first_seen_classes()
        if not rows:
            lines.append("- none")
        for r in rows:
            lines.append(f"- `{r['error_class']}` first seen {str(r['first_ts'])[:16]}")

        # 5. evidence integrity
        lines.append("")
        lines.append("## 5. Evidence integrity")
        n_ledger = self.conn.execute(
            "SELECT COUNT(*) AS c FROM evidence_ledger").fetchone()["c"]
        seal = self.conn.execute(
            "SELECT seal_id, root_hash, covers_through_seq FROM evidence_seals"
            " ORDER BY covers_through_seq DESC LIMIT 1").fetchone()
        lines.append(f"- ledger entries: {n_ledger} (append-only, hash-chained)")
        if seal:
            lines.append(f"- latest seal: `{seal['seal_id']}` root {seal['root_hash'][:16]}…"
                         f" covers seq ≤ {seal['covers_through_seq']}")
        else:
            lines.append("- no seal yet (F2 seal_ledger pending)")
        return "\n".join(lines) + "\n"
