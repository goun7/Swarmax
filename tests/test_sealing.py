"""F2 sealing tests: Merkle root, seal/verify, tamper detection, rotation."""
import pytest

from swarmax.db import connect, init_db_with_migrations
from swarmax.evidence import append_evidence, verify_chain
from swarmax.sealing import (
    load_or_create_seed, merkle_root, rotate_key, seal_ledger, verify_seals,
)


def fresh():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return conn


def test_merkle_root_basics():
    import hashlib
    # empty ledger convention
    assert merkle_root([]) == hashlib.sha256(b"GENESIS").hexdigest()
    # single element is itself the root
    h = hashlib.sha256(b"a").hexdigest()
    assert merkle_root([h]) == h
    # two elements: one hash level
    hb2, h2b = bytes.fromhex(h), bytes.fromhex(hashlib.sha256(b"b").hexdigest())
    expected = hashlib.sha256(hb2 + h2b).hexdigest()
    assert merkle_root([h, hashlib.sha256(b"b").hexdigest()]) == expected


def test_seal_and_verify_roundtrip():
    conn = fresh()
    seed = load_or_create_seed()
    for i in range(5):
        append_evidence(conn, "test", {"i": i})
    seal = seal_ledger(conn, seed)
    assert seal["covers_through_seq"] == 5
    result = verify_seals(conn)
    assert result["all_ok"] and result["seals"] == 1


def test_two_seals_over_growth():
    conn = fresh()
    seed = load_or_create_seed()
    for i in range(3):
        append_evidence(conn, "test", {"i": i})
    seal_ledger(conn, seed)
    for i in range(3, 8):
        append_evidence(conn, "test", {"i": i})
    seal_ledger(conn, seed)
    result = verify_seals(conn)
    assert result["all_ok"] and result["seals"] == 2


def test_tamper_breaks_chain_and_seal():
    conn = fresh()
    seed = load_or_create_seed()
    append_evidence(conn, "test", {"i": 1})
    seal_ledger(conn, seed)
    # simulate a retroactive edit bypassing triggers (e.g. direct file manipulation)
    conn.execute("DROP TRIGGER trg_evidence_ledger_no_update")
    conn.execute("UPDATE evidence_ledger SET payload_hash='tampered' WHERE seq=1")
    conn.commit()
    chain_ok, _ = verify_chain(conn)
    assert not chain_ok                      # prev-hash chain broken
    result = verify_seals(conn)
    assert not result["all_ok"]              # Merkle root no longer matches


def test_seal_covers_beyond_ledger_fails():
    conn = fresh()
    seed = load_or_create_seed()
    append_evidence(conn, "test", {"i": 1})
    seal = seal_ledger(conn, seed)
    # remove later entries to simulate a shrunk/rolled-back store
    conn.execute("DROP TRIGGER trg_evidence_ledger_no_delete")
    conn.execute("DELETE FROM evidence_ledger WHERE seq > 0")
    conn.commit()
    result = verify_seals(conn)
    assert not result["all_ok"]


def test_key_rotation():
    conn = fresh()
    old_seed = load_or_create_seed()
    append_evidence(conn, "test", {"i": 1})
    seal_ledger(conn, old_seed)

    from swarmax.sealing import KEY_FILE
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        new_seed = rotate_key(conn, old_seed, path=Path(td) / "seed.hex")
        assert new_seed != old_seed
        # rotation event appended to the ledger
        row = conn.execute(
            "SELECT event_type FROM evidence_ledger ORDER BY seq DESC LIMIT 1").fetchone()
        assert row["event_type"] == "key_rotation"
        # old seal still verifies (its public key is stored with the seal)
        assert verify_seals(conn)["all_ok"]
        # sealing with the new key works and verifies
        append_evidence(conn, "test", {"i": 2})
        seal_ledger(conn, new_seed)
        result = verify_seals(conn)
        assert result["all_ok"] and result["seals"] == 2
