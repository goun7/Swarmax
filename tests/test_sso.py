"""SSO (WS-C): PKCE, HS256/RS256 id_token verification, fake-IdP end-to-end flow."""
import base64
import hashlib
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from swarmax.sso import (SsoError, build_authorize_url, exchange_code,
                         pkce_pair, rsa_verify_pkcs1v15_sha256, verify_id_token)

SECRET = "client-secret-0123456789abcdef"


def _jwt(header: dict, claims: dict, key, alg: str = "HS256") -> str:
    def b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    h = b64(json.dumps(header).encode())
    p = b64(json.dumps(claims).encode())
    signing_input = f"{h}.{p}".encode()
    if alg == "HS256":
        key_b = key.encode() if isinstance(key, str) else key
        sig = hmac.new(key_b, signing_input, hashlib.sha256).digest()
    else:
        n, d = key
        k = (n.bit_length() + 7) // 8
        digest_info = bytes.fromhex("3031300d060960864801650304020105000420") \
            + hashlib.sha256(signing_input).digest()
        em = b"\x00\x01" + b"\xff" * (k - len(digest_info) - 3) + b"\x00" + digest_info
        sig = pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")
    return f"{h}.{p}.{b64(sig)}"


def _claims(**over):
    now = int(time.time())
    base = {"iss": "https://idp.example.com", "aud": "swarmax-console",
            "sub": "user-42", "email": "op@example.com", "exp": now + 300,
            "iat": now, "nonce": "n0nce"}
    base.update(over)
    return base


