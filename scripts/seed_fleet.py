#!/usr/bin/env python
"""Seed a realistic demo fleet into a SQLite store — the "user's fleet".

  python scripts/seed_fleet.py            # -> data/swarmax.db (default)
  python scripts/seed_fleet.py --reset    # overwrite an existing store
  python scripts/seed_fleet.py --db path/to/store.db

Now-relative dates: baseline days are the 6 days before yesterday and alarm
replays burst one hour ago, so the console's 24h views are alive on open. Four
calm agents plus seven scenario agents (§7 F1 matrix), an S6 aging ticket and
one mid-calibration production agent make every console state inspectable.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swarmax.db import connect, init_db_with_migrations  # noqa: E402
from swarmax.fleet import emitter  # noqa: E402
from swarmax.fleet.emitter import EXPECTED, SCENARIOS  # noqa: E402
from swarmax.pipeline import Pipeline
from swarmax.privacy.store import bind_subject_event, seal_subject_erasure  # noqa: E402

CALM_AGENTS = ("scribe-bot", "research-bot", "support-bot", "ops-bot")
SCENARIO_AGENTS = tuple(f"{name.lower()}-bot" for name in
                        ("S1", "S2", "S3", "S4", "S5", "S7", "S8"))

# now-relative dates: baseline days are the 6 days before yesterday, the alarm
# replays burst within the last ~12h — emitters stamp day+8..20h, so a −21h base
# keeps every timestamp in the past AND inside the 24h console windows
NOW = datetime.now(timezone.utc).replace(tzinfo=None)
BASE = NOW - timedelta(days=7)
SCENARIO_DAY = NOW.replace(minute=0, second=0, microsecond=0) - timedelta(hours=21)


def seed(conn, *, calm: tuple = CALM_AGENTS, scenarios: tuple = SCENARIO_AGENTS) -> None:
    pipe = Pipeline(conn)
    rng = random.Random(2026)

    for agent in calm + scenarios + ("s6-bot",):
        for d in range(6):
            events, guards = emitter.emit_baseline_day(agent, BASE + timedelta(days=d), rng)
            pipe.ingest(events, guards)

    # calm fleet: a burst inside the last 12h keeps 24h views non-zero, then
    # steady-state hourly cycles close calibration (§3.3)
    for agent in calm:
        events, guards = emitter.emit_baseline_day(agent, SCENARIO_DAY, rng)
        pipe.ingest(events, guards)
        for _ in range(30):
            pipe.evaluate_agent(agent, daily_cost=rng.uniform(9.0, 15.0))

    # scenario fleet: replay each alarm class (§7 F1 matrix) on its own agent
    for sname, agent in zip(("S1", "S2", "S3", "S4", "S5", "S7", "S8"), scenarios):
        if sname == "S1":
            for _ in range(30):
                pipe.evaluate_agent(agent, daily_cost=rng.uniform(11.0, 13.0))
            events, guards = SCENARIOS[sname](agent, SCENARIO_DAY, random.Random(1))
            pipe.ingest(events, guards)
            pipe.evaluate_agent(agent, daily_cost=42.0)
        else:
            events, guards = SCENARIOS[sname](agent, SCENARIO_DAY, random.Random(3))
            pipe.ingest(events, guards)
            pipe.evaluate_agent(agent)

    # S6 ticket aging (§4.2, R14): a 30h-open permission ticket, still open
    pipe.open_escalation(
        escalation_id="esc-s6-bot", agent_id="s6-bot", task_id="t-manual",
        reason="permission",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=30))
    pipe.evaluate_agent("s6-bot")

    # one production-style agent (synthetic=0, OTLP-shaped events): its 14-day
    # §3.3 calibration window is OPEN, so the console shows live suppression
    prod = "live-ingest-bot"
    events, guards = emitter.emit_baseline_day(prod, SCENARIO_DAY, rng)
    for e in events:
        e["synthetic"] = 0
    for g in guards:
        g["synthetic"] = 0
    pipe.ingest(events, guards)
    pipe.evaluate_agent(prod)

    # console users (§8 L2): admin for triage, viewer for read-only demo
    from swarmax import auth
    auth.bootstrap_admin(conn, "root", "swarmax-demo-admin")
    auth.add_user(conn, "viewer", "swarmax-demo-viewer", "viewer", actor="root")


def _seed_privacy(conn) -> None:
    """Demo privacy subjects (§10.3): two wrapped-DEK subjects, one bound to
    live traffic, one already erased (shows both states in the console)."""
    from swarmax.privacy.store import SubjectKeyStore, master_key_from_env
    store = SubjectKeyStore(conn, master_key_from_env())
    store.register("cust-1001", "Demo Customer A",
                   {"email": "customer.a@example.com", "plan": "pro"},
                   actor="seed", lawful_basis="contract")
    store.register("cust-1002", "Demo Customer B",
                   {"email": "customer.b@example.com", "plan": "free"},
                   actor="seed", lawful_basis="consent")
    # bind one real task event to cust-1001 so erasure scope is provable
    ev = conn.execute(
        "SELECT event_id FROM agent_task_events WHERE agent_id='s1-bot'"
        " ORDER BY ts LIMIT 1").fetchone()
    if ev:
        bind_subject_event(conn, "cust-1001", ev["event_id"])
    store.crypto_shred("cust-1002", actor="seed (erasure demo)")
    seal_subject_erasure(conn, "cust-1002")
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed the Swarmax demo fleet")
    ap.add_argument("--db", default="data/swarmax.db")
    ap.add_argument("--reset", action="store_true", help="overwrite existing store")
    args = ap.parse_args()

    db_path = Path(args.db)
    if db_path.exists():
        if not args.reset:
            print(f"store exists: {db_path} — use --reset to overwrite")
            return 2
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(str(db_path))
    init_db_with_migrations(conn)
    seed(conn)
    _seed_privacy(conn)
    n_agents = conn.execute("SELECT COUNT(*) FROM fleet_agents").fetchone()[0]
    n_events = conn.execute("SELECT COUNT(*) FROM agent_task_events").fetchone()[0]
    n_alarms = conn.execute("SELECT COUNT(*) FROM alarms WHERE status='open'").fetchone()[0]
    n_subjects = conn.execute("SELECT COUNT(*) FROM data_subjects").fetchone()[0]
    print(f"seeded {db_path}: {n_agents} agents, {n_events} events,"
          f" {n_alarms} open alarms, {n_subjects} privacy subjects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
