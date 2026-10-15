"""Append-only evidence ledger — paper §12.1.

SHA-256 payload hash chained to the previous entry (prev_hash), stored in the
append-only table (UPDATE/DELETE forbidden by triggers). Ed25519 signatures land in
F2 (§7.1); F0 rows carry an explicit unsigned marker, never a fake signature.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3

UNSIGNED_F0 = b"F0-UNSIGNED-F2-PENDING"
GENESIS = "GENESIS"

# SW-EVID-2: payload'lar tabloda saklanmadigi icin icerik-dogrulama imkansizdir,
# ama her payload_hash gercek bir SHA-256 ozeti (64-kucuk-hex) OLMALIDIR —
# manual/buggy bir INSERT 'sabit-olmayan' gibi bir deger koyup zinciri
# gecersizlestirebilir; eski verify_chain yalnizca prev baglarini sayiyordu.
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


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
    """Recompute the chain; returns (ok, entries_checked).

    Her satirin payload_hash'inin gecerli bir SHA-256 ozeti oldugunu da
    denetler (SW-EVID-2) — icerik-dogrulama payload'lar tabloda olmadigi
    icin mumkun degildir, ama 'gercek-ozet-olmayan' kayit artik kirmizi.
    """
    prev = GENESIS
    checked = 0
    for row in conn.execute(
            "SELECT seq, payload_hash, prev_hash FROM evidence_ledger ORDER BY seq"):
        h = row["payload_hash"] or ""
        if not _DIGEST_RE.match(h):        # SW-EVID-2: gercek-ozet-zorunlu
            return False, checked
        if row["prev_hash"] != prev:
            return False, checked
        prev = h
        checked += 1
    return True, checked
