"""B1 cold tier: SigV4 client ↔ fake-S3 protocol tests + archive/verify roundtrip.

The fake S3 in this file reconstructs the canonical request **from the received
headers only** (as real S3 does) and recomputes the signature; a client whose
canonical string deviates from the AWS-documented S3 format fails PUT/GET with
403. Final SigV4 conformance against a real MinIO/S3 belongs to the F5
staging gate (documented in the module); CI proves protocol behavior offline.
"""
import hashlib
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from swarmax.coldstore import (CHUNK_ROWS, S3CompatStore, archive_ledger,
                               verify_archive)
from swarmax.db import connect, init_db_with_migrations
from swarmax.evidence import append_evidence

SECRET = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
ACCESS = "AKIDEXAMPLE"


class FakeS3(BaseHTTPRequestHandler):
    """Tiny S3-compatible server: SigV4-verifying PUT/HEAD/GET over a dict."""

    def log_message(self, *a):  # silence
        pass

    # -- SigV4 server-side recompute (from received headers) -----------------
    def _verify(self) -> bool:
        auth = self.headers.get("Authorization", "")
        amz_date = self.headers.get("x-amz-date", "")
        payload_hash = self.headers.get("x-amz-content-sha256", "")
        if not (auth.startswith("AWS4-HMAC-SHA256") and amz_date and payload_hash):
            return False
        cred_part = auth.split("Credential=")[1].split(",")[0].strip()
        signed_headers = auth.split("SignedHeaders=")[1].split(",")[0].strip()
        signature = auth.split("Signature=")[1].strip()
        scope = cred_part.split("/", 1)[1]
        datestamp = amz_date[:8]
        region = scope.split("/")[1]
        # canonical: method, full path (bucket included, path-style), empty query
        key_path = self.path.split("?", 1)[0]
        header_lines, header_names = [], []
        for name in signed_headers.split(";"):
            value = self.headers.get(name, "")
            header_lines.append(f"{name}:{value.strip()}")
            header_names.append(name)
        canonical = (f"{self.command}\n{key_path}\n\n"
                     + "\n".join(header_lines) + "\n\n"
                     + ";".join(header_names) + "\n" + payload_hash)
        sts = (f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
               f"{hashlib.sha256(canonical.encode()).hexdigest()}")

        def sign(k: bytes, m: str) -> bytes:
            return hmac.new(k, m.encode(), hashlib.sha256).digest()

        k = sign(sign(sign(sign(f"AWS4{self.server.secret}".encode(),
                                datestamp), region), "s3"), "aws4_request")
        return hmac.new(k, sts.encode(), hashlib.sha256).hexdigest() == signature

    def _route(self, store_body: bytes | None = None) -> None:
        if not self._verify():
            self._respond(403, b"<Error><Code>SignatureDoesNotMatch</Code></Error>")
            return
        key = self.path.split(f"/{self.server.bucket}/", 1)[1]
        if self.command == "PUT":
            self.server.objects[key] = store_body or b""
            self._respond(200, b"")
        elif self.command == "GET":
            if key in self.server.objects:
                self._respond(200, self.server.objects[key])
            else:
                self._respond(404, b"<Error><Code>NoSuchKey</Code></Error>")
        elif self.command == "HEAD":
            self._respond(200 if key in self.server.objects else 404, b"")
        else:
            self._respond(405, b"")

    def _respond(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_PUT(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        self._route(self.rfile.read(length) if length else b"")

    def do_GET(self) -> None:
        self._route()

    def do_HEAD(self) -> None:
        self._route()


@pytest.fixture()
def fake_s3():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeS3)
    srv.objects: dict[str, bytes] = {}
    srv.bucket = "swarmax-test"
    srv.secret = SECRET
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    time.sleep(0.1)
    yield srv
    srv.shutdown()


def _store(port: int, *, secret: str = SECRET) -> S3CompatStore:
    return S3CompatStore(f"http://127.0.0.1:{port}", "swarmax-test", ACCESS,
                         secret, prefix="evidence")


def _ledger(tmp_path, n: int):
    conn = connect(str(tmp_path / "c.db"))
    init_db_with_migrations(conn)
    for i in range(n):
        append_evidence(conn, "cold_test", {"i": i, "pad": "x" * 32})
    conn.commit()
    return conn


def test_sigv4_roundtrip_and_rejection(fake_s3):
    store = _store(fake_s3.server_address[1])
    store.put("hello.txt", b"swarmax")
    assert store.head("hello.txt")
    assert store.get("hello.txt") == b"swarmax"
    assert not store.head("missing.txt")
    # wrong secret must fail on the server side with 403
    bad = _store(fake_s3.server_address[1], secret="wrong-secret")
    with pytest.raises(RuntimeError, match="403"):
        bad.put("nope.txt", b"x")


def test_archive_verify_roundtrip_multichunk(fake_s3, tmp_path, monkeypatch):
    monkeypatch.setattr("swarmax.coldstore.CHUNK_ROWS", 10)
    conn = _ledger(tmp_path, 25)
    store = _store(fake_s3.server_address[1])
    summary = archive_ledger(conn, store)
    assert summary["rows"] == 25 and summary["chunks_stored"] == 3
    result = verify_archive(store)
    assert result["ok"] is True and result["rows"] == 25
    assert result["last_seq"] == 25


def test_archive_is_idempotent(fake_s3, tmp_path, monkeypatch):
    monkeypatch.setattr("swarmax.coldstore.CHUNK_ROWS", 10)
    conn = _ledger(tmp_path, 15)
    store = _store(fake_s3.server_address[1])
    first = archive_ledger(conn, store)
    assert first["chunks_stored"] == 2
    second = archive_ledger(conn, store)
    assert second["chunks_stored"] == 0 and second["chunks_skipped"] == 2
    assert verify_archive(store)["ok"] is True


def test_verify_detects_chunk_tamper(fake_s3, tmp_path, monkeypatch):
    monkeypatch.setattr("swarmax.coldstore.CHUNK_ROWS", 10)
    conn = _ledger(tmp_path, 12)
    store = _store(fake_s3.server_address[1])
    archive_ledger(conn, store)
    # attacker rewrites one archived chunk in the object store
    fake_s3.objects["evidence/chunk_000000000001_000000000010.json.gz"] = b"forged"
    result = verify_archive(store)
    assert result["ok"] is False and "mismatch" in (result.get("reason") or "")


def test_empty_ledger_raises(fake_s3, tmp_path):
    conn = connect(str(tmp_path / "e.db"))
    init_db_with_migrations(conn)
    with pytest.raises(ValueError, match="nothing to archive"):
        archive_ledger(conn, _store(fake_s3.server_address[1]))
