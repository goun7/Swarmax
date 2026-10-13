"""Audit-trail tests: the evidence lifecycle an auditor relies on.

Covers the chain that answers "prove it" — ingest -> alarm raised -> ledger
anchor -> resolution anchor -> Merkle/Ed25519 seal -> offline archive verify —
against the real pipeline, with every expected value derived from the store.
"""
import gzip
import hashlib
import json
import random
import sqlite3
from datetime import datetime, timedelta

import pytest

from swarmax.coldstore import archive_ledger, verify_manifest_bytes
from swarmax.db import connect, init_db_with_migrations
from swarmax.ed25519 import generate_seed, secret_to_public, verify as ed25519_verify
from swarmax.evidence import append_evidence, verify_chain
from swarmax.fleet import emitter
from swarmax.pipeline import Pipeline
from swarmax.sealing import merkle_root, seal_ledger, verify_seals

BASE = datetime(2026, 9, 1)          # baseline days: Sept 1-6
SCENARIO_DAY = datetime(2026, 9, 7)  # the drift scenario lands here


def make_pipeline() -> Pipeline:
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return Pipeline(conn)


def populated(agent_id: str = "audit-agent") -> Pipeline:
    """A fleet whose drift scenario has fired a real, evidence-anchored alarm."""
    pipe = make_pipeline()
    rng = random.Random(42)
    for d in range(6):
        events, guards = emitter.emit_baseline_day(
            agent_id, BASE + timedelta(days=d), rng)
        pipe.ingest(events, guards)
    events, guards = emitter.emit_s2_tool_drift(
        agent_id, SCENARIO_DAY, random.Random(3))
    pipe.ingest(events, guards)
    pipe.evaluate_agent(agent_id)
    return pipe


def ledger_count(conn) -> int:
    return int(conn.execute("SELECT COUNT(*) AS c FROM evidence_ledger").fetchone()["c"])


def ledger_rows(conn):
    return conn.execute(
        "SELECT seq, payload_hash, prev_hash FROM evidence_ledger ORDER BY seq").fetchall()


def first_open_alarm(conn):
    return conn.execute(
        "SELECT * FROM alarms WHERE status='open' ORDER BY created_at LIMIT 1").fetchone()


# ------------------------------------------------------------------ anchoring

def test_alarm_raise_anchors_a_ledger_entry():
    pipe = populated()
    alarm = first_open_alarm(pipe.conn)
    assert alarm is not None, "drift scenario must raise at least one alarm"

    anchor = pipe.conn.execute(
        "SELECT * FROM evidence_ledger WHERE seq=?", (alarm["evidence_seq"],)).fetchone()
    assert anchor is not None                       # the anchor points at a real row
    assert anchor["event_type"] == f"{alarm['event_type']}_created"
    assert len(anchor["payload_hash"]) == 64        # SHA-256 hex
    assert anchor["prev_hash"] != anchor["payload_hash"]

    tip = pipe.conn.execute("SELECT MAX(seq) AS m FROM evidence_ledger").fetchone()["m"]
    assert 1 <= alarm["evidence_seq"] <= tip        # inside the written chain


def test_resolution_appends_evidence_and_back_links():
    pipe = populated()
    alarm = first_open_alarm(pipe.conn)
    before = ledger_count(pipe.conn)

    assert pipe.resolve_alarm(alarm["alarm_id"], "on-call") == 1

    row = pipe.conn.execute(
        "SELECT evidence_seq, evidence_seq_resolved, status, resolved_by"
        " FROM alarms WHERE alarm_id=?", (alarm["alarm_id"],)).fetchone()
    assert row["status"] == "resolved"
    assert row["resolved_by"] == "on-call"
    assert row["evidence_seq_resolved"] is not None
    # a resolution always comes after the raise it closes
    assert row["evidence_seq_resolved"] > row["evidence_seq"]

    res = pipe.conn.execute(
        "SELECT event_type FROM evidence_ledger WHERE seq=?",
        (row["evidence_seq_resolved"],)).fetchone()
    assert res["event_type"] == "alarm_resolved"
    assert ledger_count(pipe.conn) == before + 1    # exactly one ledger entry added


