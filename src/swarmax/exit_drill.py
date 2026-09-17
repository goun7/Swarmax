"""Quarterly exit drill — paper §3 (çıkış tatbikatı): prove tenant data leaves
complete, rebuildable and verifiable.

Phases (each timed):
  1. EXPORT    dump every user table to a portable JSON bundle
  2. REBUILD   fresh in-memory store, apply schema+migrations, reload the bundle
  3. VERIFY    hash chain + seals verify on the rebuilt store; row counts match

The drill writes nothing to the source store (read-only export).
"""
from __future__ import annotations

import json
import sqlite3
import time

from .db import connect, init_db_with_migrations, current_version
from .evidence import verify_chain
from .sealing import verify_seals

# user tables in dependency-tolerant order (no FKs across these beyond agents)
USER_TABLES = (
    "fleet_agents", "agent_task_events", "guard_events", "agent_drift_baselines",
    "hitl_escalations", "alarms", "evidence_ledger", "evidence_seals",
)


def _encode_value(v: object) -> object:
    """JSON-safe encoding: BLOBs become {"__bytes__": hex} markers."""
    if isinstance(v, bytes):
        return {"__bytes__": v.hex()}
    return v


def _decode_value(v: object) -> object:
    if isinstance(v, dict) and set(v) == {"__bytes__"}:
        return bytes.fromhex(v["__bytes__"])
    return v


def export_bundle(conn: sqlite3.Connection) -> dict:
    """Read-only, JSON-portable dump of all user tables + schema version."""
    bundle: dict = {"schema_version": current_version(conn), "tables": {}}
    for table in USER_TABLES:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
        bundle["tables"][table] = [
            {k: _encode_value(v) for k, v in dict(r).items()} for r in rows]
    return bundle


def rebuild_from_bundle(bundle: dict, path: str = ":memory:") -> sqlite3.Connection:
    conn = connect(path)
    init_db_with_migrations(conn)
    for table, rows in bundle["tables"].items():
        if not rows:
            continue
        cols = list(rows[0])
        placeholders = ",".join("?" for _ in cols)
        conn.executemany(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",  # noqa: S608
            [tuple(_decode_value(r[c]) for c in cols) for r in rows])
    conn.commit()
    return conn


def run_exit_drill(conn: sqlite3.Connection) -> dict:
    report: dict = {"phases": {}, "ok": True}

    t0 = time.perf_counter()
    bundle = export_bundle(conn)
    report["phases"]["export"] = {
        "s": time.perf_counter() - t0,
        "rows": {t: len(r) for t, r in bundle["tables"].items()},
    }

    t0 = time.perf_counter()
    rebuilt = rebuild_from_bundle(bundle)
    report["phases"]["rebuild"] = {"s": time.perf_counter() - t0}

    t0 = time.perf_counter()
    chain_ok, chain_checked = verify_chain(rebuilt)
    seals = verify_seals(rebuilt)
    counts_ok = all(
        bundle["tables"][t] is not None
        and len(bundle["tables"][t]) == rebuilt.execute(
            f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]  # noqa: S608
        for t in USER_TABLES)
    report["phases"]["verify"] = {
        "s": time.perf_counter() - t0,
        "chain_ok": chain_ok, "chain_entries": chain_checked,
        "seals_ok": seals["all_ok"], "seals": seals["seals"],
        "row_counts_match": counts_ok,
    }
    report["ok"] = chain_ok and seals["all_ok"] and counts_ok
    report["total_s"] = sum(p["s"] for p in report["phases"].values())
    return report


def format_drill_report(report: dict) -> str:
    lines = ["Swarmax quarterly exit drill",
             f"  result: {'PASS' if report['ok'] else 'FAIL'}"
             f" (total {report['total_s']:.2f}s)"]
    e = report["phases"]["export"]
    lines.append(f"  export:  {sum(e['rows'].values())} rows across"
                 f" {len(e['rows'])} tables in {e['s']:.2f}s")
    lines.append(f"  rebuild: {report['phases']['rebuild']['s']:.2f}s")
    v = report["phases"]["verify"]
    lines.append(f"  verify:  chain_ok={v['chain_ok']} ({v['chain_entries']} entries),"
                 f" seals_ok={v['seals_ok']} ({v['seals']} seals),"
                 f" counts_match={v['row_counts_match']} in {v['s']:.2f}s")
    return "\n".join(lines)
