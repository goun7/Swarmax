"""F1 OTLP/HTTP+JSON ingest — paper §4.3 (identity pairing + anti-replay), §7 F1.

Endpoints:
  POST /v1/traces | /v1/metrics | /v1/logs   OTLP/HTTP JSON. Spans carrying
                                             ``gen_ai.*``/``swx.*`` attributes are
                                             converted to task events and fed to the
                                             pipeline; evaluation runs per agent-day.
                                             ``swx.subject.id`` binds the span to a
                                             privacy data subject (B2 erase path).
  GET  /healthz                              liveness
  GET  /metrics                              counters (text/plain): received, accepted,
                                             rejected (+ reason), ingest_reject (§4.3)

Anti-replay (§4.3): every request must carry
  X-SWX-Key       shared key id
  X-SWX-Timestamp unix seconds (accepted skew ±300 s)
  X-SWX-Nonce     unique per request within the replay window
  X-SWX-Signature hex HMAC-SHA256(key, "{timestamp}.{nonce}.{body}")
Requests failing timestamp, nonce or HMAC checks are rejected with 401 and counted in
``ingest_reject_total``; never replayed, never double-counted (paper: "tekrar paketler
ingest_reject metriğine yazılır").
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .db import connect, init_db_with_migrations
from .pipeline import Pipeline

REPLAY_WINDOW_S = 300  # accepted clock skew / nonce retention (§4.3)


@dataclass
class ReplayGuard:
    """HMAC-SHA256 request authentication with timestamp skew + nonce cache."""
    keys: dict[str, bytes]                       # key_id -> secret
    skew_s: int = REPLAY_WINDOW_S
    _nonces: dict[str, float] = field(default_factory=dict)  # "key:nonce" -> seen_at
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        # tolerate bytes key ids at the API boundary
        self.keys = {k.decode() if isinstance(k, bytes) else k: v
                     for k, v in self.keys.items()}

    def check(self, key_id: str, timestamp: str, nonce: str,
              signature: str, body: bytes) -> str | None:
        """Return a rejection reason or None when the request is authentic+fresh."""
        secret = self.keys.get(key_id)
        if secret is None:
            return "unknown_key"
        try:
            ts = int(timestamp)
        except (TypeError, ValueError):
            return "bad_timestamp"
        if abs(time.time() - ts) > self.skew_s:
            return "timestamp_skew"
        if not nonce:
            return "missing_nonce"
        expected = hmac.new(
            secret, f"{timestamp}.{nonce}".encode() + body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ""):
            return "bad_signature"
        tag = f"{key_id}:{nonce}"
        now = time.time()
        with self._lock:
            self._gc(now)
            if tag in self._nonces:
                return "replay"
            self._nonces[tag] = now
        return None

    def _gc(self, now: float) -> None:
        for k in [k for k, t in self._nonces.items() if now - t > self.skew_s * 2]:
            del self._nonces[k]


class OtlpIngest:
    """OTLP/HTTP JSON → task events → Pipeline, plus auth/reject accounting."""

    def __init__(self, conn: sqlite3.Connection, keys: dict[str, bytes],
                 pipeline: Pipeline | None = None) -> None:
        self.conn = conn
        init_db_with_migrations(conn)
        self.pipe = pipeline or Pipeline(conn)
        self.guard = ReplayGuard(keys)
        self.counters: Counter[str] = Counter()
        self._lock = threading.Lock()
        self._db_lock = threading.Lock()   # serialize store writes across handlers

    # ------------------------------------------------------------------ OTLP → events
    def convert_traces(self, payload: dict) -> list[dict]:
        """Flatten OTLP/JSON ExportTraceServiceRequest spans into task events."""
        events: list[dict] = []
        rs = payload.get("resourceSpans", [])
        if isinstance(rs, dict):
            rs = [rs]
        for resource in rs:
            attrs = _attr_map(resource.get("resource", {}).get("attributes", []))
            scope_spans = resource.get("scopeSpans", [])
            if isinstance(scope_spans, dict):
                scope_spans = [scope_spans]
            for scope in scope_spans:
                for span in scope.get("spans", []):
                    sattrs = _attr_map(span.get("attributes", []))
                    events.append(_span_to_event(None, span, sattrs, attrs))
        return [e for e in events if e is not None]

    def convert_traces_for_tenant(self, payload: dict, tenant_id: str) -> list[dict]:
        """convert_traces + a tenant stamp (§8 multi-team deployment model)."""
        return [{**e, "tenant_id": tenant_id} for e in self.convert_traces(payload)]

    def ingest_traces(self, payload: dict, tenant_id: str | None = None) -> int:
        events = (self.convert_traces_for_tenant(payload, tenant_id)
                  if tenant_id else self.convert_traces(payload))
        if events:
            with self._db_lock:
                self.pipe.ingest(events)
        return len(events)

    # ------------------------------------------------------------------ accounting
    def note(self, counter: str) -> None:
        with self._lock:
            self.counters[counter] += 1

    def metrics_text(self) -> str:
        lines = [f"otlp_received_total {self.counters['otlp_received_total']}",
                 f"otlp_accepted_spans_total {self.counters['otlp_accepted_spans_total']}",
                 f"otlp_rejected_total {self.counters['otlp_rejected_total']}",
                 f"ingest_reject_total {self.counters['ingest_reject_total']}"]
        for reason, n in sorted(self.counters.items()):
            if reason.startswith("reject:"):
                lines.append(f'otlp_reject_reason{{reason="{reason[7:]}"}} {n}')
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ HTTP wiring
    def make_handler(self):  # noqa: ANN201 - factory returns a Handler class
        ingest = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence default stderr chatter
                pass

            def _send(self, code: int, body: bytes, ctype: str = "text/plain") -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path == "/healthz":
                    self._send(200, b"ok")
                elif self.path == "/metrics":
                    self._send(200, ingest.metrics_text().encode())
                else:
                    self._send(404, b"not found")

            def do_POST(self) -> None:
                if self.path not in ("/v1/traces", "/v1/metrics", "/v1/logs"):
                    self._send(404, b"not found")
                    return
                ingest.note("otlp_received_total")
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                reason = ingest.guard.check(
                    self.headers.get("X-SWX-Key"),
                    self.headers.get("X-SWX-Timestamp"),
                    self.headers.get("X-SWX-Nonce"),
                    self.headers.get("X-SWX-Signature"),
                    body)
                if reason:
                    ingest.note("ingest_reject_total")
                    ingest.note(f"reject:{reason}")
                    self._send(401, f"rejected: {reason}".encode())
                    return
                try:
                    payload = json.loads(body or b"{}")
                    if self.path == "/v1/traces":
                        n = ingest.ingest_traces(payload)
                    else:  # metrics/logs accepted+counted; trace-style handling at F1
                        ingest.note("otlp_rejected_total")
                        self._send(202, b'{"accepted": 0}')
                        return
                    ingest.note("otlp_accepted_spans_total")
                    self._send(200, json.dumps(
                        {"acceptedSpans": n, "rejectedSpans": 0}).encode())
                except (ValueError, KeyError, json.JSONDecodeError) as exc:
                    ingest.note("otlp_rejected_total")
                    ingest.note("reject:bad_payload")
                    self._send(400, f"bad payload: {exc}".encode())
                except Exception as exc:  # store failure: respond, never drop the line
                    ingest.note("otlp_errors_total")
                    self._send(500, f"ingest error: {exc}".encode())

        return Handler

    def serve(self, host: str = "127.0.0.1", port: int = 4318) -> ThreadingHTTPServer:
        server = ThreadingHTTPServer((host, port), self.make_handler())
        return server


# ------------------------------------------------------------------ helpers

def _attr_map(attributes: list[dict]) -> dict[str, object]:
    """OTLP KeyValue list → dict, honoring anyValue oneof."""
    out: dict[str, object] = {}
    for kv in attributes or []:
        key = kv.get("key")
        val = kv.get("value", {})
        for kind in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if kind in val:
                out[key] = val[kind]
                break
        else:
            if "arrayValue" in val:
                out[key] = [e.get("stringValue") for e in
                            val["arrayValue"].get("values", [])]
            else:
                out[key] = None
    return out


def _span_to_event(agent_id: str | None, span: dict, sattrs: dict,
                   rattrs: dict) -> dict | None:
    """Map one span onto agent_task_events columns; non-task spans return None.
    Agent identity (§4.3 pairing): span-level swx.agent.id/gen_ai.agent.id wins,
    falling back to resource-level, then service.name."""
    name = str(span.get("name") or "span")
    if sattrs.get("gen_ai.operation.name") is None and not name.startswith("gen_ai"):
        return None
    if agent_id is None:
        agent_id = str(sattrs.get("swx.agent.id")
                       or sattrs.get("gen_ai.agent.id")
                       or rattrs.get("swx.agent.id")
                       or rattrs.get("gen_ai.agent.id")
                       or rattrs.get("service.name") or "unknown-agent")
    status_code = (span.get("status") or {}).get("code", 0)
    error_class = sattrs.get("error.type") or sattrs.get("swx.error.class")
    ts_us = int(span.get("timeUnixNano") or 0)
    end_us = int(span.get("timeEndedUnixNano") or 0)
    latency_ms = max(0, (end_us - ts_us) // 1000) if end_us else 0
    return {
        "event_id": f"otlp-{span.get('traceId', '')}-{span.get('spanId', time.time_ns())}",
        "agent_id": agent_id,
        "task_id": str(sattrs.get("swx.task.id") or span.get("traceId") or "task"),
        "session_id": str(span.get("traceId") or ""),
        "model_name": str(sattrs.get("gen_ai.request.model")
                          or sattrs.get("gen_ai.response.model") or "unknown"),
        "input_tokens": int(sattrs.get("gen_ai.usage.input_tokens") or 0),
        "output_tokens": int(sattrs.get("gen_ai.usage.output_tokens") or 0),
        "cost_usd": float(sattrs.get("gen_ai.usage.cost") or 0.0),
        "latency_ms": latency_ms,
        "error_class": str(error_class) if error_class else None,
        "status": "error" if status_code == 2 else "ok",
        "synthetic": 0,
        "ts": _iso_from_ns(ts_us),
        "retry_count": int(sattrs.get("swx.retry.count") or 0),
        "ttft_s": float(sattrs.get("swx.ttft.s") or 0.0),
        "task_template": (str(sattrs["swx.task.template"])
                          if sattrs.get("swx.task.template") else None),
        "end_state_json": (str(sattrs["swx.end_state.json"])
                           if sattrs.get("swx.end_state.json") else None),
        # B2 (§10.3): optional privacy subject binding (GDPR/AI-Act erase path);
        # consumed by Pipeline.ingest → evidence anchor → per-subject crypto-shred
        "data_subject_id": (str(sattrs["swx.subject.id"])
                            if sattrs.get("swx.subject.id") else None),
    }


def _iso_from_ns(ns: int) -> str:
    if ns <= 0:
        ns = time.time_ns()
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ns / 1e9))


def main() -> None:
    """Standalone F1 ingest: SWX_INGEST_KEY_ID + SWX_INGEST_SECRET from env."""
    import argparse
    import os

    ap = argparse.ArgumentParser(description="Swarmax OTLP ingest (F1)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4318)
    ap.add_argument("--db", default=os.environ.get("SWX_DB", "data/swarmax.db"))
    args = ap.parse_args()
    secret = os.environ.get("SWX_INGEST_SECRET", "")
    if not secret:
        raise SystemExit("set SWX_INGEST_SECRET (shared HMAC secret); "
                         "optionally SWX_INGEST_KEY_ID (default: 'default')")
    conn = connect(args.db)
    ingest = OtlpIngest(conn, {os.environ.get("SWX_INGEST_KEY_ID", "default"): secret.encode()})
    server = ingest.serve(args.host, args.port)
    print(f"Swarmax OTLP ingest on http://{args.host}:{args.port} (db={args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