# ------------------------------------------------------------------ chain

def test_chain_is_continuous_and_covers_every_anchor():
    pipe = populated()
    alarm = first_open_alarm(pipe.conn)
    pipe.resolve_alarm(alarm["alarm_id"], "on-call")

    ok, checked = verify_chain(pipe.conn)
    assert ok
    assert checked == ledger_count(pipe.conn)       # every row walked, none skipped

    rows = ledger_rows(pipe.conn)
    seqs = [int(r["seq"]) for r in rows]
    assert seqs == list(range(1, checked + 1))       # contiguous from 1
    prev = "GENESIS"
    for r in rows:                                   # each row links to its predecessor
        assert r["prev_hash"] == prev
        prev = r["payload_hash"]

    # every alarm anchor (raise + resolve) sits inside the verified chain
    for a in pipe.conn.execute("SELECT * FROM alarms").fetchall():
        assert 1 <= a["evidence_seq"] <= checked
        if a["evidence_seq_resolved"] is not None:
            assert a["evidence_seq"] < a["evidence_seq_resolved"] <= checked


def test_ledger_refuses_retroactive_edits():
    pipe = populated()
    assert ledger_count(pipe.conn) > 0
    with pipe.conn:
        with pytest.raises(sqlite3.IntegrityError) as exc:
            pipe.conn.execute("UPDATE evidence_ledger SET payload_hash='deadbeef' WHERE seq=1")
        assert "append-only" in str(exc.value)
    with pipe.conn:
        with pytest.raises(sqlite3.IntegrityError):
            pipe.conn.execute("DELETE FROM evidence_ledger WHERE seq=1")
    # nothing was written by the aborted statements
    assert ledger_count(pipe.conn) > 0
    assert pipe.conn.execute(
        "SELECT payload_hash FROM evidence_ledger WHERE seq=1").fetchone()[
            "payload_hash"] != "deadbeef"


# ------------------------------------------------------------------ sealing

def fresh_seed() -> bytes:
    return generate_seed()                          # hermetic: never touches keys/


def test_seal_grows_with_the_audit_trail():
    pipe = populated()
    seed = fresh_seed()

    # a seal covers the ledger as it stood *at seal time*; the seal's own
    # ledger event is appended afterwards and is covered by the next seal
    before = ledger_count(pipe.conn)
    first = seal_ledger(pipe.conn, seed)
    assert first["covers_through_seq"] == before
    assert ledger_count(pipe.conn) == before + 1

    alarm = first_open_alarm(pipe.conn)
    pipe.resolve_alarm(alarm["alarm_id"], "on-call")
    after_resolve = ledger_count(pipe.conn)
    second = seal_ledger(pipe.conn, seed)
    assert second["covers_through_seq"] == after_resolve > first["covers_through_seq"]

    result = verify_seals(pipe.conn)
    assert result["all_ok"] and result["seals"] == 2
    # neither seal is reported as countersigned (no TSA was configured)
    assert all(r["countersigned"] is False for r in result["results"])


def test_seal_signature_is_recomputable_offline():
    """An auditor holding only the public key + ledger recomputes root and
    signature over the covered range and reaches the same verdict as verify_seals."""
    pipe = populated()
    seed = fresh_seed()
    seal = seal_ledger(pipe.conn, seed)

    all_hashes = [r["payload_hash"] for r in pipe.conn.execute(
        "SELECT payload_hash FROM evidence_ledger ORDER BY seq")]
    covers = seal["covers_through_seq"]
    covered = all_hashes[:covers]          # the seal's own event is excluded
    assert len(all_hashes) == covers + 1   # ... it sits just outside the range
    root = merkle_root(covered)
    msg = root.encode() + covers.to_bytes(8, "big")

    assert seal["public_key"] == secret_to_public(seed).hex()
    assert ed25519_verify(secret_to_public(seed), msg,
                          bytes.fromhex(seal["signature"]))
    # a root computed over the uncovered tail must NOT verify
    wrong = merkle_root(all_hashes).encode() + covers.to_bytes(8, "big")
    assert not ed25519_verify(secret_to_public(seed), wrong,
                              bytes.fromhex(seal["signature"]))
    assert verify_seals(pipe.conn)["all_ok"]


