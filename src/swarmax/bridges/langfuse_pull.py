"""Langfuse → Swarmax bridge: pull traces, emit signed ``gen_ai.*`` spans.

One-way, read-only pull from any Langfuse deployment (cloud or self-hosted):

    python -m swarmax.bridges.langfuse_pull \
        --lf-url https://cloud.langfuse.com --lf-pk pk-lf-... --lf-sk sk-lf-... \
        --swx http://127.0.0.1:4318 --swx-key mykey --swx-secret ... \
        --since-min 60

Mapping (Langfuse observation → Swarmax task event):

  type=GENERATION          → task span; name/gen_ai.request.model carried
  usage.input/output       → gen_ai.usage.input_tokens / output_tokens
  usage.totalCost          → gen_ai.usage.cost (fallback: unit costs × tokens)
  latency (computed)       → span start/end from timestamps
  level=ERROR / statusMsg  → error.type = first token of statusMessage
  traceId / id             → swx.task.id = "<traceId>:<obsId>"
  env / tags               → resource swx.tenant / swx.tag (first tag)

Auth: Langfuse public API uses HTTP Basic auth (public_key:secret_key) on
``/api/public/observations``; Swarmax side uses the X-SWX-* HMAC headers —
the exact wire contract ``otlp.OtlpIngest`` validates.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json
import time
import urllib.parse
import urllib.request
import uuid

__all__ = ["LangfuseBridge", "main"]


def _basic(user: str, pwd: str) -> str:
    raw = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return f"Basic {raw}"


class LangfuseBridge:
    """Pull-based Langfuse → Swarmax emitter (stdlib only, deterministic ids)."""

    def __init__(self, lf_url: str, lf_public_key: str, lf_secret_key: str,
                 swx_endpoint: str, swx_key_id: str, swx_secret: bytes, *,
                 timeout_s: float = 10.0) -> None:
        u = urllib.parse.urlparse(lf_url if "://" in lf_url else "https://" + lf_url)
        self._lf_host, self._lf_port = u.hostname, u.port or (443 if u.scheme == "https" else 80)
        self._lf_https, self._lf_auth = u.scheme == "https", _basic(lf_public_key, lf_secret_key)
        self._lf_path = (u.path.rstrip("/") + "/api/public/observations") or "/api/public/observations"
        e = urllib.parse.urlparse(swx_endpoint if "://" in swx_endpoint else "http://" + swx_endpoint)
        self._swx_host, self._swx_port = e.hostname, e.port or (443 if e.scheme == "https" else 80)
        self._swx_https, self._swx_key, self._swx_secret = e.scheme == "https", swx_key_id, swx_secret
        self.timeout = timeout_s
        self.sent = 0
        self.rejected = 0

    # -- Langfuse side -------------------------------------------------------
    def fetch_observations(self, *, since_minutes: int = 60, limit: int = 100) -> list[dict]:
        q = urllib.parse.urlencode({"fromTimestamp": _iso_utc(since_minutes), "limit": limit})
        path = f"{self._lf_path}?{q}"
        conn = (http.client.HTTPSConnection(self._lf_host, self._lf_port, timeout=self.timeout)
                if self._lf_https else
                http.client.HTTPConnection(self._lf_host, self._lf_port, timeout=self.timeout))
        try:
            conn.request("GET", path, headers={"Authorization": self._lf_auth,
                                               "Accept": "application/json"})
            resp = conn.getresponse()
            body = resp.read()
            if resp.status != 200:
                raise RuntimeError(f"langfuse API {resp.status}: {body[:200]!r}")
            data = json.loads(body.decode("utf-8"))
        finally:
            conn.close()
        return [o for o in data.get("data", []) if o.get("type") == "GENERATION"]

    # -- Swarmax side --------------------------------------------------------
    def _span(self, obs: dict) -> dict:
        trace_id = hashlib.sha256(str(obs.get("traceId") or obs["id"]).encode()).hexdigest()[:32]
        span_id = hashlib.sha256(str(obs["id"]).encode()).hexdigest()[:16]
        started = _ns(obs.get("startTime"))
        ended = _ns(obs.get("endTime")) or started
        usage = obs.get("usage") or {}
        model = obs.get("model") or obs.get("providedModelName") or "unknown"
        cost = obs.get("cost") if obs.get("cost") is not None else usage.get("totalCost") or 0.0
        error = None
        if (obs.get("level") == "ERROR") or obs.get("statusMessage"):
            msg = str(obs.get("statusMessage") or "ERROR")
            error = msg.split()[0][:64] or "error"
        attrs = _attrs([
            ("gen_ai.operation.name", "chat"),
            ("gen_ai.request.model", model),
            ("gen_ai.usage.input_tokens", int(usage.get("input") or 0)),
            ("gen_ai.usage.output_tokens", int(usage.get("output") or 0)),
            ("gen_ai.usage.cost", float(cost)),
            ("swx.agent.id", str(obs.get("name") or "langfuse-gen")),
            ("swx.task.id", f"{obs.get('traceId')}:{obs['id']}"),
            ("swx.agent.version", "langfuse-bridge-1"),
            ("swx.tenant", str(obs.get("env") or "default")),
        ])
        if error:
            attrs.append(_attr("error.type", error))
        return {"resourceSpans": [{"resource": {"attributes": _attrs([
            ("service.name", "swarmax-langfuse-bridge")])},
            "scopeSpans": [{"spans": [{
                "traceId": trace_id, "spanId": span_id, "name": "gen_ai.chat",
                "timeUnixNano": str(started),
                "timeEndedUnixNano": str(max(started, ended)),
                "attributes": attrs,
                "status": {"code": 2 if error else 0}}]}]}]}

    def _sign(self, body: bytes, nonce: str) -> dict[str, str]:
        ts = str(int(time.time()))
        sig = hmac.new(self._swx_secret, f"{ts}.{nonce}".encode() + body,
                       hashlib.sha256).hexdigest()
        return {"X-SWX-Key": self._swx_key, "X-SWX-Timestamp": ts,
                "X-SWX-Nonce": nonce, "X-SWX-Signature": sig,
                "Content-Type": "application/json"}

    def emit(self, observations: list[dict]) -> int:
        """Emit mapped spans in one signed batch; returns accepted count."""
        spans = [self._span(o) for o in observations]
        if not spans:
            return 0
        body = json.dumps(spans[0] if len(spans) == 1 else
                          {"resourceSpans": spans[0]["resourceSpans"]}).encode("utf-8")
        if len(spans) > 1:
            body = json.dumps(_merge_spans(spans)).encode("utf-8")
        headers = self._sign(body, nonce=uuid.uuid4().hex[:24])
        conn = (http.client.HTTPSConnection(self._swx_host, self._swx_port, timeout=self.timeout)
                if self._swx_https else
                http.client.HTTPConnection(self._swx_host, self._swx_port, timeout=self.timeout))
        try:
            conn.request("POST", "/v1/traces", body=body, headers=headers)
            resp = conn.getresponse()
            resp.read()
            if resp.status in (200, 202):
                self.sent += len(spans)
                return len(spans)
            self.rejected += len(spans)
            raise RuntimeError(f"swarmax ingest {resp.status}: {body[:120]!r}")
        finally:
            conn.close()

    def sync(self, *, since_minutes: int = 60, limit: int = 100) -> int:
        """One pull-emit pass. Deterministic ids make re-runs idempotent."""
        return self.emit(self.fetch_observations(since_minutes=since_minutes, limit=limit))


# -- helpers -----------------------------------------------------------------
def _attr(k: str, v) -> dict:
    if isinstance(v, bool):
        val = {"boolValue": v}
    elif isinstance(v, int):
        val = {"intValue": str(v)}
    elif isinstance(v, float):
        val = {"doubleValue": v}
    else:
        val = {"stringValue": str(v)}
    return {"key": k, "value": val}


def _attrs(pairs) -> list[dict]:
    return [_attr(k, v) for k, v in pairs]


def _merge_spans(spans: list[dict]) -> dict:
    merged: dict[str, dict] = {}
    for s in spans:
        rs = s["resourceSpans"][0]
        svc = json.dumps(rs["resource"])
        merged.setdefault(svc, []).extend(rs["scopeSpans"][0]["spans"])
    return {"resourceSpans": [
        {"resource": json.loads(svc), "scopeSpans": [{"spans": spans}]}
        for svc, spans in merged.items()]}


def _iso_utc(minutes: int) -> str:
    t = time.gmtime(time.time() - minutes * 60)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", t)


def _ns(iso: str | None) -> int:
    if not iso:
        return time.time_ns()
    s = iso.replace("Z", "+00:00")
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(s)
    except ValueError:
        return time.time_ns()
    return int(dt.timestamp() * 1_000_000_000)


def main() -> None:  # pragma: no cover — thin CLI
    import argparse
    p = argparse.ArgumentParser(description="Langfuse -> Swarmax one-pass sync")
    p.add_argument("--lf-url", required=True)
    p.add_argument("--lf-pk", required=True)
    p.add_argument("--lf-sk", required=True)
    p.add_argument("--swx", required=True)
    p.add_argument("--swx-key", required=True)
    p.add_argument("--swx-secret", required=True)
    p.add_argument("--since-min", type=int, default=60)
    p.add_argument("--limit", type=int, default=100)
    a = p.parse_args()
    bridge = LangfuseBridge(a.lf_url, a.lf_pk, a.lf_sk, a.swx, a.swx_key,
                            a.swx_secret.encode())
    n = bridge.sync(since_minutes=a.since_min, limit=a.limit)
    print(f"langfuse-bridge: emitted {n} spans "
          f"(sent={bridge.sent}, rejected={bridge.rejected})")


if __name__ == "__main__":  # pragma: no cover
    main()
