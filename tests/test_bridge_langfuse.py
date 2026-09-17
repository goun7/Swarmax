"""Langfuse pull bridge: fake Langfuse API -> real Swarmax ingest -> store."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from swarmax.bridges import LangfuseBridge
from swarmax.db import connect, init_db_with_migrations
from swarmax.otlp import OtlpIngest

NOW = time.time()


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


OBS = [
    {"id": "obs-1", "traceId": "tr-1", "type": "GENERATION", "name": "support-bot",
     "model": "gpt-4o-mini", "startTime": _iso(NOW - 30), "endTime": _iso(NOW - 29),
     "usage": {"input": 120, "output": 40, "totalCost": 0.0021},
     "level": "DEFAULT", "env": "production"},
    {"id": "obs-2", "traceId": "tr-2", "type": "GENERATION", "name": "critic-bot",
     "model": "claude-3-5-sonnet", "startTime": _iso(NOW - 20), "endTime": _iso(NOW - 19),
     "usage": {"input": 900, "output": 10, "totalCost": 0.0044},
     "level": "ERROR", "statusMessage": "TimeoutError while calling vendor"},
    {"id": "obs-3", "traceId": "tr-3", "type": "SPAN", "name": "not-a-generation"},
]


class _FakeLangfuse(BaseHTTPRequestHandler):
    pulls = {"n": 0}

    def do_GET(self):
        if not self.path.startswith("/api/public/observations"):
            self.send_response(404)
            self.end_headers()
            return
        assert self.headers["Authorization"] == "Basic cGstbGY6c2stbGY="  # pk-lf:sk-lf
        _FakeLangfuse.pulls["n"] += 1
        body = json.dumps({"data": OBS}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence
        pass


@pytest.fixture()
def fake_lf():
    srv = HTTPServer(("127.0.0.1", 0), _FakeLangfuse)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


@pytest.fixture()
def swx_ingest(tmp_path):
    conn = connect(str(tmp_path / "b.db"))
    init_db_with_migrations(conn)
    ingest = OtlpIngest(conn, {"bridge": b"br-s3cret"})
    srv = ingest.serve("127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", conn
    srv.shutdown()


def test_bridge_maps_and_ingests(fake_lf, swx_ingest):
    swx, conn = swx_ingest
    bridge = LangfuseBridge(fake_lf, "pk-lf", "sk-lf", swx, "bridge", b"br-s3cret")
    n = bridge.sync(since_minutes=60)
    assert n == 2 and bridge.sent == 2 and bridge.rejected == 0
    rows = conn.execute(
        "SELECT agent_id, task_id, model_name, input_tokens, output_tokens,"
        " cost_usd, error_class FROM agent_task_events ORDER BY ts").fetchall()
    assert len(rows) == 2
    r1, r2 = rows
    assert r1["agent_id"] == "support-bot"
    assert r1["task_id"] == "tr-1:obs-1"
    assert r1["model_name"] == "gpt-4o-mini"
    assert r1["input_tokens"] == 120 and r1["output_tokens"] == 40
    assert r1["cost_usd"] == pytest.approx(0.0021)
    assert r1["error_class"] is None
    assert r2["agent_id"] == "critic-bot"
    assert r2["error_class"] == "TimeoutError"


def test_bridge_resync_is_idempotent(fake_lf, swx_ingest):
    swx, conn = swx_ingest
    bridge = LangfuseBridge(fake_lf, "pk-lf", "sk-lf", swx, "bridge", b"br-s3cret")
    bridge.sync()
    bridge.sync()   # same observation ids -> deterministic span ids -> deduped
    n = conn.execute("SELECT COUNT(*) FROM agent_task_events").fetchone()[0]
    assert n == 2