def test_tamper_breaks_chain_and_every_covering_seal():
    pipe = populated()
    seed = fresh_seed()
    seal_ledger(pipe.conn, seed)
    alarm = first_open_alarm(pipe.conn)
    pipe.resolve_alarm(alarm["alarm_id"], "on-call")
    seal_ledger(pipe.conn, seed)
    assert verify_seals(pipe.conn)["all_ok"]

    # simulate an attacker with direct file access bypassing the triggers
    pipe.conn.execute("DROP TRIGGER trg_evidence_ledger_no_update")
    pipe.conn.execute("UPDATE evidence_ledger SET payload_hash='tampered' WHERE seq=1")
    pipe.conn.commit()

    ok, _ = verify_chain(pipe.conn)
    assert not ok
    result = verify_seals(pipe.conn)
    assert not result["all_ok"]
    assert result["results"] and all(r["ok"] is False for r in result["results"])


def test_rollback_of_a_later_range_breaks_only_the_covering_seal():
    """Removing rows from the middle of the trail invalidates the seals that
    covered them, while earlier seals over the surviving range still verify —
    evidence from before the rollback stays provable."""
    pipe = populated()
    seed = fresh_seed()
    alarm = first_open_alarm(pipe.conn)
    first = seal_ledger(pipe.conn, seed)
    pipe.resolve_alarm(alarm["alarm_id"], "on-call")
    second = seal_ledger(pipe.conn, seed)
    assert verify_seals(pipe.conn)["all_ok"]

    pipe.conn.execute("DROP TRIGGER trg_evidence_ledger_no_delete")
    pipe.conn.execute("DELETE FROM evidence_ledger WHERE event_type='alarm_resolved'")
    pipe.conn.commit()

    result = verify_seals(pipe.conn)
    assert not result["all_ok"]
    by_id = {r["seal_id"]: r for r in result["results"]}
    assert by_id[second["seal_id"]]["ok"] is False
    assert by_id[second["seal_id"]]["reason"] == "root or signature mismatch"
    assert by_id[first["seal_id"]]["ok"] is True


# ------------------------------------------------------------------ fail-closed

def test_resolve_unknown_or_stale_alarm_writes_no_evidence():
    pipe = populated()
    before = ledger_count(pipe.conn)

    assert pipe.resolve_alarm("alm-does-not-exist", "on-call") == 0
    assert ledger_count(pipe.conn) == before         # unknown id -> no evidence

    alarm = first_open_alarm(pipe.conn)
    assert pipe.resolve_alarm(alarm["alarm_id"], "on-call") == 1
    mid = ledger_count(pipe.conn)

    # already resolved: stale re-triage is a no-op, never a second resolution
    assert pipe.resolve_alarm(alarm["alarm_id"], "someone-else") == 0
    assert ledger_count(pipe.conn) == mid

    row = pipe.conn.execute(
        "SELECT status, resolved_by FROM alarms WHERE alarm_id=?",
        (alarm["alarm_id"],)).fetchone()
    assert row["status"] == "resolved" and row["resolved_by"] == "on-call"


def test_baseline_audit_note_is_part_of_the_chain():
    pipe = populated()
    pipe.record_baseline_audit("threshold tuned", {"signal": "error.rate>0.20",
                                                   "from": 0.20, "to": 0.15})
    row = pipe.conn.execute(
        "SELECT event_type FROM evidence_ledger ORDER BY seq DESC LIMIT 1").fetchone()
    assert row["event_type"] == "baseline_audit"
    assert verify_chain(pipe.conn)[0]


