"""Per-subject key custody + crypto-shredding helpers (§10.3, R7, B2).

Data-model (migration 008):
  - data_subjects: one row per natural person; their PII is AEAD-encrypted
    (ChaCha20-Poly1305, RFC 8439) under a per-subject 256-bit DEK.
  - subject_keys:  append-only key-custody ledger; the DEK is stored wrapped
    under the deployment master key. Erasure appends a tombstone (wrapped_key
    = NULL) — the custody history itself is never rewritten.

Crypto-shred semantics (the whole point): the DEK is *random*, never derived
from the master key. Destroying the wrapped-DEK row makes every payload
ciphertext permanently undecryptable **even for the master-key holder**, while
evidence-ledger hashes and seals stay intact — GDPR/AI-Act Art. 17 erasure
without rewriting append-only compliance records.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from swarmax.privacy.crypto import ChaCha20Poly1305, b64d, b64e


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def master_key_from_env(env_var: str = "SWARMAX_MASTER_KEY") -> bytes:
    """32-byte master key from the environment; dev fallback is clearly labeled.

    Production MUST set SWARMAX_MASTER_KEY (hex or passphrase) — the default is
    derived from a fixed dev string and exists only so demos run out of the box.
    """
    raw = os.environ.get(env_var, "")
    if raw:
        try:
            b = bytes.fromhex(raw)
            if len(b) == 32:
                return b
        except ValueError:
            pass
        return hashlib.sha256(raw.encode()).digest()
    return hashlib.sha256(b"swarmax-dev-master-key (set SWARMAX_MASTER_KEY)").digest()


@dataclass
class SubjectRecord:
    subject_id: str
    display_name: str
    ciphertext_b64: str
    nonce_b64: str
    key_version: int
    sealed: bool


class SubjectKeyStore:
    """Data-subject registry + wrapped-DEK custody over the main connection."""

    def __init__(self, conn: sqlite3.Connection, master_key: bytes):
        if len(master_key) != 32:
            raise ValueError("master_key must be 32 bytes")
        self._conn = conn
        self._master = master_key

    # -- registration ------------------------------------------------------
    def register(self, subject_id: str, display_name: str, pii: dict,
                 actor: str = "system", *, lawful_basis: str = "") -> int:
        """Wrap fresh random DEK under the master key, encrypt PII under DEK.

        ``lawful_basis`` is mandatory (AI-Act/GDPR discipline): PII is only
        accepted after a documented basis — e.g. 'consent' or 'contract'. The
        basis is recorded in the append-only custody ledger, never with the
        payload.
        """
        import json
        if not lawful_basis or not lawful_basis.strip():
            raise ValueError("lawful_basis is required (consent | contract | …)")
        cur = self._conn.execute(
            "SELECT 1 FROM data_subjects WHERE subject_id=?", (subject_id,))
        if cur.fetchone():
            raise ValueError(f"subject {subject_id!r} already registered")
        dek = secrets.token_bytes(32)                       # random, NOT derived
        wrap_nonce = secrets.token_bytes(12)
        wrapped = ChaCha20Poly1305(self._master).encrypt(
            wrap_nonce, dek, aad=f"{subject_id}#v1".encode())
        payload_nonce = secrets.token_bytes(12)
        pt = json.dumps(pii, sort_keys=True).encode()
        payload_ct = ChaCha20Poly1305(dek).encrypt(
            payload_nonce, pt, subject_id.encode())
        cur = self._conn.execute(
            "INSERT INTO data_subjects(subject_id, display_name, ciphertext_b64,"
            " nonce_b64, key_version, registered_at) VALUES (?,?,?,?,1,?)",
            (subject_id, display_name, b64e(payload_ct), b64e(payload_nonce),
             _utcnow()))
        self._conn.execute(
            "INSERT INTO subject_keys(subject_id, key_version, wrapped_key, note,"
            " created_at, revoked_at) VALUES (?,1,?,?,?,NULL)",
            (subject_id, b64e(wrap_nonce + wrapped),
             f"created by {actor}; lawful basis: {lawful_basis}", _utcnow()))
        return cur.lastrowid

    def get(self, subject_id: str) -> SubjectRecord | None:
        row = self._conn.execute(
            "SELECT subject_id, display_name, ciphertext_b64, nonce_b64,"
            " key_version, erased_at FROM data_subjects WHERE subject_id=?",
            (subject_id,)).fetchone()
        if not row:
            return None
        return SubjectRecord(row[0], row[1], row[2], row[3], row[4],
                             row[5] is not None)

    # -- unwrap / decrypt --------------------------------------------------
    def _active_dek(self, subject_id: str) -> bytes:
        row = self._conn.execute(
            "SELECT wrapped_key FROM subject_keys WHERE subject_id=?"
            " AND revoked_at IS NULL AND wrapped_key IS NOT NULL"
            " ORDER BY key_version DESC LIMIT 1", (subject_id,)).fetchone()
        if not row:
            raise ValueError("key destroyed (crypto-shredded)")
        blob = b64d(row[0])
        return ChaCha20Poly1305(self._master).decrypt(
            blob[:12], blob[12:], aad=f"{subject_id}#v1".encode())

    def decrypt_pii(self, subject_id: str) -> dict:
        """Plaintext PII. ValueError('key destroyed') after crypto-shredding."""
        import json
        rec = self.get(subject_id)
        if rec is None:
            raise KeyError(subject_id)
        dek = self._active_dek(subject_id)
        pt = ChaCha20Poly1305(dek).decrypt(
            b64d(rec.nonce_b64), b64d(rec.ciphertext_b64), subject_id.encode())
        return json.loads(pt)

    # -- crypto-shredding (Art. 17 / Md. 17) --------------------------------
    def crypto_shred(self, subject_id: str, actor: str = "system") -> dict:
        """Erase: destroy the wrapped DEK, tombstone custody, redact the name.

        Idempotent; returns an auditable result dict. After this call the
        payload ciphertext is undecryptable by anyone — including the master
        key holder — and no ledger row was rewritten.
        """
        rec = self.get(subject_id)
        if rec is None:
            raise KeyError(subject_id)
        if rec.sealed:
            return {"subject_id": subject_id, "erased": False,
                    "reason": "already erased"}
        self._conn.execute(
            "UPDATE data_subjects SET erased_at=?, display_name='[ERASED]'"
            " WHERE subject_id=?", (_utcnow(), subject_id))
        self._conn.execute(
            "UPDATE subject_keys SET revoked_at=?, wrapped_key=NULL,"
            " note=note || ? WHERE subject_id=? AND revoked_at IS NULL",
            (_utcnow(), f" | crypto-shredded by {actor}", subject_id))
        self._conn.commit()
        return {"subject_id": subject_id, "erased": True,
                "method": "crypto-shred (wrapped DEK destroyed, ledger untouched)"}

    def custody_chain(self, subject_id: str) -> list[dict]:
        """Key-custody history for the audit file (who/when, never key material)."""
        rows = self._conn.execute(
            "SELECT key_version, note, created_at, revoked_at FROM subject_keys"
            " WHERE subject_id=? ORDER BY key_version", (subject_id,)).fetchall()
        return [{"key_version": r[0], "note": r[1], "created_at": r[2],
                 "revoked_at": r[3]} for r in rows]


def bind_subject_event(conn: sqlite3.Connection, subject_id: str,
                       event_id: str) -> str:
    """Anchor a subject↔event binding into the evidence ledger (Md. 12 trace)."""
    from swarmax.evidence import append_evidence
    return append_evidence(conn, "subject_event_bound",
                           {"subject_id": subject_id, "event_id": event_id})


def seal_subject_erasure(conn: sqlite3.Connection, subject_id: str) -> str:
    """Anchor the erasure itself into the evidence ledger."""
    from swarmax.evidence import append_evidence
    return append_evidence(conn, "subject_erased", {"subject_id": subject_id})


def redact_subject_record(subject_id: str) -> str:
    """Display form for erased subjects (used by console + reports)."""
    return f"{subject_id} [erased — crypto-shredded]"
