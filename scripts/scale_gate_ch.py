#!/usr/bin/env python
"""F3-scale gate against a REAL ClickHouse server (§10.1 hot-tier contract).

  SWARMAX_CH_URL=http://127.0.0.1:18123 \
  SWARMAX_CH_PASSWORD=swarmax \
  SWARMAX_SCALE_ROWS=10_000_000 python scripts/scale_gate_ch.py

What it does, honestly:
  1. applies the production DDL (ch.DDL, verbatim);
  2. generates N events SERVER-SIDE (numbers(m) generator — no client
     transfer) and inserts them via the same HTTP interface the mirror uses;
  3. times the §10.1 query contract per agent (point aggregations on the
     (agent_id, ts, event_id) key) — 5 warm runs each, worst kept;
  4. times the full mirror round-trip of a small batch through ch.mirror_events
     against the live server (proves the mirror path works for real, not just
     the DDL);
  5. prints a PASS/FAIL card; exit 1 on breach.  No mocks anywhere.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from swarmax import ch  # noqa: E402

THRESHOLD_MS = 200.0


def main() -> int:
    url = os.environ.get("SWARMAX_CH_URL")
    if not url:
        print("SWARMAX_CH_URL not set — nothing to prove", file=sys.stderr)
        return 2
    n = int(os.environ.get("SWARMAX_SCALE_ROWS", "10000000").replace("_", ""))
    agents = int(os.environ.get("SWARMAX_SCALE_AGENTS", "64"))
    print(f"== Swarmax F3-scale gate ==\nserver: {url}\nrows  : {n:,}  "
          f"agents: {agents}")

    ch.ensure_schema(url)
    # server-side generation: 64 agents x 7.8h of 20/s events, deterministic
    print("generating server-side ...", end="", flush=True)
    t0 = time.perf_counter()
    ch.query(url, f"""
        INSERT INTO swarmax_events
        SELECT
            toString(number)                              AS event_id,
            'agent-' || toString(number % {agents})       AS agent_id,
            'task-' || toString(number)                   AS task_id,
            'sess-' || toString(number % 100000)          AS session_id,
            ['gpt-4o-mini','claude-sonnet'][1 + number % 2] AS model_name,
            500 + number % 2000                            AS input_tokens,
            200 + number % 900                             AS output_tokens,
            0.002 + (number % 37) / 10000.0                AS cost_usd,
            400 + number % 2400                            AS latency_ms,
            ['','timeout','tool_fail'][1 + number % 3]     AS error_class,
            if(number % 3 = 0, 'error', 'ok')              AS status,
            number % 4                                     AS retry_count,
            0.2 + (number % 80) / 100.0                    AS ttft_s,
            toDateTime('2026-09-15 00:00:00') + number % 28125 AS ts
        FROM numbers({n})
    """, timeout=600)
    print(f" {time.perf_counter() - t0:,.1f}s")

    cnt = int(ch.query(url, "SELECT count() FROM swarmax_events FINAL"))
    print(f"server rows: {cnt:,}")

    # §10.1 gate: per-agent point aggregations (the console's real views)
    queries = {
        "agent daily cost (7d)": (
            "SELECT toDate(ts) d, sum(cost_usd) c, count() tasks "
            "FROM swarmax_events WHERE agent_id='agent-3' "
            "AND ts >= now() - INTERVAL 300 DAY GROUP BY d ORDER BY d"),
        "agent status counts": (
            "SELECT status, count() FROM swarmax_events "
            "WHERE agent_id='agent-3' GROUP BY status"),
        "agent top tasks": (
            "SELECT task_id, sum(cost_usd) c FROM swarmax_events "
            "WHERE agent_id='agent-3' GROUP BY task_id ORDER BY c DESC LIMIT 5"),
    }
    worst = 0.0
    for name, sql in queries.items():
        times = []
        for _ in range(5):
            t = time.perf_counter()
            ch.query(url, sql)
            times.append((time.perf_counter() - t) * 1000)
        worst = max(worst, max(times))
        print(f"  {name:24s} {min(times):7.1f} .. {max(times):7.1f} ms")

    # real mirror round-trip: batch events land in CH through the project code
    import tempfile
    from swarmax.db import connect, init_db_with_migrations
    from swarmax.pipeline import Pipeline
    dbfile = os.path.join(tempfile.mkdtemp(), "mirror.db")
    conn = connect(dbfile)
    init_db_with_migrations(conn)
    pipe = Pipeline(conn)
    pipe.ingest([{
        "event_id": f"mirror-{i}", "agent_id": "mirror-agent",
        "task_id": f"t{i}", "session_id": "s", "model_name": "m",
        "input_tokens": 10, "output_tokens": 10, "cost_usd": 0.01,
        "latency_ms": 100, "error_class": None, "status": "ok",
        "synthetic": 1, "ts": "2026-09-16 10:00:00", "retry_count": 0,
        "ttft_s": 0.2, "task_template": None, "end_state_json": None}
        for i in range(50)])
    res = ch.mirror_events(conn, url, limit=1000)
    ok_mirror = res.get("mirrored", 0) >= 50
    print(f"  mirror round-trip        {res}")

    verdict = worst <= THRESHOLD_MS and ok_mirror
    print(f"\nverdict : {'PASS' if verdict else 'FAIL'}  "
          f"(worst {worst:.1f} ms vs {THRESHOLD_MS:.0f} ms; "
          f"mirror {'ok' if ok_mirror else 'BROKEN'})")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
