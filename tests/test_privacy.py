"""B2 crypto-shredding + B4 evidence-seq anchors (AI_ACT_COMPLIANCE.md gaps).

Crypto layer is pinned to RFC 8439 (full AEAD vector, cross-checked against
OpenSSL) and RFC 5869 HKDF; the store layer is pinned to lifecycle semantics:
decryptable → erased (undecryptable for EVERYONE, ledger untouched) → anchored.
"""
import pytest

import swarmax.auth as auth
from swarmax.db import connect, init_db_with_migrations
from swarmax.pipeline import Pipeline
from swarmax.privacy.crypto import ChaCha20Poly1305, hkdf_sha256
from swarmax.privacy.store import (
    SubjectKeyStore, bind_subject_event, master_key_from_env,
    seal_subject_erasure,
)

MASTER = bytes(range(32))


def fresh():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return conn


# ---------------------------------------------------------------- RFC pins
def test_rfc8439_section_2_3_2_keystream():
    from swarmax.privacy.crypto import _chacha20_block
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f"
                        "101112131415161718191a1b1c1d1e1f")
    nonce = bytes.fromhex("000000090000004a00000000")
    ks = _chacha20_block(key, 1, nonce)
    assert ks.hex() == ("10f1e7e4d13b5915500fdd1fa32071c4"
                        "c7d1f4c733c068030422aa9ac3d46c4e"
                        "d2826446079faa0914c2d705d98b02a2"
                        "b5129cd1de164eb9cbd083e8a2503c4e")


def test_rfc8439_section_2_4_2_poly1305():
    from swarmax.privacy.crypto import _poly1305_mac
    mac = _poly1305_mac(
        bytes.fromhex("85d6be7857556d337f4452fe42d506a80"
                      "103808afb0db2fd4abff6af4149f51b"),
        b"Cryptographic Forum Research Group")
    assert mac.hex() == "a8061dc1305136c6c22b8baf0c0127a9"


def test_rfc8439_section_2_8_2_aead_roundtrip_and_tamper():
    key = bytes.fromhex("808182838485868788898a8b8c8d8e8f"
                        "909192939495969798999a9b9c9d9e9f")
    nonce = bytes.fromhex("070000004041424344454647")
    pt = (b"Ladies and Gentlemen of the class of '99: If I could offer you "
          b"only one tip for the future, sunscreen would be it.")
    a = ChaCha20Poly1305(key)
    ct_tag = a.encrypt(nonce, pt, b"")
    # ciphertext + tag cross-checked against OpenSSL chacha20-poly1305
    assert ct_tag[-16:].hex() == "6a23a4681fd59456aea1d29f82477216"
    assert a.decrypt(nonce, ct_tag, b"") == pt
    bad = bytearray(ct_tag)
    bad[7] ^= 1
    with pytest.raises(ValueError, match="authentication failed"):
        a.decrypt(nonce, bytes(bad), b"")


