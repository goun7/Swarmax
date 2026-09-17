"""F1 OTLP ingest tests: span conversion, anti-replay matrix, HTTP flow, metrics."""
import hashlib
import hmac
import json
import time
import urllib.request

import pytest

from swarmax.db import connect, init_db_with_migrations
from swarmax.otlp import OtlpIngest, ReplayGuard, _attr_map, _span_to_event


def make_ingest() -> OtlpIngest:
    conn = connect(":memory:")
    return OtlpIngest(conn, {b"swx-key-1": b"secret-1"})


def otlp_span(*, agent: str = "agent-1", model: str = "gpt-4o-mini",
              status: int = 0, error_type: str | None = None,
              cost: str = "0.01", task_id: str = "t1") -> dict:
    attrs = [
        {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
        {"key": "gen_ai.request.model", "value": {"stringValue": model}},
        {"key": "gen_ai.usage.input_tokens", "value": {"intValue": "900"}},
        {"key": "gen_ai.usage.output_tokens", "value": {"intValue": "350"}},
        {"key": "gen_ai.usage.cost", "value": {"doubleValue": float(cost)}},
        {"key": "swx.agent.id", "value": {"stringValue": agent}},
        {"key": "swx.task.id", "value": {"stringValue": task_id}},
    ]
    if error_type:
        attrs.append({"key": "error.type", "value": {"stringValue": error_type}})
    now_ns = time.time_ns()
    return {
        "traceId": "ab" * 16, "spanId": "cd" * 8,
        "name": "gen_ai.chat", "timeUnixNano": str(now_ns - 500_000_000),
        "timeEndedUnixNano": str(now_ns),
        "attributes": attrs,
        "status": {"code": status},
    }


def otlp_payload(span) -> dict:
    return {"resourceSpans": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "synthetic-fleet"}}]},
        "scopeSpans": [{"spans": [span]}]}]}


# ---------------------------------------------------------------- conversion

def test_attr_map_and_span_conversion():
    span = otlp_span()
    event = _span_to_event("agent-1", span, _attr_map(span["attributes"]), {})
    assert event["agent_id"] == "agent-1"
    assert event["model_name"] == "gpt-4o-mini"
    assert event["input_tokens"] == 900
    assert event["cost_usd"] == pytest.approx(0.01)
    assert event["status"] == "ok"
    assert event["error_class"] is None


def test_non_genai_span_skipped():
    span = otlp_span()
    span["name"] = "http.get"; span["attributes"] = []
    assert _span_to_event("a", span, {}, {}) is None


def test_ingest_traces_end_to_end():
    ingest = make_ingest()
    n = ingest.ingest_traces(otlp_payload(otlp_span()))
    assert n == 1
    count = ingest.conn.execute(
        "SELECT COUNT(*) c FROM agent_task_events").fetchone()["c"]
    assert count == 1


# ---------------------------------------------------------------- anti-replay

def signed_headers(body: bytes, *, secret: bytes = b"secret-1", key_id: str = "swx-key-1",
                   nonce: str = "n1", ts: int | None = None) -> dict:
    timestamp = str(ts if ts is not None else int(time.time()))
    sig = hmac.new(secret, f"{timestamp}.{nonce}".encode() + body,
                   hashlib.sha256).hexdigest()
    return {"X-SWX-Key": key_id, "X-SWX-Timestamp": timestamp,
            "X-SWX-Nonce": nonce, "X-SWX-Signature": sig}


def test_replay_guard_accepts_fresh_request():
    guard = ReplayGuard({b"swx-key-1": b"secret-1"})
    body = b"{}"
    h = signed_headers(body)
    assert guard.check(h["X-SWX-Key"], h["X-SWX-Timestamp"], h["X-SWX-Nonce"],
                       h["X-SWX-Signature"], body) is None


def test_replay_guard_rejects_replay_and_tampering():
    guard = ReplayGuard({b"swx-key-1": b"secret-1"})
    body = b"{}"
    h = signed_headers(body)
    assert guard.check(h["X-SWX-Key"], h["X-SWX-Timestamp"], h["X-SWX-Nonce"],
                       h["X-SWX-Signature"], body) is None
    # exact same nonce+signature again => replay
    assert guard.check(h["X-SWX-Key"], h["X-SWX-Timestamp"], h["X-SWX-Nonce"],
                       h["X-SWX-Signature"], body) == "replay"
    # tampered body, same signature => bad signature
    h2 = signed_headers(body, nonce="n2")
    assert guard.check(h2["X-SWX-Key"], h2["X-SWX-Timestamp"], h2["X-SWX-Nonce"],
                       h2["X-SWX-Signature"], b'{"evil":true}') == "bad_signature"
    # unknown key
    h3 = signed_headers(body, nonce="n3", key_id="nope")
    assert guard.check(h3["X-SWX-Key"], h3["X-SWX-Timestamp"], h3["X-SWX-Nonce"],
                       h3["X-SWX-Signature"], body) == "unknown_key"
    # clock skew beyond window
    h4 = signed_headers(body, nonce="n4", ts=int(time.time()) - 4000)
    assert guard.check(h4["X-SWX-Key"], h4["X-SWX-Timestamp"], h4["X-SWX-Nonce"],
                       h4["X-SWX-Signature"], body) == "timestamp_skew"


# ---------------------------------------------------------------- HTTP flow

def test_http_flow_and_reject_metrics():
    ingest = make_ingest()
    server = ingest.serve("127.0.0.1", 0)  # port 0 => OS picks a free port
    port = server.server_address[1]
    import threading
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{port}"
        body = json.dumps(otlp_payload(otlp_span())).encode()
        req = urllib.request.Request(
            base + "/v1/traces", data=body, method="POST",
            headers={**signed_headers(body), "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            out = json.loads(resp.read())
            assert out["acceptedSpans"] == 1

        # unsigned request -> 401 + ingest_reject_total
        req2 = urllib.request.Request(base + "/v1/traces", data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req2, timeout=5)
            assert False, "unsigned request must fail"
        except urllib.error.HTTPError as e:
            assert e.code == 401

        # replayed exact request -> 401 again
        req3 = urllib.request.Request(
            base + "/v1/traces", data=body, method="POST",
            headers={**signed_headers(body), "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req3, timeout=5)
            assert False, "replayed request must fail"
        except urllib.error.HTTPError as e:
            assert e.code == 401

        with urllib.request.urlopen(base + "/metrics", timeout=5) as resp:
            text = resp.read().decode()
        assert "otlp_accepted_spans_total 1" in text
        assert "ingest_reject_total 2" in text
        # unsigned => unknown_key; replayed nonce => replay
        assert 'otlp_reject_reason{reason="unknown_key"}' in text
        assert 'otlp_reject_reason{reason="replay"}' in text
    finally:
        server.shutdown()
        server.server_close()
