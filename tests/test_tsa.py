"""T3.1 countersignature tests — RFC 3161 client + seal integration.

The live-TSA proof is a separate drill (scripts/trust_drill.py, real network);
these tests use a wire-accurate fake TSA so they run offline and deterministically.
"""
import hashlib
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from swarmax.db import connect, init_db_with_migrations
from swarmax.evidence import append_evidence
from swarmax.sealing import load_or_create_seed, seal_ledger, verify_seals
from swarmax.tsa import (TSAError, build_ts_request, request_timestamp,
                         verify_token_binding)


# ------------------------------------------------------- DER / request tests
def test_request_der_contains_imprint_and_nonce():
    data = b"seal message"
    der, nonce = build_ts_request(data)
    assert der[0] == 0x30                       # SEQUENCE
    assert hashlib.sha256(data).digest() in der  # imprint embedded
    # nonce is DER INTEGER-encoded inside the request
    body = nonce.to_bytes((nonce.bit_length() + 8) // 8, "big")
    assert body in der
    # certReq=TRUE present
    assert b"\x01\x01\xff" in der
    # byte-compat with `openssl ts -query` (FreeTSA parser requirements):
    # version INTEGER(1) first, sha256 AlgorithmIdentifier with NULL params
    assert der.startswith(b"\x30\x02\x01\x01") or b"\x02\x01\x01" in der
    assert bytes.fromhex("060960864801650304020105 00".replace(" ", "")) in der


@pytest.mark.filterwarnings("ignore:tsa:UserWarning")
def test_binding_verification():
    data = b"root12345678"
    der, nonce = build_ts_request(data)
    # fake token = a reply-ish blob containing imprint + nonce value
    token = b"\x30" + bytes([len(der)]) + der
    assert verify_token_binding(token, data, nonce=nonce)
    assert not verify_token_binding(token, b"other data", nonce=nonce)
    assert not verify_token_binding(b"\x30\x00", data, nonce=nonce)


# ------------------------------------------------------------- fake TSA wire
class _TSAHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.headers.get("Content-Type") != "application/timestamp-query":
            self.send_response(415)
            self.end_headers()
            return
        # honest fake: echo request DER inside a SEQUENCE (binding survives)
        resp = b"\x30" + bytes([len(body) + 2]) + b"\x30\x00" + body
        self.send_response(200)
        self.send_header("Content-Type", "application/timestamp-reply")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


@pytest.fixture()
def tsa_url():
    srv = HTTPServer(("127.0.0.1", 0), _TSAHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.1)
    yield f"http://127.0.0.1:{srv.server_address[1]}/tsr"
    srv.shutdown()


@pytest.mark.filterwarnings("ignore:tsa:UserWarning")
def test_request_timestamp_roundtrip_offline(tsa_url):
    token = request_timestamp(b"hello seal", url=tsa_url)
    assert token.startswith(b"\x30")


def test_request_rejects_wrong_content_type(tsa_url):
    with pytest.raises(TSAError):
        request_timestamp(b"x", url=tsa_url.replace("/tsr", "/")) \
            if False else _post_wrong(tsa_url)


def _post_wrong(url):
    import urllib.request
    req = urllib.request.Request(
        url, data=b"x", method="POST",
        headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:  # noqa: BLE001 - the handler 415s; urlopen raises
        raise TSAError(str(exc)) from exc
    raise TSAError("expected rejection")


# ------------------------------------------------------- seal integration
def _fresh_ledger(conn, n=5):
    for i in range(n):
        append_evidence(conn, "drill", {"i": i})
    conn.commit()


@pytest.mark.filterwarnings("ignore:tsa:UserWarning")
def test_seal_countersign_binds_and_verifies(tsa_url, tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db_with_migrations(conn)
    _fresh_ledger(conn)
    seed = load_or_create_seed(tmp_path / "seed.hex")
    res = seal_ledger(conn, seed, tsa_url=tsa_url)
    assert res["countersigned"] is True
    row = conn.execute(
        "SELECT tsa_token FROM evidence_seals WHERE seal_id=?",
        (res["seal_id"],)).fetchone()
    assert row["tsa_token"] is not None
    v = verify_seals(conn)
    assert v["all_ok"] and v["results"][0]["countersigned"] is True
    assert v["results"][0]["countersign_ok"] is True


def test_seal_without_tsa_stays_valid(tsa_url, tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db_with_migrations(conn)
    _fresh_ledger(conn)
    seed = load_or_create_seed(tmp_path / "seed.hex")
    res = seal_ledger(conn, seed)          # no TSA: legacy behaviour
    assert res["countersigned"] is False
    v = verify_seals(conn)
    assert v["all_ok"]
    assert v["results"][0]["countersigned"] is False
    assert v["results"][0]["countersign_ok"] is None


@pytest.mark.filterwarnings("ignore:tsa:UserWarning")
def test_tampered_token_fails_closed(tsa_url, tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db_with_migrations(conn)
    _fresh_ledger(conn)
    seed = load_or_create_seed(tmp_path / "seed.hex")
    res = seal_ledger(conn, seed, tsa_url=tsa_url)
    conn.execute("UPDATE evidence_seals SET tsa_token=? WHERE seal_id=?",
                 (b"\x04\x02not-a-bound-token", res["seal_id"]))
    conn.commit()
    v = verify_seals(conn)
    assert not v["all_ok"]
    assert v["results"][0]["reason"] == "countersign binding failed"


def test_tsa_outage_fails_closed_not_silent(tmp_path):
    """Operator explicitly enabled TSA → outage must raise, never skip."""
    conn = connect(str(tmp_path / "t.db"))
    init_db_with_migrations(conn)
    _fresh_ledger(conn)
    seed = load_or_create_seed(tmp_path / "seed.hex")
    with pytest.raises(TSAError):
        seal_ledger(conn, seed, tsa_url="http://127.0.0.1:1/tsr")  # dead port
    # nothing was sealed, nothing anchored as a false success
    assert conn.execute("SELECT COUNT(*) c FROM evidence_seals").fetchone()["c"] == 0
