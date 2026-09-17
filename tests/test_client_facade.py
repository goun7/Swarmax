"""Integration facade: SwarmaxClient (task/span/guard) over the real OTLP path."""
import threading
import time

import pytest

from swarmax import LoopDetected, SwarmaxClient
from swarmax.db import connect, init_db_with_migrations
from swarmax.dogfood import FleetSdk  # noqa: F401  (back-compat surface)
from swarmax.otlp import OtlpIngest


@pytest.fixture()
def ingest_server(tmp_path):
    conn = connect(str(tmp_path / "d.db"))
    init_db_with_migrations(conn)
    ingest = OtlpIngest(conn, {"demo": b"facade-secret"})
    srv = ingest.serve("127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.1)
    yield f"http://127.0.0.1:{port}", conn
    srv.shutdown()


def _events(conn, agent):
    return conn.execute(
        "SELECT * FROM agent_task_events WHERE agent_id=? ORDER BY ts",
        (agent,)).fetchall()


def test_task_facade_records_real_event(ingest_server):
    base, conn = ingest_server
    client = SwarmaxClient(base, "demo", b"facade-secret")
    client.set_agent("fac-bot", model="m-1")
    tid = client.task("t-1", cost_usd=0.01, tokens_in=10, tokens_out=5,
                      latency_ms=40)
    assert tid == "t-1" and client.flush() == 1
    rows = _events(conn, "fac-bot")
    assert len(rows) == 1 and rows[0]["task_id"] == "t-1"
    assert rows[0]["model_name"] == "m-1"
    assert rows[0]["input_tokens"] == 10


def test_span_context_times_block_and_captures_error(ingest_server):
    base, conn = ingest_server
    client = SwarmaxClient(base, "demo", b"facade-secret", agent_id="span-bot",
                           default_cost_usd=0.002)
    with pytest.raises(ValueError):
        with client.span() as s:
            time.sleep(0.01)
            raise ValueError("boom")
    assert client.flush() == 1
    row = _events(conn, "span-bot")[0]
    assert row["error_class"] == "ValueError"
    assert row["latency_ms"] >= 8


def test_guard_allows_distinct_blocks_repeats(ingest_server):
    base, conn = ingest_server
    client = SwarmaxClient(base, "demo", b"facade-secret", agent_id="g-bot")

    def tool(q):
        return f"r:{q}"

    assert client.guard("tool", tool, "a") == "r:a"
    assert client.guard("tool", tool, "b") == "r:b"     # distinct -> reset
    assert client.guard("tool", tool, "a") == "r:a"     # 1st repeat ok
    assert client.flush() == 3
    assert all(r["error_class"] is None for r in _events(conn, "g-bot"))


def test_guard_blocks_third_identical_call(ingest_server):
    base, conn = ingest_server
    client = SwarmaxClient(base, "demo", b"facade-secret", agent_id="g2-bot")
    calls = {"n": 0}

    def tool(q):
        calls["n"] += 1
        return q

    client.guard("tool", tool, "same")
    client.guard("tool", tool, "same")
    with pytest.raises(LoopDetected):
        client.guard("tool", tool, "same")
    assert calls["n"] == 2                     # 3rd never executed
    assert client.flush() == 3
    rows = _events(conn, "g2-bot")
    assert rows[-1]["error_class"] == "loop"   # blocked attempt recorded


def test_guard_distinct_call_resets_streak(ingest_server):
    base, conn = ingest_server
    client = SwarmaxClient(base, "demo", b"facade-secret", agent_id="g3-bot")

    def tool(q):
        return q

    client.guard("tool", tool, "x")
    client.guard("tool", tool, "x")
    assert client.guard("tool", tool, "y") == "y"   # streak reset
    client.guard("tool", tool, "x")
    client.guard("tool", tool, "x")
    with pytest.raises(LoopDetected):
        client.guard("tool", tool, "x")             # fresh streak of 3
    assert client.flush() == 6