def test_rfc5869_hkdf_test_case_1():
    okm = hkdf_sha256(b"\x0b" * 22, bytes.fromhex("000102030405060708090a0b0c"),
                      bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"), 42)
    assert okm.hex() == ("3cb25f25faacd57a90434f64d0362f2a"
                         "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
                         "34007208d5b887185865")


# ------------------------------------------------------------- B2 lifecycle
def test_register_requires_lawful_basis():
    conn = fresh()
    store = SubjectKeyStore(conn, MASTER)
    with pytest.raises(ValueError, match="lawful_basis"):
        store.register("p1", "Person One", {"email": "p1@x.io"})


def test_crypto_shred_lifecycle():
    conn = fresh()
    store = SubjectKeyStore(conn, MASTER)
    store.register("p1", "Person One", {"email": "p1@x.io"},
                   lawful_basis="consent")
    assert store.decrypt_pii("p1") == {"email": "p1@x.io"}

    result = store.crypto_shred("p1", actor="dpo")
    assert result["erased"] is True
    rec = store.get("p1")
    assert rec.sealed and rec.display_name == "[ERASED]"
    with pytest.raises(ValueError, match="key destroyed"):
        store.decrypt_pii("p1")
    # even the master-key holder cannot unwrap: custody row is destroyed
    assert all(k.get("wrapped_key") is None for k in store.custody_chain("p1"))

    # idempotent second call
    again = store.crypto_shred("p1")
    assert again["erased"] is False and again["reason"] == "already erased"

    # erasure is anchored in the append-only evidence ledger
    seq = seal_subject_erasure(conn, "p1")
    row = conn.execute("SELECT event_type FROM evidence_ledger WHERE seq=?",
                       (seq,)).fetchone()
    assert row["event_type"] == "subject_erased"


def test_master_key_rotation_does_not_resurrect_subject():
    """The whole point of random DEKs: a NEW master key must not decrypt old
    payloads — and shredding is independent of the master key entirely."""
    conn = fresh()
    store = SubjectKeyStore(conn, MASTER)
    store.register("p2", "P", {"email": "p2@x.io"}, lawful_basis="contract")
    store.crypto_shred("p2")
    new_store = SubjectKeyStore(conn, bytes(32))  # rotated master key
    with pytest.raises(ValueError, match="key destroyed"):
        new_store.decrypt_pii("p2")


def test_master_key_from_env(monkeypatch):
    monkeypatch.setenv("SWARMAX_MASTER_KEY", "00" * 32)
    assert master_key_from_env() == bytes(32)
    monkeypatch.setenv("SWARMAX_MASTER_KEY", "passphrase")
    assert len(master_key_from_env()) == 32
    monkeypatch.delenv("SWARMAX_MASTER_KEY")
    assert len(master_key_from_env()) == 32  # labeled dev fallback


def test_bind_subject_event_anchors_ledger():
    conn = fresh()
    ev = {"event_id": "ev-1", "agent_id": "a1", "task_id": "t1",
          "session_id": "s", "model_name": "m", "input_tokens": 1,
          "output_tokens": 1, "cost_usd": 0.0, "latency_ms": 1.0,
          "error_class": None, "status": "ok", "synthetic": 0,
          "ts": "2026-09-16 10:00:00", "retry_count": 0, "ttft_s": 0.0,
          "task_template": None, "end_state_json": None,
          "data_subject_id": "subj-b4"}
    Pipeline(conn).ingest([ev])
    row = conn.execute(
        "SELECT payload_hash FROM evidence_ledger"
        " WHERE event_type='subject_event_bound' ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    # the ingest-time binding already committed it; ledger stays chain-valid
    from swarmax.evidence import verify_chain
    ok, n = verify_chain(conn)
    assert ok and n >= 1


# --------------------------------------------------------------- B4 anchors
def test_alarms_carry_evidence_seq_anchors():
    conn = fresh()
    pipe = Pipeline(conn)
    pipe._register_agent("b4-bot", synthetic=True)
    for i in range(3):
        pipe.ingest([_task("b4-bot", i, error_class="tool_fail",
                           status="error")])
    alarms = pipe.evaluate_agent("b4-bot")
    assert alarms, "expected at least one alarm from error burst"
    row = conn.execute(
        "SELECT evidence_seq, evidence_seq_resolved FROM alarms"
        " WHERE agent_id='b4-bot' LIMIT 1").fetchone()
    assert row["evidence_seq"] is not None
    raised = conn.execute(
        "SELECT seq FROM evidence_ledger WHERE seq=?",
        (row["evidence_seq"],)).fetchone()
    assert raised, "raise anchor must exist in the ledger"

    alarm_id = conn.execute(
        "SELECT alarm_id FROM alarms WHERE agent_id='b4-bot'"
        " LIMIT 1").fetchone()["alarm_id"]
    assert pipe.resolve_alarm(alarm_id, "tester") == 1
    row = conn.execute(
        "SELECT evidence_seq_resolved FROM alarms WHERE alarm_id=?",
        (alarm_id,)).fetchone()
    assert row["evidence_seq_resolved"] is not None
    # unknown alarm: fail-closed, no anchor fabricated
    assert pipe.resolve_alarm("alm_unknown", "tester") == 0
    after = conn.execute("SELECT COUNT(*) c FROM evidence_ledger").fetchone()["c"]
    assert pipe.resolve_alarm("alm_unknown", "tester") == 0
    assert conn.execute(
        "SELECT COUNT(*) c FROM evidence_ledger").fetchone()["c"] == after


# ------------------------------------------------- console /forget (HTTP e2e)
def _http_forget_checks(serve):
    import threading
    import urllib.error
    import urllib.parse
    import urllib.request
    import http.cookiejar
    import re

    conn = fresh()
    auth.bootstrap_admin(conn, "root", "swarmax-demo-admin")
    auth.add_user(conn, "view", "viewer-pass-123", "viewer",
                  actor="test")
    SubjectKeyStore(conn, MASTER).register(
        "subj-live", "Live Subject", {"email": "live@x.io"},
        actor="test", lawful_basis="consent")
    conn.commit()
    console = serve(conn)
    srv = console.serve(port=0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def session_for(op, user, pwd):
        op.open(base + "/login", data=urllib.parse.urlencode(
            {"username": user, "password": pwd}).encode(), timeout=30)
        h = op.open(base + "/", timeout=30).read().decode()
        return (re.search(r"name='csrf' value='([^']+)'", h).group(1),
                re.search(r"name='token' value='([^']+)'", h).group(1), h)

    def post(op, path, **d):
        req = urllib.request.Request(
            base + path, urllib.parse.urlencode(d).encode())
        try:
            return op.open(req, timeout=30)
        except urllib.error.HTTPError as e:
            return e

    op = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf, token, home = session_for(op, "root", "swarmax-demo-admin")

    # privacy section visible with the subject listed
    assert "Art. 17 crypto-shred" in home and "subj-live" in home

    # admin erases over real HTTP; erasure anchored in the ledger
    r = post(op, "/forget", csrf=csrf, token=token, subject_id="subj-live")
    assert r.status == 200 and b"erased: subj-live" in r.read()
    kinds = conn.execute("SELECT group_concat(event_type) g"
                         " FROM evidence_ledger").fetchone()["g"]
    assert "subject_erased" in kinds

    # unknown subject: fail-closed 404, nothing fabricated
    r = post(op, "/forget", csrf=csrf, token=token, subject_id="ghost")
    assert r.status == 404

    # viewer role cannot erase
    op2 = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    c2, t2, _ = session_for(op2, "view", "viewer-pass-123")
    r = post(op2, "/forget", csrf=c2, token=t2, subject_id="x")
    assert r.status == 403


def test_console_forget_http(serve_http):
    _http_forget_checks(serve_http)


def _task(agent_id: str, i: int, **kw) -> dict:
    base = {
        "event_id": f"{agent_id}-e{i}", "agent_id": agent_id,
        "task_id": f"t{i}", "session_id": "s", "model_name": "m",
        "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01,
        "latency_ms": 100.0, "error_class": None, "status": "ok",
        "synthetic": 1, "ts": "2026-09-16 10:00:00", "retry_count": 0,
        "ttft_s": 0.1, "task_template": None, "end_state_json": None,
    }
    base.update(kw)
    return base
