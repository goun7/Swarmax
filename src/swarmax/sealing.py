"""F2 evidence sealing — Ed25519 + Merkle root over the hash-chained ledger
(paper §12.1, §14 R1; fixes the F0 UNSIGNED-F2-PENDING marker).

A seal commits to:
  - the Merkle root over every ``evidence_ledger.payload_hash`` up to a seq, and
  - ``covers_through_seq`` itself,
signed with the operator's Ed25519 key. ``verify_seal`` recomputes the root from the
database and checks the signature, so any retroactive ledger edit breaks both the
hash chain (append-only triggers already forbid it) and the seal.

Key custody (paper §14): the seed lives in SWX_EVIDENCE_SEED or a local file
(``keys/evidence_seed.hex``); rotations append a rotation event to the ledger.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from pathlib import Path

from .ed25519 import generate_seed, secret_to_public, sign, verify
from .evidence import append_evidence
from .tsa import TSAError, request_timestamp, tsa_url_from_env, verify_token_binding

ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = ROOT / "keys" / "evidence_seed.hex"


def load_or_create_seed(path: Path | None = None) -> bytes:
    p = path or KEY_FILE
    if p.exists():
        return bytes.fromhex(p.read_text().strip())
    seed = generate_seed()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(seed.hex())
    return seed


def merkle_root(hashes: list[str]) -> str:
    """Merkle root over payload hashes (duplicate-last on odd levels; GENESIS when empty)."""
    if not hashes:
        return hashlib.sha256(b"GENESIS").hexdigest()
    level = [bytes.fromhex(h) for h in hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex()


def seal_ledger(conn: sqlite3.Connection, seed: bytes,
                *, event_type: str = "ledger_seal",
                tsa_url: str | None = None) -> dict:
    """Seal the current ledger state; returns the seal record (also stored).

    T3.1 (§5.3 Hat 2): when ``tsa_url`` is given (or SWARMAX_TSA_URL is set),
    the seal message is countersigned by an RFC 3161 TSA and the raw token
    is stored on the seal row.  A TSA outage raises TSAError — an operator
    who explicitly enabled countersigning must never get a silent skip."""
    rows = conn.execute(
        "SELECT seq, payload_hash FROM evidence_ledger ORDER BY seq").fetchall()
    if not rows:
        raise ValueError("nothing to seal: ledger is empty")
    covers = int(rows[-1]["seq"])
    hashes = [r["payload_hash"] for r in rows]
    root = merkle_root(hashes)
    msg = root.encode() + covers.to_bytes(8, "big")
    sig = sign(seed, msg)
    public = secret_to_public(seed)
    seal_id = f"seal_{covers:08d}_{int(time.time())}"
    conn.execute(
        "INSERT INTO evidence_seals (seal_id, root_hash, covers_through_seq,"
        " public_key, ed25519_sig) VALUES (?, ?, ?, ?, ?)",
        (seal_id, root, covers, public, sig))

    tsa_url = tsa_url or tsa_url_from_env()
    countersigned = False
    if tsa_url:
        try:
            token = request_timestamp(msg, url=tsa_url)
            if not verify_token_binding(token, msg):
                raise TSAError("TSA token does not bind to the seal message")
        except TSAError:
            conn.rollback()   # fail closed: no seal row, no anchor, no residue
            raise
        conn.execute("UPDATE evidence_seals SET tsa_token=? WHERE seal_id=?",
                     (token, seal_id))
        countersigned = True

    append_evidence(conn, event_type, {
        "seal_id": seal_id, "root": root, "covers_through_seq": covers,
        "countersigned": countersigned})
    conn.commit()
    return {"seal_id": seal_id, "root_hash": root, "covers_through_seq": covers,
            "public_key": public.hex(), "signature": sig.hex(),
            "countersigned": countersigned}


def verify_seals(conn: sqlite3.Connection) -> dict:
    """Verify every stored seal against the current ledger content. Corrupt
    (non-hex) payload hashes count as verification failure, never an exception.

    T3.1: seals carrying a ``tsa_token`` get an additional binding check —
    the token must contain the SHA-256 imprint of this seal's message
    (root || covers).  A present-but-unbound token fails the seal; absence
    of a token is reported, not failed (pre-T3.1 seals stay valid)."""
    rows = conn.execute(
        "SELECT seal_id, root_hash, covers_through_seq, public_key, ed25519_sig,"
        " tsa_token FROM evidence_seals ORDER BY covers_through_seq").fetchall()
    all_hashes = [r["payload_hash"] for r in conn.execute(
        "SELECT payload_hash FROM evidence_ledger ORDER BY seq")]
    results = []
    for r in rows:
        covers = int(r["covers_through_seq"])
        if covers > len(all_hashes):
            results.append({"seal_id": r["seal_id"], "ok": False,
                            "reason": "covers seq beyond ledger"})
            continue
        try:
            covered = [bytes.fromhex(h) for h in all_hashes[:covers]]
        except ValueError:
            results.append({"seal_id": r["seal_id"], "ok": False,
                            "reason": "corrupt payload hash in covered range"})
            continue
        root = merkle_root([b.hex() for b in covered])
        msg = root.encode() + covers.to_bytes(8, "big")
        ok = verify(bytes(r["public_key"]), msg, bytes(r["ed25519_sig"])) \
            and root == r["root_hash"]
        countersign_ok: bool | None = None
        if ok and r["tsa_token"] is not None:
            countersign_ok = verify_token_binding(bytes(r["tsa_token"]), msg)
            ok = countersign_ok
        results.append({"seal_id": r["seal_id"], "ok": ok,
                        "countersigned": r["tsa_token"] is not None,
                        "countersign_ok": countersign_ok,
                        "reason": None if ok else
                        ("countersign binding failed" if countersign_ok is False
                         else "root or signature mismatch")})
    return {"seals": len(results), "all_ok": all(x["ok"] for x in results),
            "results": results}


def rotate_key(conn: sqlite3.Connection, old_seed: bytes, *, path: Path | None = None) -> bytes:
    """Operator-approved key rotation (§14): new seed, rotation event appended,
    key file atomically replaced. Old seals stay verifiable (public key stored)."""
    new_seed = generate_seed()
    append_evidence(conn, "key_rotation", {
        "old_public": secret_to_public(old_seed).hex(),
        "new_public": secret_to_public(new_seed).hex(),
    })
    p = path or KEY_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".hex.tmp")
    tmp.write_text(new_seed.hex())
    os.replace(tmp, p)
    return new_seed
