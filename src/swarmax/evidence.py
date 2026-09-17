"""Append-only evidence ledger — paper §12.1.

SHA-256 payload hash chained to the previous entry (prev_hash), stored in the
append-only table (UPDATE/DELETE forbidden by triggers). Ed25519 signatures land in
F2 (§7.1); F0 rows carry an explicit unsigned marker, never a fake signature.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

UNSIGNED_F0 = b"F0-UNSIGNED-F2-PENDING"
GENESIS = "GENESIS"


def payload_digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def append_evidence(conn: sqlite3.Connection, event_type: str, payload: dict) -> int:
    """Append one hash-chained entry; returns its seq. Must run inside a transaction
    to keep the chain linear under concurrency."""
    cur = conn.execute(
        "SELECT payload_hash FROM evidence_ledger ORDER BY seq DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row["payload_hash"] if row else GENESIS
    payload_hash = payload_digest(payload)
    cur = conn.execute(
        "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash, ed25519_sig) "
        "VALUES (?, ?, ?, ?)",
        (event_type, payload_hash, prev_hash, UNSIGNED_F0),
    )
    return int(cur.lastrowid)


def verify_chain(conn: sqlite3.Connection) -> tuple[bool, int]:
    """Recompute the chain; returns (ok, entries_checked)."""
    prev = GENESIS
    checked = 0
    for row in conn.execute(
            "SELECT seq, payload_hash, prev_hash FROM evidence_ledger ORDER BY seq"):
        if row["prev_hash"] != prev:
            return False, checked
        prev = row["payload_hash"]
        checked += 1
    return True, checked
