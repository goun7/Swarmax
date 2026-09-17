"""OTLP relay bridge — accept UNSIGNED OTLP/HTTP from any agent framework,
re-emit SIGNED batches to Swarmax ingest (§4.3 HMAC anti-replay).

Why: most frameworks (LangChain, CrewAI, AutoGen, OpenLLMetry, OpenAI SDKs
via exporters…) already ship OpenTelemetry exporters. Point them at this
relay instead of a vendor endpoint and the whole fleet lands in Swarmax
without code changes:

    # 1) run the relay next to your ingest
    SWARMAX_RELAY_KEY=mykey SWARMAX_RELAY_SECRET=... \\
    SWARMAX_INGEST=http://127.0.0.1:4318 swarmax-otel-relay

    # 2) point any framework's OTLP exporter at it (no SDK, no keys there):
    OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4319

The relay is a pure forwarder: it validates shape, adds nothing to the
payload, signs the exact bytes with the X-SWX-* HMAC headers and forwards
to ``/v1/traces``. Fail-closed: if Swarmax ingest is down, upstream gets 503
and retries (OTel exporters retry 429/503 by spec) — telemetry is never
dropped silently, because silence would break the evidence chain.

Run inside ``OtlpIngest``-shaped threading HTTP server; zero dependencies.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

__all__ = ["OtelRelay", "serve", "main"]


class OtelRelay:
    """Signs and forwards OTLP/HTTP+JSON bodies to a Swarmax ingest."""

    def __init__(self, ingest_url: str, key_id: str, secret: bytes, *,
                 timeout_s: float = 10.0) -> None:
        u = urlparse(ingest_url if "://" in ingest_url else "http://" + ingest_url)
        self.host = u.hostname or "127.0.0.1"
        self.port = u.port or (443 if u.scheme == "https" else 80)
        self.https = u.scheme == "https"
        self.path = (u.path.rstrip("/") or "") + "/v1/traces"
        self.key_id, self.secret = key_id, secret
        self.timeout = timeout_s
        self.forwarded = 0
        self.rejected = 0

    def sign(self, body: bytes) -> dict[str, str]:
        ts = str(int(time.time()))
        nonce = uuid.uuid4().hex[:24]
        sig = hmac.new(self.secret, f"{ts}.{nonce}".encode() + body,
                       hashlib.sha256).hexdigest()
        return {"X-SWX-Key": self.key_id, "X-SWX-Timestamp": ts,
                "X-SWX-Nonce": nonce, "X-SWX-Signature": sig,
                "Content-Type": "application/json"}

    def forward(self, body: bytes) -> tuple[int, bytes]:
        """POST signed body to Swarmax; returns (status, response fragment)."""
        conn = (http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout)
                if self.https else
                http.client.HTTPConnection(self.host, self.port, timeout=self.timeout))
        try:
            conn.request("POST", self.path, body=body, headers=self.sign(body))
            resp = conn.getresponse()
            frag = resp.read(512)
            if resp.status in (200, 202):
                self.forwarded += 1
            else:
                self.rejected += 1
            return resp.status, frag
        finally:
            conn.close()


class _Handler(BaseHTTPRequestHandler):
    relay: OtelRelay = None  # injected by serve()

    def do_POST(self):
        if not self.path.startswith("/v1/traces"):
            self._json(404, b'{"error":"only /v1/traces"}')
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._json(400, b'{"error":"bad Content-Length"}')
            return
        if length <= 0 or length > 32 * 1024 * 1024:
            self._json(413, b'{"error":"empty or oversized body"}')
            return
        body = self.rfile.read(length)
        # shape sanity: OTLP JSON carries resourceSpans
        if b"resourceSpans" not in body:
            self._json(400, b'{"error":"not OTLP/JSON (resourceSpans missing)"}')
            return
        try:
            status, frag = self.relay.forward(body)
        except OSError as exc:
            # fail-closed: upstream retries (OTel spec), nothing dropped silently
            self._json(503, b'{"error":"swarmax ingest unreachable"}')
            return
        self._json(status if status in (200, 202) else 502, frag or b"{}")

    def do_GET(self):
        if self.path == "/healthz":
            self._json(200, b'{"ok":true,"relay":true}')
            return
        self._json(404, b'{"error":"not found"}')

    def _json(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet by default
        pass


def serve(ingest_url: str, key_id: str, secret: bytes, host: str = "127.0.0.1",
          port: int = 4319) -> tuple[ThreadingHTTPServer, OtelRelay]:
    relay = OtelRelay(ingest_url, key_id, secret)
    handler = type("BoundHandler", (_Handler,), {"relay": relay})
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd, relay


def main() -> None:  # pragma: no cover — thin CLI
    import argparse
    p = argparse.ArgumentParser(description="Unsigned OTLP -> signed Swarmax relay")
    p.add_argument("--ingest", default=os.environ.get("SWARMAX_INGEST", "http://127.0.0.1:4318"))
    p.add_argument("--key", default=os.environ.get("SWARMAX_RELAY_KEY", "relay"))
    p.add_argument("--secret", default=os.environ.get("SWARMAX_RELAY_SECRET", ""))
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=4319)
    a = p.parse_args()
    if not a.secret:
        p.error("SWARMAX_RELAY_SECRET env or --secret required")
    httpd, relay = serve(a.ingest, a.key, a.secret.encode(), a.host, a.port)
    print(f"swarmax-otel-relay :{a.port} -> {a.ingest} (key={a.key})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
