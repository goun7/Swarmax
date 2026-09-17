"""D1: durable calibration state (§3.3) — survives restart, console-visible."""
from swarmax.db import connect, init_db_with_migrations
from swarmax.pipeline import Pipeline


def _event(agent_id: str, synthetic: int, event_id: str) -> dict:
    return {
        "event_id": event_id, "agent_id": agent_id, "task_id": f"t-{event_id}",
        "session_id": "s", "model_name": "m", "input_tokens": 1, "output_tokens": 1,
        "cost_usd": 0.01, "latency_ms": 100, "error_class": None, "status": "ok",
        "synthetic": synthetic, "ts": "2026-09-12 10:00:00", "retry_count": 0,
        "ttft_s": 0.1, "task_template": None, "end_state_json": None,
    }


def test_production_agent_window_persisted_open():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    pipe = Pipeline(conn)
    pipe.ingest([_event("prod-agent", 0, "e1")])
    row = conn.execute(
        "SELECT closed, calibration_until FROM agent_calibration"
        " WHERE agent_id='prod-agent'").fetchone()
    assert row is not None and row["closed"] == 0
    # in-memory window must agree with the store
    assert pipe.apd.window_for("prod-agent").closed is False


def test_calibration_survives_pipeline_restart():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    Pipeline(conn).ingest([_event("prod-agent", 0, "e1")])
    # new Pipeline over the same store == process restart
    pipe2 = Pipeline(conn)
    assert pipe2.apd.window_for("prod-agent").closed is False
    assert "prod-agent" in pipe2._known_agents


def test_synthetic_agent_stays_preclosed():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    pipe = Pipeline(conn)
    pipe.ingest([_event("syn-agent", 1, "e1")])
    row = conn.execute(
        "SELECT closed FROM agent_calibration WHERE agent_id='syn-agent'").fetchone()
    assert row["closed"] == 1
    assert pipe.apd.window_for("syn-agent").closed is True


def test_console_renders_calibration_section():
    from swarmax.console import FleetConsole
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    pipe = Pipeline(conn)
    pipe.ingest([_event("prod-agent", 0, "e1"), _event("syn-agent", 1, "e2")])
    page = FleetConsole(conn).render(
        {"csrf_token": "c", "token": "t", "username": "t", "role": "admin"})
    assert "Calibration" in page and "calibrating" in page
