"""v1.1 attribution suggestions (§9.2): ladder, confirmation gate, approval rate."""
import pytest

from swarmax import attribution
from swarmax.db import connect, init_db_with_migrations
from swarmax.pipeline import Pipeline


@pytest.fixture()
def env():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    pipe = Pipeline(conn)
    # drive a loop alarm (S3 shape) and a deny alarm (S5 shape) through the APD
    # by reusing the scenario harness pieces directly
    from datetime import datetime, timedelta, timezone
    base = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    for i in range(3):  # identical calls → loop breaker
        pipe.ingest([], [{
            "event_id": f"g{i}", "agent_id": "a-loop", "task_id": "t1",
            "event_type": "tool_call", "decision": "allow",
            "tool_name": "search_flights", "arguments_json": '{"q": "x"}',
            "synthetic": 1,
            "ts": (base + timedelta(seconds=10 * i)).isoformat(sep=" ")}])
    pipe.evaluate_agent("a-loop")
    # deny storm: §4.2 window is the latest 1s of decisions → 50% deny inside it
    for i in range(10):
        pipe.ingest([], [{
            "event_id": f"d{i}", "agent_id": "a-deny", "task_id": f"t{i}",
            "event_type": "permission_decision", "decision": "deny" if i < 5 else "allow",
            "tool_name": "payments.refund" if i < 5 else "inbox.read",
            "arguments_json": "{}", "synthetic": 1,
            "ts": (base + timedelta(seconds=i * 0.08)).isoformat(sep=" ")}])
    pipe.evaluate_agent("a-deny")
    return conn, pipe


def _open(conn, agent_id):
    return conn.execute(
        "SELECT * FROM alarms WHERE agent_id=? AND status='open'",
        (agent_id,)).fetchone()


def test_every_alarm_gets_a_suggestion(env):
    conn, pipe = env
    for a in conn.execute("SELECT * FROM alarms WHERE status='open'").fetchall():
        sug = conn.execute(
            "SELECT * FROM attribution_suggestions WHERE alarm_id=?",
            (a["alarm_id"],)).fetchone()
        assert sug is not None
        assert 0.0 <= sug["confidence"] <= 1.0
        assert sug["method"].startswith("swarmax.heuristic.v1")


def test_loop_ladder_names_the_repeated_tool(env):
    conn, _ = env
    alarm = _open(conn, "a-loop")
    sug = conn.execute(
        "SELECT * FROM attribution_suggestions WHERE alarm_id=?",
        (alarm["alarm_id"],)).fetchone()
    assert "search_flights" in sug["suggested_step"]
    assert sug["confidence"] >= 0.85


def test_deny_ladder_names_the_denied_tool(env):
    conn, _ = env
    alarm = _open(conn, "a-deny")
    sug = conn.execute(
        "SELECT * FROM attribution_suggestions WHERE alarm_id=?",
        (alarm["alarm_id"],)).fetchone()
    assert "payments.refund" in sug["suggested_step"]


def test_human_confirm_gate_and_ledger(env):
    conn, _ = env
    alarm = _open(conn, "a-loop")
    assert attribution.confirm_attribution(conn, alarm["alarm_id"], True, "op1")
    row = conn.execute(
        "SELECT confirmed, confirmed_by FROM attribution_suggestions"
        " WHERE alarm_id=?", (alarm["alarm_id"],)).fetchone()
    assert row["confirmed"] == 1 and row["confirmed_by"] == "op1"
    # verdict is sealed into the append-only ledger
    assert conn.execute(
        "SELECT 1 FROM evidence_ledger WHERE event_type='attribution_confirmed'"
    ).fetchone()
    # second verdict on the same alarm is refused (already decided)
    assert not attribution.confirm_attribution(conn, alarm["alarm_id"], False, "op2")


def test_approval_rate_matches_gate(env):
    conn, _ = env
    rows = conn.execute(
        "SELECT alarm_id FROM attribution_suggestions WHERE confirmed IS NULL"
    ).fetchall()
    for i, r in enumerate(rows):
        attribution.confirm_attribution(conn, r["alarm_id"], i % 2 == 0, "op")
    stats = attribution.approval_rate(conn)
    assert stats["decided"] == len(rows) and stats["accepted"] == (len(rows) + 1) // 2
    assert 0 <= stats["rate"] <= 1
