"""Weekly report, console data layer, and exit-drill tests."""
import json
import random
from datetime import datetime, timedelta

from swarmax.console import FleetConsole
from swarmax.db import connect, init_db_with_migrations
from swarmax.exit_drill import export_bundle, rebuild_from_bundle, run_exit_drill
from swarmax.fleet import emitter
from swarmax.pipeline import Pipeline
from swarmax.report import WeeklyReport
from swarmax.sealing import load_or_create_seed, seal_ledger

BASE = datetime(2026, 9, 1)
SCENARIO_DAY = datetime(2026, 9, 7)


def make_store() -> Pipeline:
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return Pipeline(conn)


def populated() -> Pipeline:
    pipe = make_store()
    rng = random.Random(42)
    for d in range(6):
        events, guards = emitter.emit_baseline_day("agent-a", BASE + timedelta(days=d), rng)
        pipe.ingest(events, guards)
    events, guards = emitter.emit_s2_tool_drift("agent-a", SCENARIO_DAY, random.Random(3))
    pipe.ingest(events, guards)
    pipe.evaluate_agent("agent-a")
    return pipe


# ---------------------------------------------------------------- report

def test_weekly_report_renders_sections():
    pipe = populated()
    text = WeeklyReport(pipe.conn).render()
    assert "# Swarmax Weekly Fleet Report" in text
    assert "## 1. Behavioral drift" in text
    assert "drift.tool_distribution>0.40" in text
    assert "## 2. Escalations & SLA" in text
    assert "## 5. Evidence integrity" in text


def test_report_sla_summary_counts():
    pipe = populated()
    sla = WeeklyReport(pipe.conn).sla_summary()
    assert "Medium" in sla            # drift report_item landed
    assert sla["Medium"]["count"] >= 1


# ---------------------------------------------------------------- console

def fake_session(role: str = "admin") -> dict:
    """Operator actor for render-level tests (token shape matches _token())."""
    return {"csrf_token": "csrf-test-token", "token": "tok-test-token",
            "username": "test-admin", "role": role}


def test_console_summary_and_page():
    pipe = populated()
    console = FleetConsole(pipe.conn)
    s = console.summary()
    assert s["open_alarms"] >= 1
    assert s["agents"] >= 1
    page = console.render(fake_session())
    assert "Swarmax Fleet Console" in page
    assert "drift.tool_distribution&gt;0.40" in page or "drift.tool_distribution>0.40" in page
    assert "resolve" in page
    assert "evidence:" in page


def test_console_resolve_action():
    pipe = populated()
    console = FleetConsole(pipe.conn)
    alarm_id = console.open_alarms()[0]["alarm_id"]
    console.conn.execute(
        "UPDATE alarms SET status='resolved', resolved_by='test' WHERE alarm_id=?",
        (alarm_id,))
    pipe.conn.commit()
    assert all(a["alarm_id"] != alarm_id for a in console.open_alarms())


# ---------------------------------------------------------------- exit drill

def test_exit_drill_roundtrip_preserves_and_verifies():
    pipe = populated()
    seed = load_or_create_seed()
    seal_ledger(pipe.conn, seed)

    report = run_exit_drill(pipe.conn)
    assert report["ok"], json.dumps(report, indent=2)
    assert report["phases"]["verify"]["chain_ok"]
    assert report["phases"]["verify"]["row_counts_match"]

    # rebuilt store answers the same queries
    bundle = export_bundle(pipe.conn)
    rebuilt = rebuild_from_bundle(bundle)
    assert rebuilt.execute(
        "SELECT COUNT(*) c FROM agent_task_events").fetchone()["c"] == \
        pipe.conn.execute(
            "SELECT COUNT(*) c FROM agent_task_events").fetchone()["c"]


def test_exit_drill_detects_tamper():
    pipe = populated()
    seed = load_or_create_seed()
    seal_ledger(pipe.conn, seed)
    pipe.conn.execute("DROP TRIGGER trg_evidence_ledger_no_update")
    pipe.conn.execute("UPDATE evidence_ledger SET payload_hash='x' WHERE seq=1")
    pipe.conn.commit()
    report = run_exit_drill(pipe.conn)
    assert not report["ok"] and not report["phases"]["verify"]["chain_ok"]
