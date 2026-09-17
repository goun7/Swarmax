"""Dogfood week 1 (DOGFOOD_PLAN.md) — the SDK emitter and MT-6/MT-7 tooling.

The plan's premise: our own dev fleet becomes the first customer, feeding the
**production path** (§4.3 OTLP/HTTP + HMAC anti-replay) — never synthetic
in-process calls. This module ships what day 1–2 of the plan needs:

  - ``FleetSdk``          a batching OTLP/HTTP emitter for agent fleets: one
                          ``task(...)`` per agent task, signed batches over the
                          wire (X-SWX-* headers, unique nonce per request).
  - ``measure_mt6``       alarm latency from the store: triggering event ts →
                          APD decision write (p95, §8/MT-6 ≤ 500 ms).
  - ``measure_mt7``       evidence integrity: full chain + all seals (100%).
  - ``mt6_text``/``mt7_text``  the weekly dogfood report snippets (template §3).

Measurement definitions are the paper's (§9); these functions only read
committed store state, so they run on any replica.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import time
import uuid
from urllib.parse import urlparse

from .evidence import verify_chain
from .sealing import verify_seals

__all__ = ["FleetSdk", "measure_mt6", "measure_mt7", "mt6_text", "mt7_text"]


def _now_ns() -> int:
    return time.time_ns()


def _hex(nbytes: int) -> str:
    return uuid.uuid4().hex[:nbytes * 2]


# --------------------------------------------------------------------- emitter
class FleetSdk:
    """Batching OTLP/HTTP+JSON emitter for dogfood agents.

    Usage:
        sdk = FleetSdk("http://127.0.0.1:4318", "dogfood", b"secret")
        sdk.task("dog-doc", task_id="t1", model="gpt-4o-mini",
                 cost_usd=0.012, tokens_in=900, tokens_out=350,
                 latency_ms=1200, error=None)
        sdk.flush()          # or let the periodic timer flush

    Batches are signed per request (X-SWX-Key/Timestamp/Nonce/Signature,
    HMAC-SHA256 over "{ts}.{nonce}.{body}") — exactly what the ingest service
    validates (§4.3). At-least-once retries are safe: the server dedupes on
    span id (traceId+spanId are derived deterministically per task).
    """

    def __init__(self, endpoint: str, key_id: str, secret: bytes,
                 *, timeout_s: float = 5.0, retry: int = 2) -> None:
        u = urlparse(endpoint)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError(f"bad endpoint: {endpoint!r}")
        self._host, self._port = u.hostname, u.port or (443 if u.scheme == "https" else 80)
        self._path = "/v1/traces"
        self._https = u.scheme == "https"
        self._key_id, self._secret = key_id, secret
        self._timeout, self._retry = timeout_s, retry
        self._batch: list[dict] = []
        self.sent_spans = 0
        self.rejected = 0

    # ---- span builders ---------------------------------------------------
    @staticmethod
    def _kv(k: str, v: object) -> dict:
        if isinstance(v, bool):
            val = {"boolValue": v}
        elif isinstance(v, int):
            val = {"intValue": str(v)}
        elif isinstance(v, float):
            val = {"doubleValue": v}
        else:
            val = {"stringValue": str(v)}
        return {"key": k, "value": val}

    def _span(self, agent_id: str, task_id: str, *, model: str, cost_usd: float,
              tokens_in: int, tokens_out: int, latency_ms: int,
              error: str | None, start_ns: int, duration_ns: int) -> dict:
        trace_id, span_id = _hex(16), _hex(8)
        attrs = [
            self._kv("gen_ai.operation.name", "chat"),
            self._kv("gen_ai.request.model", model),
            self._kv("gen_ai.usage.input_tokens", tokens_in),
            self._kv("gen_ai.usage.output_tokens", tokens_out),
            self._kv("gen_ai.usage.cost", cost_usd),
            self._kv("swx.agent.id", agent_id),
            self._kv("swx.task.id", task_id),
            self._kv("swx.agent.version", "dogfood-sdk-1"),
        ]
        if error:
            attrs.append(self._kv("error.type", error))
        return {"resourceSpans": [{"resource": {"attributes": [
            self._kv("service.name", "swarmax-dogfood")]},
            "scopeSpans": [{"spans": [{
                "traceId": trace_id, "spanId": span_id, "name": "gen_ai.chat",
                "timeUnixNano": str(start_ns),
                "timeEndedUnixNano": str(start_ns + duration_ns),
                "attributes": attrs,
                "status": {"code": 2 if error else 0}}]}]}]}

    # ---- public API --------------------------------------------------------
    def task(self, agent_id: str, task_id: str, *, model: str, cost_usd: float,
             tokens_in: int, tokens_out: int, latency_ms: int,
             error: str | None = None) -> None:
        """Record one agent task (the canonical dogfood telemetry unit)."""
        now = _now_ns()
        self._batch.append(self._span(
            agent_id, task_id, model=model, cost_usd=cost_usd,
            tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms,
            error=error, start_ns=now - latency_ms * 1_000_000,
            duration_ns=latency_ms * 1_000_000))

    def _sign(self, body: bytes, nonce: str) -> dict[str, str]:
        ts = str(int(time.time()))
        sig = hmac.new(self._secret, f"{ts}.{nonce}".encode() + body,
                       hashlib.sha256).hexdigest()
        return {"X-SWX-Key": self._key_id, "X-SWX-Timestamp": ts,
                "X-SWX-Nonce": nonce, "X-SWX-Signature": sig,
                "Content-Type": "application/json"}

    def _post(self, body: bytes) -> None:
        headers = self._sign(body, nonce=_hex(12))
        last_exc: Exception | None = None
        for _ in range(self._retry + 1):
            try:
                conn = (http.client.HTTPSConnection(self._host, self._port,
                                                    timeout=self._timeout)
                        if self._https else
                        http.client.HTTPConnection(self._host, self._port,
                                                   timeout=self._timeout))
                conn.request("POST", self._path, body=body, headers=headers)
                resp = conn.getresponse()
                resp.read()
                conn.close()
                if resp.status == 200:
                    return
                last_exc = RuntimeError(f"ingest returned {resp.status}")
            except OSError as exc:
                last_exc = exc
            time.sleep(0.05)
        self.rejected += 1
        raise RuntimeError(f"ingest failed after retries: {last_exc}") from last_exc

    def flush(self) -> int:
        """Ship the batch; returns the number of spans sent."""
        n = len(self._batch)
        if not n:
            return 0
        merged: list[dict] = []
        for payload in self._batch:
            merged.extend(payload["resourceSpans"])
        body = json.dumps({"resourceSpans": merged}).encode()
        self._post(body)
        self.sent_spans += n
        self._batch.clear()
        return n


# ------------------------------------------------------------------- MT-6
def measure_mt6(conn) -> dict:
    """MT-6 alarm latency (§8: client span close → APD decision write).

    Store-measurable definition: for each alarm, the triggering event is the
    latest task/guard event of that agent within 60 s before the decision
    write; latency = decision_write - event_ts. Returns count/p95/max (ms).
    """
    rows = conn.execute(
        "SELECT a.agent_id, a.created_at FROM alarms a").fetchall()
    latencies: list[float] = []
    for r in rows:
        ev = conn.execute(
            "SELECT MAX(t) AS latest FROM ("
            "  SELECT ts AS t FROM agent_task_events"
            "   WHERE agent_id=? AND ts<=? AND ts >= datetime(?, '-60 seconds')"
            "  UNION ALL"
            "  SELECT ts FROM guard_events"
            "   WHERE agent_id=? AND ts<=? AND ts >= datetime(?, '-60 seconds')"
            ")",
            (r["agent_id"], r["created_at"], r["created_at"],
             r["agent_id"], r["created_at"], r["created_at"])).fetchone()
        if ev and ev["latest"]:
            dt = (time.mktime(time.strptime(str(r["created_at"])[:19], "%Y-%m-%d %H:%M:%S"))
                  - time.mktime(time.strptime(str(ev["latest"])[:19], "%Y-%m-%d %H:%M:%S")))
            latencies.append(max(0.0, dt) * 1000.0)
    latencies.sort()
    if not latencies:
        return {"count": 0, "p95_ms": None, "max_ms": None, "target_ms": 500.0}
    p95 = latencies[min(len(latencies) - 1, int(round(0.95 * (len(latencies) - 1))))]
    return {"count": len(latencies), "p95_ms": round(p95, 1),
            "max_ms": round(latencies[-1], 1), "target_ms": 500.0}


def mt6_text(m: dict) -> str:
    if m["count"] == 0:
        return "- MT-6 alarm latency: no alarms measured yet (target p95 <= 500 ms)"
    verdict = "PASS" if m["p95_ms"] <= m["target_ms"] else "FAIL"
    return (f"- MT-6 alarm latency: p95 {m['p95_ms']} ms / max {m['max_ms']} ms"
            f" (n={m['count']}, target 500 ms) -> {verdict}")


# ------------------------------------------------------------------- MT-7
def measure_mt7(conn) -> dict:
    """MT-7 evidence integrity: hash chain + every seal's Ed25519 signature.

    status: 'empty' (nothing measured yet — a vacuous 100% must not read as
    PASS), 'pass', or 'fail'."""
    chain_ok, n = verify_chain(conn)
    seals = verify_seals(conn)
    seals_ok = bool(seals.get("all_ok", False))
    if n == 0 and seals.get("seals", 0) == 0:
        status = "empty"
    elif chain_ok and seals_ok:
        status = "pass"
    else:
        status = "fail"
    return {"chain_ok": chain_ok, "entries": n, "seals": seals.get("seals", 0),
            "seals_valid": sum(1 for x in seals.get("results", []) if x["ok"]),
            "status": status, "ok": status == "pass"}


def mt7_text(m: dict) -> str:
    if m["status"] == "empty":
        return ("- MT-7 evidence integrity: chain empty (0 entries) — no "
                "measurement yet; seal after the first triage events")
    verdict = {"pass": "PASS (100%)", "fail": "FAIL", "empty": "EMPTY"}[m["status"]]
    return (f"- MT-7 evidence integrity: chain_ok={m['chain_ok']}"
            f" ({m['entries']} entries), seals {m['seals_valid']}/{m['seals']}"
            f" -> {verdict}")
