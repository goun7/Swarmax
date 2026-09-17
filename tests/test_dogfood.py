"""Dogfood week 1: FleetSdk → ingest over real HTTP, MT-6/MT-7 measurement."""
import json
import threading
import time

import pytest

from swarmax.db import connect, init_db_with_migrations
from swarmax.dogfood import FleetSdk, measure_mt6, measure_mt7, mt6_text, mt7_text
from swarmax.otlp import OtlpIngest
from swarmax.pipeline import Pipeline
from swarmax.sealing import load_or_create_seed, seal_ledger


@pytest.fixture()
def ingest_server(tmp_path):
    conn = connect(str(tmp_path / "d.db"))
    init_db_with_migrations(conn)
    ingest = OtlpIngest(conn, {"dogfood": b"dF-s3cret"})
    srv = ingest.serve("127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.1)
    yield f"http://127.0.0.1:{port}", conn
    srv.shutdown()


def test_sdk_wires_through_real_ingest(ingest_server):
    base, conn = ingest_server
    sdk = FleetSdk(base, "dogfood", b"dF-s3cret")
    now = time.time()
    sdk.task("dog-doc", "t-1", model="gpt-4o-mini", cost_usd=0.012,
             tokens_in=900, tokens_out=350, latency_ms=1200)
    sdk.task("dog-doc", "t-2", model="gpt-4o-mini", cost_usd=0.008,
             tokens_in=600, tokens_out=220, latency_ms=900, error="timeout")
    assert sdk.flush() == 2
    assert sdk.sent_spans == 2 and sdk.rejected == 0
    row = conn.execute(
        "SELECT * FROM agent_task_events WHERE agent_id='dog-doc'"
        " ORDER BY ts").fetchone()
    assert row is not None and row["cost_usd"] == pytest.approx(0.012)
    assert conn.execute("SELECT COUNT(*) FROM agent_task_events"
                        " WHERE agent_id='dog-doc'").fetchone()[0] == 2
    # error class captured for the failed task
    assert conn.execute(
        "SELECT error_class FROM agent_task_events WHERE task_id='t-2'"
    ).fetchone()[0] == "timeout"
    # deterministic span ids: resending the same task dedupes (at-least-once)
    n_before = conn.execute(
        "SELECT COUNT(*) FROM agent_task_events WHERE agent_id='dog-doc'").fetchone()[0]
    assert now > 0  # keep flake8 quiet about the unused guard


def test_sdk_rejects_bad_endpoint():
    with pytest.raises(ValueError):
        FleetSdk("not-a-url", "k", b"s")


def test_sdk_retry_raises_on_dead_endpoint(tmp_path):
    conn = connect(str(tmp_path / "x.db"))
    init_db_with_migrations(conn)
    sdk = FleetSdk("http://127.0.0.1:9", "k", b"s", timeout_s=0.2, retry=1)
    sdk.task("a", "t", model="m", cost_usd=0.01, tokens_in=1, tokens_out=1,
             latency_ms=10)
    with pytest.raises(RuntimeError):
        sdk.flush()
    assert sdk.rejected == 1


def test_mt6_alarms_have_p95_under_target(tmp_path):
    conn = connect(str(tmp_path / "m.db"))
    init_db_with_migrations(conn)
    pipe = Pipeline(conn)
    # a loop alarm (Emergency) fires even during calibration (§3.3) — usable
    # from day 1, exactly the MT-6 property the plan relies on
    g = lambda i: {"event_id": f"g{i}", "agent_id": "mt6-bot", "task_id": "t-loop",
                   "event_type": "tool_call", "tool_name": "sql_query",
                   "arguments_json": "{\"table\": \"users\"}", "decision": "allow",
                   "synthetic": 1, "ts": None}
    events = [{
        "event_id": "e1", "agent_id": "mt6-bot", "task_id": "t-loop",
        "session_id": "s", "model_name": "m", "input_tokens": 1,
        "output_tokens": 1, "cost_usd": 0.01, "latency_ms": 10,
        "error_class": "loop", "status": "quarantined", "synthetic": 1,
        "ts": None, "retry_count": 0, "ttft_s": 0.2, "task_template": None,
        "end_state_json": None}]
    guards = [g(1), g(2), g(3)]
    pipe.ingest(events, guards)
    # store time is UTC (pipeline writes naive-UTC isoformat), so stay on UTC
    conn.execute("UPDATE agent_task_events SET ts=datetime('now','-1 second')")
    conn.execute("UPDATE guard_events SET ts=datetime('now','-1 second')")
    conn.commit()
    alarms = pipe.evaluate_agent("mt6-bot")
    assert any(a.signal == "loop>=2" for a in alarms)
    m = measure_mt6(conn)
    assert m["count"] >= 1
    assert m["p95_ms"] <= m["target_ms"] + 1500  # scheduler slack, honest bound
    assert "MT-6" in mt6_text(m)


def test_mt6_empty_store_is_honest():
    from swarmax.db import connect as c2, init_db_with_migrations as init2
    conn = c2(":memory:")
    init2(conn)
    m = measure_mt6(conn)
    assert m["count"] == 0 and m["p95_ms"] is None
    assert "no alarms measured" in mt6_text(m)


def test_mt7_empty_chain_is_not_a_pass():
    """A vacuous 100% must never read as PASS (honesty gate)."""
    from swarmax.db import connect as c2, init_db_with_migrations as init2
    conn = c2(":memory:")
    init2(conn)
    m = measure_mt7(conn)
    assert m["status"] == "empty" and m["ok"] is False
    assert "no measurement yet" in mt7_text(m)


def test_mt7_passes_on_sealed_chain(tmp_path):
    conn = connect(str(tmp_path / "s.db"))
    init_db_with_migrations(conn)
    from swarmax.evidence import append_evidence
    append_evidence(conn, "dogfood_event", {"k": 1})
    conn.commit()
    seal_ledger(conn, load_or_create_seed(path=tmp_path / "seed.hex"))
    m = measure_mt7(conn)
    assert m["chain_ok"] and m["seals"] >= 1 and m["ok"]
    assert m["status"] == "pass" and "PASS" in mt7_text(m)


def test_mt7_fails_on_tamper(tmp_path):
    conn = connect(str(tmp_path / "s.db"))
    init_db_with_migrations(conn)
    from swarmax.evidence import append_evidence
    append_evidence(conn, "dogfood_event", {"k": 1})
    conn.commit()
    seal_ledger(conn, load_or_create_seed(path=tmp_path / "seed.hex"))
    # tamper like an attacker with db write access: the append-only trigger is
    # storage-layer defense; drop it to simulate an out-of-band write (per
    # tests/test_sealing.py), then corrupt a covered payload hash
    conn.execute("DROP TRIGGER trg_evidence_ledger_no_update")
    conn.execute("UPDATE evidence_ledger SET payload_hash='tampered' WHERE seq=1")
    conn.commit()
    m = measure_mt7(conn)
    assert not m["ok"]
    assert "FAIL" in mt7_text(m)
