#!/usr/bin/env python
"""End-to-end smoke: OTLP ingest → alarms → evidence sealing → console + report.

  python scripts/smoke_e2e.py            (temp DB, ephemeral ports, ~2 s)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swarmax.console import FleetConsole  # noqa: E402
from swarmax.db import connect, init_db_with_migrations  # noqa: E402
from swarmax.otlp import OtlpIngest  # noqa: E402
from swarmax.report import WeeklyReport  # noqa: E402
from swarmax.sealing import load_or_create_seed, seal_ledger, verify_seals  # noqa: E402


def otlp_payload(agent: str, error: str | None, status: int, smoke_i: int = 0) -> dict:
    now_ns = time.time_ns()
    attrs = [
        {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
        {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o-mini"}},
        {"key": "gen_ai.usage.cost", "value": {"doubleValue": 0.02}},
        {"key": "swx.agent.id", "value": {"stringValue": agent}},
    ]
    if error:
        attrs.append({"key": "error.type", "value": {"stringValue": error}})
    return {"resourceSpans": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "smoke"}}]},
        "scopeSpans": [{"spans": [{
            "traceId": ("ab" * 15 + f"{smoke_i:02x}"),
            "spanId": ("cd" * 7 + f"{smoke_i:02x}"), "name": "gen_ai.chat",
            "timeUnixNano": str(now_ns - 400_000_000),
            "timeEndedUnixNano": str(now_ns),
            "attributes": attrs, "status": {"code": status}}]}]}]}


def signed_headers(body: bytes, secret: bytes = b"smoke-secret", nonce: str = "x") -> dict:
    ts = str(int(time.time()))
    sig = hmac.new(secret, f"{ts}.{nonce}".encode() + body, hashlib.sha256).hexdigest()
    return {"X-SWX-Key": "smoke", "X-SWX-Timestamp": ts,
            "X-SWX-Nonce": nonce, "X-SWX-Signature": sig}


def main() -> int:
    from datetime import datetime, timedelta, timezone

    with tempfile.TemporaryDirectory() as td:
        conn = connect(str(Path(td) / "swx.db"))
        init_db_with_migrations(conn)
        ingest = OtlpIngest(conn, {"smoke": b"smoke-secret"})
        server = ingest.serve("127.0.0.1", 0)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()

        # 1. ship 12 spans: 6 error (rate 50% > 20%) over 12 s via OTLP
        for i in range(12):
            body = json.dumps(otlp_payload(
                "smoke-agent", "timeout" if i % 2 == 0 else None,
                2 if i % 2 == 0 else 0, smoke_i=i)).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/traces", data=body, method="POST",
                headers={**signed_headers(body, nonce=f"n{i}"),
                         "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)

        # force the error window: rewrite last 12 task events into the last 24 s
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.execute("UPDATE agent_task_events SET ts=? WHERE agent_id='smoke-agent'",
                     ((now - timedelta(seconds=20)).isoformat(sep=" "),))
        conn.commit()
        # simulate a calibrated agent (§3.3: fresh production agents are suppressed
        # during their 14-day calibration window — the paper's design, verified;
        # D1: the window is persisted, so close both the memory and store state)
        ingest.pipe.apd.window_for("smoke-agent").closed = True
        conn.execute("UPDATE agent_calibration SET closed=1 WHERE agent_id='smoke-agent'")
        conn.commit()
        alarms = ingest.pipe.evaluate_agent("smoke-agent")
        fired = [a.signal for a in alarms if not a.suppressed]
        print(f"1) OTLP ingest: 12 spans accepted; fired: {fired}")
        assert "error.rate>0.20" in fired

        # 2. seal + verify
        seal = seal_ledger(conn, load_or_create_seed())
        v = verify_seals(conn)
        print(f"2) F2 seal: {seal['seal_id']} verified={v['all_ok']}")
        assert v["all_ok"]

        # 3. console v2 (auth) + weekly report over the same store
        page = FleetConsole(conn).render(
            {"csrf_token": "c", "token": "t", "username": "smoke", "role": "admin"})
        assert "Swarmax Fleet Console" in page \
            and ("error.rate&gt;0.20" in page or "error.rate>0.20" in page) \
            and "Attribution" in page
        report = WeeklyReport(conn).render()
        assert "# Swarmax Weekly Fleet Report" in report
        print("3) console (auth) + weekly report rendered over the same store")

        # 4. metrics endpoint shows anti-replay accounting
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as r:
            m = r.read().decode()
        assert "otlp_accepted_spans_total 12" in m and "ingest_reject_total 0" in m
        print("4) metrics: 12 accepted, 0 rejects — anti-replay clean")
        server.shutdown()
        print("\nSMOKE PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