# ------------------------------------------------------------------ cold archive

class _MemArchive:
    """In-memory stand-in for an S3-compatible store (put/head/get only)."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(self, name: str, data: bytes) -> str:
        self._objects[name] = data
        return name

    def head(self, name: str) -> bool:
        return name in self._objects

    def get(self, name: str) -> bytes:
        return self._objects[name]


def test_archive_of_audit_trail_verifies_offline():
    pipe = populated()
    seed = fresh_seed()
    alarm = first_open_alarm(pipe.conn)
    pipe.resolve_alarm(alarm["alarm_id"], "on-call")
    seal_ledger(pipe.conn, seed)

    store = _MemArchive()
    report = archive_ledger(pipe.conn, store)
    assert report["rows"] == ledger_count(pipe.conn)
    assert report["last_seq"] == ledger_count(pipe.conn)

    # offline verification: no DB, no private key — manifest + chunks only
    result = verify_manifest_bytes(store.get("manifest.json"), store.get)
    assert result["ok"]
    assert result["rows"] == ledger_count(pipe.conn)
    assert result["last_seq"] == ledger_count(pipe.conn)

    manifest = json.loads(store.get("manifest.json"))
    assert manifest["genesis_prev"] == "GENESIS"
    # every archived row is accounted for exactly once, in seq order
    seen = []
    for chunk in manifest["chunks"]:
        rows = json.loads(gzip.decompress(store.get(chunk["key"])))
        assert [int(r["seq"]) for r in rows] == list(
            range(chunk["first_seq"], chunk["last_seq"] + 1))
        seen.extend(rows)
    assert len(seen) == report["rows"]
    prev = "GENESIS"
    for r in seen:
        assert r["prev_hash"] == prev                # archive chain == store chain
        prev = r["payload_hash"]


def test_archive_verification_detects_chunk_tamper():
    pipe = populated()
    seal_ledger(pipe.conn, fresh_seed())
    store = _MemArchive()
    archive_ledger(pipe.conn, store)
    assert verify_manifest_bytes(store.get("manifest.json"), store.get)["ok"]

    manifest = json.loads(store.get("manifest.json"))
    key = manifest["chunks"][0]["key"]
    store.put(key, gzip.compress(b"[{\"seq\": 1, \"payload_hash\": \"fake\"}]",
                                 mtime=0))
    tainted = verify_manifest_bytes(store.get("manifest.json"), store.get)
    assert not tainted["ok"]
    assert "hash mismatch" in tainted["reason"]


def test_archive_detects_a_row_rewritten_with_updated_manifest():
    """An attacker who rewrites a ledger row AND refreshes the manifest's
    chunk hash still fails: the prev_hash link of the following row no longer
    resolves, and the chain check is independent of the chunk hash."""
    pipe = populated()
    seal_ledger(pipe.conn, fresh_seed())
    store = _MemArchive()
    archive_ledger(pipe.conn, store)
    assert verify_manifest_bytes(store.get("manifest.json"), store.get)["ok"]

    manifest = json.loads(store.get("manifest.json"))
    chunk = manifest["chunks"][0]
    rows = json.loads(gzip.decompress(store.get(chunk["key"])))
    assert len(rows) >= 2
    rows[1]["prev_hash"] = "00" * 32          # silently detached from row 0
    blob = gzip.compress(json.dumps(rows).encode(), mtime=0)
    store.put(chunk["key"], blob)
    chunk["sha256"] = hashlib.sha256(blob).hexdigest()
    store.put("manifest.json", json.dumps(manifest, sort_keys=True).encode())

    result = verify_manifest_bytes(store.get("manifest.json"), store.get)
    assert not result["ok"]
    assert result["reason"] == "chain break at seq 2"
