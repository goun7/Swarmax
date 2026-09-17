"""SSO for the fleet console — OpenID Connect with PKCE (§8 ops model, v2 step).

Zero-dependency OIDC RP (relying party) covering the two signature algorithms
that matter in practice:

  - HS256: id_token signed with the client secret (shared symmetric key)
  - RS256: id_token signed with an RSA key; verification is pure stdlib
    (modular exponentiation + PKCS#1 v1.5 encoding) driven by the provider's
    published JWK — no vendor SDK.

Flow: ``build_authorize_url`` → user authenticates at the IdP →
``exchange_code`` posts the authorization code (with PKCE verifier) to the
token endpoint → ``verify_id_token`` validates iss/aud/exp/nonce/signature and
returns the claims. The console maps claims → ``sso_links`` → a session.

Honest scope: this is the console login SSO. SCIM-style user sync and
multi-tenant console sharding are v2 distribution work (AI_ACT gap B-log).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse
import urllib.request

__all__ = ["SsoError", "pkce_pair", "build_authorize_url", "exchange_code",
           "verify_id_token", "rsa_verify_pkcs1v15_sha256"]


class SsoError(ValueError):
    """Any SSO verification failure — always fail closed."""


# ------------------------------------------------------------------ helpers
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def pkce_pair() -> tuple[str, str]:
    """(verifier, challenge) — RFC 7636 S256: challenge = BASE64URL(SHA256(verifier))."""
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


# ------------------------------------------------------------------ RSA (verify only)
# DigestInfo prefix for SHA-256 (RFC 8017 §9.2 note 1)
_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def rsa_verify_pkcs1v15_sha256(n: int, e: int, signature: bytes, msg: bytes) -> bool:
    """RSASSA-PKCS1-v1_5 with SHA-256, verify-only, pure stdlib."""
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    s = int.from_bytes(signature, "big")
    if s >= n:
        return False
    em = pow(s, e, n).to_bytes(k, "big")
    t = _SHA256_DIGEST_INFO + hashlib.sha256(msg).digest()
    ps_len = k - len(t) - 3
    expected = b"\x00\x01" + b"\xff" * ps_len + b"\x00" + t
    return hmac.compare_digest(em, expected)


def _jwk_rsa_public(jwk: dict) -> tuple[int, int]:
    if jwk.get("kty") != "RSA":
        raise SsoError("JWK is not RSA")
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return n, e


# ------------------------------------------------------------------ OIDC flow
def build_authorize_url(config: dict, *, redirect_uri: str,
                        state: str | None = None) -> tuple[str, str, str]:
    """Return (authorize_url, state, code_verifier).

    ``config``: {issuer or authorization_endpoint, client_id, code_challenge_method
    defaults to S256}. ``state`` is generated when omitted.
    """
    issuer = config.get("issuer", "").rstrip("/")
    endpoint = config.get("authorization_endpoint") or f"{issuer}/authorize"
    client_id = config["client_id"]
    state = state or secrets.token_urlsafe(24)
    verifier, challenge = pkce_pair()
    q = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "nonce": secrets.token_urlsafe(16),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return f"{endpoint}?{q}", state, verifier


def exchange_code(config: dict, *, code: str, redirect_uri: str,
                  code_verifier: str) -> dict:
    """POST the code to the token endpoint; returns the parsed token JSON."""
    issuer = config.get("issuer", "").rstrip("/")
    endpoint = config.get("token_endpoint") or f"{issuer}/token"
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": config["client_id"],
        "client_secret": config.get("client_secret", ""),
        "code_verifier": code_verifier,
    }).encode()
    req = urllib.request.Request(endpoint, data=data, method="POST",
                                 headers={"Content-Type":
                                          "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def verify_id_token(jwt: str, *, expect_iss: str, expect_aud: str,
                    client_secret: str | None = None,
                    jwk: dict | None = None, expect_nonce: str | None = None,
                    leeway_s: int = 60) -> dict:
    """Validate an OIDC id_token (fail closed) and return its claims.

    Checks: 3-part shape, alg ∈ {HS256, RS256}, signature (secret or JWK),
    exp/nbf/iat with leeway, iss, aud. Nonce checked when provided.
    """
    parts = jwt.split(".")
    if len(parts) != 3:
        raise SsoError("malformed id_token")
    try:
        header = json.loads(_b64url_decode(parts[0]))
        claims = json.loads(_b64url_decode(parts[1]))
        sig = _b64url_decode(parts[2])
    except (ValueError, json.JSONDecodeError) as exc:
        raise SsoError(f"undecodable id_token: {exc}") from exc

    alg = header.get("alg")
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    now = int(time.time())

    def _chk(cond: bool, why: str) -> None:
        if not cond:
            raise SsoError(why)

    _chk(alg in ("HS256", "RS256"), f"unsupported alg: {alg}")

    if alg == "HS256":
        _chk(client_secret is not None, "HS256 requires client_secret")
        expected = hmac.new(client_secret.encode(), signing_input,
                            hashlib.sha256).digest()
        _chk(hmac.compare_digest(sig, expected), "HS256 signature mismatch")
    else:
        _chk(jwk is not None, "RS256 requires the provider JWK")
        n, e = _jwk_rsa_public(jwk)
        _chk(rsa_verify_pkcs1v15_sha256(n, e, sig, signing_input),
             "RS256 signature mismatch")

    exp = claims.get("exp")
    _chk(isinstance(exp, (int, float)), "missing exp")
    _chk(now <= exp + leeway_s, "token expired")
    nbf = claims.get("nbf")
    if nbf is not None:
        _chk(now >= nbf - leeway_s, "token not yet valid")
    iat = claims.get("iat")
    if iat is not None:
        _chk(now >= iat - 3600 - leeway_s, "iat far in the future")

    _chk(claims.get("iss") == expect_iss.rstrip("/"), "iss mismatch")
    aud = claims.get("aud")
    aud_ok = aud == expect_aud or (isinstance(aud, list) and expect_aud in aud)
    _chk(aud_ok, "aud mismatch")
    if expect_nonce is not None:
        _chk(claims.get("nonce") == expect_nonce, "nonce mismatch")
    return claims
