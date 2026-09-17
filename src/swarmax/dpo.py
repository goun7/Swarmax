"""DPO daily privacy report (§10.3 + AI_ACT_COMPLIANCE.md Md. 17 evidence).

Pure stdlib; reads only committed state so it runs on any replica. Answers the
three questions a data-protection officer asks every morning:

  1. Which data subjects exist, in which key state, since when?
  2. Were any erasure requests breached (registered → erased outside SLA)?
  3. Is the erasure record itself tamper-evident (ledger anchors present)?
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

ERASE_SLA_DAYS = 30  # Art. 17(1): response "without undue delay"; internal SLA


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DpoReport:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def subjects(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT subject_id, display_name, key_version, registered_at,"
            " erased_at FROM data_subjects ORDER BY registered_at").fetchall()

    def erasure_sla_breaches(self) -> list[dict]:
        """Subjects erased later than the internal 30-day SLA (None = OK)."""
        breaches = []
        for r in self.conn.execute(
                "SELECT subject_id, registered_at, erased_at FROM data_subjects"
                " WHERE erased_at IS NOT NULL").fetchall():
            try:
                reg = datetime.strptime(str(r["registered_at"])[:19],
                                        "%Y-%m-%d %H:%M:%S")
                era = datetime.strptime(str(r["erased_at"])[:19],
                                        "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            days = (era - reg).total_seconds() / 86400
            if days > ERASE_SLA_DAYS:
                breaches.append({"subject_id": r["subject_id"], "days": round(days, 1)})
        return breaches

    def ledger_anchors(self) -> dict:
        q = lambda t: self.conn.execute(  # noqa: E731
            "SELECT COUNT(*) c FROM evidence_ledger WHERE event_type=?", (t,)
        ).fetchone()["c"]
        return {"subject_event_bound": q("subject_event_bound"),
                "subject_erased": q("subject_erased")}

    def pending_erase_requests(self) -> int:
        """Subjects still alive = potential open erasure obligations."""
        return self.conn.execute(
            "SELECT COUNT(*) c FROM data_subjects WHERE erased_at IS NULL"
        ).fetchone()["c"]

    def render(self, *, since_days: int = 1) -> str:
        now = _utcnow()
        lines = [f"# Swarmax DPO Privacy Report — {now:%Y-%m-%d %H:%M} UTC", ""]
        subs = self.subjects()
        lines.append(f"## Subjects ({len(subs)})")
        for s in subs:
            state = (f"ERASED (crypto-shred) at {str(s['erased_at'])[:16]}"
                     if s["erased_at"] else
                     f"active (wrapped DEK v{s['key_version']}, registered"
                     f" {str(s['registered_at'])[:16]})")
            lines.append(f"- `{s['subject_id']}` ({s['display_name']}): {state}")
        lines.append("")
        lines.append("## Erasure SLA (internal 30d)")
        breaches = self.erasure_sla_breaches()
        lines.append(f"- breaches: {len(breaches)}"
                     + ("".join(f"\n  - `{b['subject_id']}`: {b['days']} days"
                                for b in breaches)))
        lines.append(f"- subjects with live keys (erasure obligation pool):"
                     f" {self.pending_erase_requests()}")
        lines.append("")
        anchors = self.ledger_anchors()
        lines.append("## Tamper-evidence of the erase path")
        lines.append(f"- `subject_event_bound` anchors: {anchors['subject_event_bound']}")
        lines.append(f"- `subject_erased` anchors: {anchors['subject_erased']}")
        n = self.conn.execute("SELECT COUNT(*) c FROM evidence_ledger").fetchone()["c"]
        lines.append(f"- ledger entries: {n} (append-only, hash-chained;"
                     f" cold-archive via `make cold-archive`)")
        return "\n".join(lines) + "\n"