def test_pkce_pair_rfc7636_shape():
    v, c = pkce_pair()
    assert 64 <= len(v) <= 128 and "+" not in c and "/" not in c and "=" not in c
    assert c == base64.urlsafe_b64encode(
        hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


def test_hs256_roundtrip_and_nonce():
    tok = _jwt({"alg": "HS256", "typ": "JWT"}, _claims(), SECRET)
    claims = verify_id_token(tok, expect_iss="https://idp.example.com",
                             expect_aud="swarmax-console", client_secret=SECRET,
                             expect_nonce="n0nce")
    assert claims["sub"] == "user-42"


def test_hs256_rejects_tamper_and_wrong_secret():
    tok = _jwt({"alg": "HS256", "typ": "JWT"}, _claims(), SECRET)
    h, p, s = tok.split(".")
    bad = f"{h}.{p}." + (s[:-2] + ("aa" if not s.endswith("aa") else "bb"))
    with pytest.raises(SsoError, match="signature"):
        verify_id_token(bad, expect_iss="https://idp.example.com",
                        expect_aud="swarmax-console", client_secret=SECRET)
    with pytest.raises(SsoError):
        verify_id_token(tok, expect_iss="https://idp.example.com",
                        expect_aud="swarmax-console", client_secret="wrong")


def test_claim_checks_fail_closed():
    tok = _jwt({"alg": "HS256", "typ": "JWT"},
               _claims(exp=int(time.time()) - 300),  # far beyond the 60 s leeway
               SECRET)
    with pytest.raises(SsoError, match="expired"):
        verify_id_token(tok, expect_iss="https://idp.example.com",
                        expect_aud="swarmax-console", client_secret=SECRET)
    tok = _jwt({"alg": "HS256", "typ": "JWT"}, _claims(iss="https://evil.example"),
               SECRET)
    with pytest.raises(SsoError, match="iss"):
        verify_id_token(tok, expect_iss="https://idp.example.com",
                        expect_aud="swarmax-console", client_secret=SECRET)
    tok = _jwt({"alg": "HS256", "typ": "JWT"}, _claims(aud="other-client"), SECRET)
    with pytest.raises(SsoError, match="aud"):
        verify_id_token(tok, expect_iss="https://idp.example.com",
                        expect_aud="swarmax-console", client_secret=SECRET)
    tok = _jwt({"alg": "HS256", "typ": "JWT"}, _claims(nonce="wrong"), SECRET)
    with pytest.raises(SsoError, match="nonce"):
        verify_id_token(tok, expect_iss="https://idp.example.com",
                        expect_aud="swarmax-console", client_secret=SECRET,
                        expect_nonce="n0nce")
    tok = _jwt({"alg": "none", "typ": "JWT"}, _claims(), b"")
    with pytest.raises(SsoError, match="alg"):
        verify_id_token(tok, expect_iss="https://idp.example.com",
                        expect_aud="swarmax-console")


def _gen_prime(rng, bits: int) -> int:
    """Deterministic-ish prime via Miller-Rabin (fixed seed -> reproducible test)."""
    def is_probable_prime(n: int) -> bool:
        if n < 2:
            return False
        for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            if n % p == 0:
                return n == p
        d, r = n - 1, 0
        while d % 2 == 0:
            d //= 2
            r += 1
        for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            x = pow(a, d, n)
            if x in (1, n - 1):
                continue
            for _ in range(r - 1):
                x = pow(x, 2, n)
                if x == n - 1:
                    break
            else:
                return False
        return True

    while True:
        c = rng.getrandbits(bits) | (1 << (bits - 1)) | 1
        if is_probable_prime(c) and c % 65537 != 1:
            return c


def test_rs256_signs_with_d_and_verifies_with_n_e():
    import random
    rng = random.Random(7)
    # PKCS#1 v1.5 + SHA-256 needs a modulus of >= ~520 bits (t is 51 bytes)
    p = _gen_prime(rng, 320)
    q = _gen_prime(rng, 320)
    while q == p:
        q = _gen_prime(rng, 320)
    n = p * q
    phi = (p - 1) * (q - 1)
    e = 65537
    d = pow(e, -1, phi)
    tok = _jwt({"alg": "RS256", "typ": "JWT"}, _claims(), (n, d), alg="RS256")
    claims = verify_id_token(
        tok, expect_iss="https://idp.example.com", expect_aud="swarmax-console",
        jwk={"kty": "RSA", "n": _b64int(n), "e": _b64int(e)})
    assert claims["sub"] == "user-42"


def _b64int(v: int) -> str:
    return base64.urlsafe_b64encode(v.to_bytes((v.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()


def test_authorize_url_contains_pkce_and_state():
    url, state, verifier = build_authorize_url(
        {"issuer": "https://idp.example.com", "client_id": "swarmax-console"},
        redirect_uri="http://127.0.0.1:8080/sso/callback")
    q = parse_qs(urlparse(url).query)
    assert q["code_challenge_method"] == ["S256"]
    assert q["state"] == [state] and q["response_type"] == ["code"]
    assert q["code_challenge"][0] == base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


class FakeIdP(BaseHTTPRequestHandler):
    """In-process IdP: validates PKCE and mints an HS256 id_token."""

    def log_message(self, *a):
        pass

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode())
        verifier = form["code_verifier"][0]
        code = form["code"][0]
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        ok = self.server.challenges.get(code) == expected
        body = json.dumps({
            "access_token": "at", "token_type": "Bearer",
            "id_token": self.server.mint(ok, self.server.server_address[1]),
        }).encode()
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def fake_idp():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeIdP)

    def mint(ok: bool, port: int) -> str:
        iss = f"http://127.0.0.1:{port}"
        claims = _claims(nonce="n0nce", email="operator@example.com", iss=iss)
        if not ok:
            claims["iss"] = "https://spoofed"
        return _jwt({"alg": "HS256", "typ": "JWT"}, claims, SECRET)

    srv.mint = mint
    srv.challenges: dict[str, str] = {}
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    time.sleep(0.1)
    yield srv
    srv.shutdown()


def test_end_to_end_pkce_flow(fake_idp):
    port = fake_idp.server_address[1]
    config = {"issuer": f"http://127.0.0.1:{port}", "client_id": "swarmax-console",
              "client_secret": SECRET}
    url, state, verifier = build_authorize_url(config,
                                               redirect_uri="http://127.0.0.1:8080/sso/callback")
    code = "authcode-1"
    fake_idp.challenges[code] = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    tokens = exchange_code(config, code=code,
                           redirect_uri="http://127.0.0.1:8080/sso/callback",
                           code_verifier=verifier)
    claims = verify_id_token(tokens["id_token"],
                             expect_iss=f"http://127.0.0.1:{port}",
                             expect_aud="swarmax-console",
                             client_secret=SECRET, expect_nonce="n0nce")
    assert claims["email"] == "operator@example.com"


def test_wrong_pkce_verifier_fails(fake_idp):
    port = fake_idp.server_address[1]
    config = {"issuer": f"http://127.0.0.1:{port}", "client_id": "swarmax-console",
              "client_secret": SECRET}
    code = "authcode-2"
    fake_idp.challenges[code] = "correct-challenge"
    with pytest.raises(Exception):
        exchange_code(config, code=code,
                      redirect_uri="http://127.0.0.1:8080/sso/callback",
                      code_verifier="wrong-verifier")
