"""OTLP relay: unsigned in -> signed out -> real Swarmax ingest -> store."""
import json
import threading
import time

import pytest

from swarmax.bridges import otel_relay
from swarmax.db import connect, init_db_with_migrations
from swarmax.otlp import OtlpIngest


def _otlp_body(agent="fw-bot", task="t-1", error=None):
    attrs = [
        {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
        {"key": "gen_ai.request.model", "value": {"stringValue": "m-1"}},
        {"key": "gen_ai.usage.cost", "value": {"doubleValue": 0.01}},
        {"key": "swx.agent.id", "value": {"stringValue": agent}},
        {"key": "swx.task.id", "value": {"stringValue": task}},
    ]
    if error:
        attrs.append({"key": "error.type", "value": {"stringValue": error}})
    return json.dumps({"resourceSpans": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "some-framework"}}]},
        "scopeSpans": [{"spans": [{
            "traceId": "1234567890abcdef1234567890abcdef",
            "spanId": "1234567890abcdef",
            "name": "gen_ai.chat",
            "timeUnixNano": str(time.time_ns()),
            "attributes": attrs,
            "status": {"code": 2 if error else 0}}]}]}]}).encode()


@pytest.fixture()
def ingest(tmp_path):
    conn = connect(str(tmp_path / "r.db"))
    init_db_with_migrations(conn)
    ing = OtlpIngest(conn, {"relay": b"relay-secret"})
    srv = ing.serve("127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", conn
    srv.shutdown()


@pytest.fixture()
def relay(ingest):
    httpd, r = otel_relay.serve(ingest[0], "relay", b"relay-secret",
                                host="127.0.0.1", port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.05)
    yield f"http://127.0.0.1:{httpd.server_address[1]}", ingest[1]
    httpd.shutdown()


def _post(url, body, headers=None):
    import http.client
    from urllib.parse import urlparse
    u = urlparse(url)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    conn.request("POST", u.path, body=body, headers=headers or
                 {"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def test_relay_forwards_unsigned_to_signed_ingest(relay):
    url, conn = relay
    status, _ = _post(url + "/v1/traces", _otlp_body())
    assert status == 200
    row = conn.execute(
        "SELECT agent_id, task_id, cost_usd FROM agent_task_events "
        "WHERE agent_id='fw-bot'").fetchone()
    assert row is not None and row["task_id"] == "t-1"
    assert row["cost_usd"] == pytest.approx(0.01)


def test_relay_rejects_non_otlp_shape(relay):
    url, conn = relay
    status, data = _post(url + "/v1/traces", b'{"hello": "world"}')
    assert status == 400 and b"resourceSpans" in data
    assert conn.execute("SELECT COUNT(*) FROM agent_task_events").fetchone()[0] == 0


def test_relay_fail_closed_when_ingest_down():
    httpd, r = otel_relay.serve("http://127.0.0.1:59999", "relay", b"s",
                                host="127.0.0.1", port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.05)
    port = httpd.server_address[1]
    try:
        status, data = _post(f"http://127.0.0.1:{port}/v1/traces", _otlp_body())
        assert status == 503 and b"unreachable" in data
    finally:
        httpd.shutdown()


def test_relay_healthz(relay):
    import urllib.request
    url = relay[0].replace("http://", "") 
    with urllib.request.urlopen(f"http://{url}/healthz", timeout=5) as resp:
        assert resp.status == 200
        assert b"relay" in resp.read()
