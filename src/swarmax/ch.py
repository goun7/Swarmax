"""F3 scale — ClickHouse hot tier (§10.1 warm tier, SQLite→ClickHouse step).

The §10.1 tiering contract: hot layer (0–30d) on SQLite for v1, ClickHouse
MergeTree for v2, query < 200 ms. This module ships the v2 client *today*:

  - tiny stdlib HTTP client for the ClickHouse server protocol
    (no vendor SDK; the project stays zero-runtime-dependency, §7 F0);
  - MergeTree DDL matching the paper (ORDER BY (agent_id, ts), TTL 30d);
  - ``mirror_events``: idempotent batched dual-write from SQLite;
  - fail-safe semantics: an unreachable ClickHouse degrades the mirror to a
    logged no-op and SQLite keeps serving — the SPOF stays the store, never
    the scale tier;
  - opt-in via SWARMAX_CH_URL (terminal command `make ch-mirror` in v1).

ClickHouse wire notes: POST of a query string executes it; FORMAT JSONEachRow
returns rows as newline-delimited JSON. INSERTs use JSONEachRow input format.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

DDL = """\
CREATE TABLE IF NOT EXISTS swarmax_events
(
    event_id      String,
    agent_id      String,
    task_id       String,
    session_id    String,
    model_name    String,
    input_tokens  UInt64,
    output_tokens UInt64,
    cost_usd      Float64,
    latency_ms    UInt64,
    error_class   LowCardinality(String),
    status        LowCardinality(String),
    retry_count   UInt32,
    ttft_s        Float64,
    ts            DateTime
)
ENGINE = ReplacingMergeTree(ts)
ORDER BY (agent_id, ts, event_id)
TTL ts + INTERVAL 30 DAY;
-- ReplacingMergeTree + (agent_id, ts, event_id) key: re-mirrored rows collapse
-- on merge, so the inclusive resume window below is idempotent by design.
-- Exact-count queries use SELECT ... FINAL (or argMax(ts) patterns)."""

BATCH = 2000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ch_url() -> str | None:
    """Opt-in endpoint; None disables the mirror entirely (v1 default)."""
    return os.environ.get("SWARMAX_CH_URL")


def query(ch: str, sql: str | bytes, *, post_data: str | None = None,
          timeout: float = 10.0) -> str:
    """Run one statement; returns the raw body. Raises ClickHouseError on
    non-200 so callers never see silent partial writes.

    ``post_data`` REPLACES the body (kept for backwards compatibility);
    to send an INSERT with row data, pass the full wire payload as sql::

        query(ch, "INSERT INTO t FORMAT JSONEachRow", post_data=None)
        # -> use insert_rows() instead: the SQL and the data must share the
    body, which is what the ClickHouse HTTP interface actually expects."""
    payload: bytes | str = sql if isinstance(sql, (bytes, bytearray)) else \
        (post_data or sql).encode()
    req = urllib.request.Request(
        ch.rstrip("/"), data=payload,
        method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8",
                 "X-ClickHouse-User": os.environ.get("SWARMAX_CH_USER", "default"),
                 **({"X-ClickHouse-Key": os.environ["SWARMAX_CH_PASSWORD"]}
                    if os.environ.get("SWARMAX_CH_PASSWORD") else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as exc:
        raise ClickHouseError(exc.read().decode(errors="replace")) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ClickHouseError(f"unreachable: {exc}") from exc


def insert_rows(ch: str, table: str, rows: list[dict],
                *, timeout: float = 30.0) -> None:
    """INSERT rows via the HTTP interface: one body containing the
    ``INSERT INTO <table> FORMAT JSONEachRow`` statement followed by the
    newline-delimited JSON rows (the ClickHouse wire contract)."""
    body = (f"INSERT INTO {table} FORMAT JSONEachRow\n"
            + "\n".join(json.dumps(r) for r in rows)).encode()
    query(ch, body, timeout=timeout)


class ClickHouseError(RuntimeError):
    pass


def ensure_schema(ch: str) -> None:
    query(ch, DDL)


def _rows(conn: sqlite3.Connection, since_ts: str | None, limit: int,
          *, inclusive: bool = False) -> list[dict]:
    sql = ("SELECT event_id, agent_id, task_id, session_id, model_name,"
           " input_tokens, output_tokens, cost_usd, latency_ms, error_class,"
           " status, retry_count, ttft_s, ts FROM agent_task_events")
    args: list = []
    if since_ts:
        sql += " WHERE ts >= ?" if inclusive else " WHERE ts > ?"
        args.append(since_ts)
    sql += " ORDER BY ts LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def mirror_events(conn: sqlite3.Connection, ch: str, *, limit: int = 200_000,
                  progress=lambda done: None) -> dict:
    """Idempotent dual-write: rows from the last mirrored ts (inclusive —
    ReplacingMergeTree collapses re-writes) go to ClickHouse in batches.
    Returns {mirrored, skipped, elapsed_s}."""
    import time
    t0 = time.perf_counter()
    last_ts = None
    try:
        last = query(ch, "SELECT max(ts) FROM swarmax_events FORMAT JSON").strip()
        point = json.loads(last or "{}")
        vals = (point.get("data") or [{}])[0]
        last_ts = vals.get("max(ts)")
    except (ClickHouseError, ValueError, IndexError, KeyError):
        last_ts = None  # empty table or unreachable -> full backfill below
    ensure_schema(ch)
    mirrored = skipped = 0
    while True:
        rows = _rows(conn, last_ts, BATCH, inclusive=True)
        if not rows:
            break
        insert_rows(ch, "swarmax_events", rows)
        mirrored += len(rows)
        last_ts = rows[-1]["ts"]
        progress(mirrored)
        if mirrored >= limit:
            break
    return {"mirrored": mirrored, "skipped": skipped,
            "elapsed_s": round(time.perf_counter() - t0, 3)}


def mirror_events_safe(conn: sqlite3.Connection, *, ch: str | None = None) -> dict:
    """Fail-safe wrapper used by the pipeline: never raises, always logs.
    ClickHouse problems degrade to a no-op; SQLite remains the serving tier."""
    target = ch or ch_url()
    if not target:
        return {"mirrored": 0, "disabled": True}
    try:
        return mirror_events(conn, target)
    except ClickHouseError as exc:
        print(f"swarmax: ClickHouse mirror degraded (store unaffected): {exc}",
              file=sys.stderr)
        return {"mirrored": 0, "degraded": True, "error": str(exc)}
