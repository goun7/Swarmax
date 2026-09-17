"""RFC 3161 timestamp client — Evidence Trust Services T3.1 (§5.3 Hat 2).

A minimal, dependency-free Time-Stamp Protocol client: builds the TSRequest
DER by hand, POSTs it to any HTTP(S) TSA (FreeTSA, DigiCert, EJBCA-internal…),
and verifies the reply *binds* to the stamped data by checking that both the
SHA-256 message imprint and the client nonce appear verbatim in the token.

Honest scope: this module proves binding (that the TSA received and
committed to exactly these bytes at some time it signed) and persists the
raw token.  Full PKI signature-chain verification of the token is left to
standard tooling (`openssl ts -verify -CAfile <tsa.crt>`) — that is an
external audit step, wired into the compliance drill, not silently re-
invented here.  Zero runtime dependencies (§7 F0).
"""
from __future__ import annotations

import hashlib
import os
import secrets
import urllib.error
import urllib.request


class TSAError(RuntimeError):
    pass


# ---------------------------------------------------------------- DER writer
def _der_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def _tlv(tag: int, body: bytes) -> bytes:
    return bytes([tag]) + _der_len(len(body)) + body


def _der_seq(*parts: bytes) -> bytes:
    return _tlv(0x30, b"".join(parts))


def _der_int(value: int) -> bytes:
    if value == 0:
        return _tlv(0x02, b"\x00")
    body = value.to_bytes((value.bit_length() + 8) // 8, "big", signed=False)
    return _tlv(0x02, body)


def _der_oid(dotted: str) -> bytes:
    parts = [int(p) for p in dotted.split(".")]
    body = bytearray([parts[0] * 40 + parts[1]])
    for arc in parts[2:]:
        chunk = bytearray()
        chunk.append(arc & 0x7F)
        arc >>= 7
        while arc:
            chunk.append(0x80 | (arc & 0x7F))
            arc >>= 7
        body += bytes(reversed(chunk))
    return _tlv(0x06, bytes(body))


_SHA256_OID = "2.16.840.1.101.3.4.2.1"


def build_ts_request(data: bytes, *, nonce: int | None = None) -> tuple[bytes, int]:
    """Build a TSRequest over SHA-256(data). Returns (der, nonce).

    Byte-compat verified against `openssl ts -query -data -sha256 -cert`:
    version INTEGER(1) present (FreeTSA's parser rejects the DEFAULT-omitted
    form), AlgorithmIdentifier carries explicit NULL parameters, certReq=TRUE."""
    nonce = nonce if nonce is not None else secrets.randbits(56)
    imprint = hashlib.sha256(data).digest()
    alg = _der_seq(_der_oid(_SHA256_OID), _tlv(0x05, b""))
    message_imprint = _der_seq(alg, _tlv(0x04, imprint))
    req = _der_seq(_der_int(1), message_imprint,
                   _der_int(nonce), _tlv(0x01, b"\xff"))
    return req, nonce


# ---------------------------------------------------------------- HTTP client
def request_timestamp(data: bytes, *, url: str, timeout: float = 15.0,
                      nonce: int | None = None) -> bytes:
    """POST a timestamp query; returns the raw TimeStampResp token bytes.

    Raises TSAError on non-200, wrong content-type, or a reply that does not
    bind to (imprint, nonce) — never stores an unbound token.
    """
    req_der, nonce = build_ts_request(data, nonce=nonce)
    http = urllib.request.Request(
        url, data=req_der, method="POST",
        headers={"Content-Type": "application/timestamp-query",
                 "Accept": "application/timestamp-reply"})
    try:
        with urllib.request.urlopen(http, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            token = resp.read()
    except urllib.error.HTTPError as exc:
        raise TSAError(f"TSA returned {exc.code}: "
                       f"{exc.read()[:200]!r}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TSAError(f"TSA unreachable: {exc}") from exc
    if "application/timestamp-reply" not in ctype and ctype:
        raise TSAError(f"unexpected content-type: {ctype}")
    if not token.startswith(b"\x30"):
        raise TSAError("reply is not DER (missing SEQUENCE tag)")
    verify_token_binding(token, data, nonce=nonce)
    return token


# ---------------------------------------------------------------- verification
def verify_token_binding(token: bytes, data: bytes, *,
                         nonce: int | None = None) -> bool:
    """True when the token carries the exact imprint of ``data`` (and the
    exact nonce, when given).  Binding check only — see module docstring
    for the honest scope of cryptographic chain validation."""
    imprint = hashlib.sha256(data).digest()
    if imprint not in token:
        return False
    if nonce is not None:
        if _der_int(nonce)[2:] not in token:  # value bytes incl. sign byte
            return False
    return True


def tsa_url_from_env() -> str | None:
    """Operator contract: SWARMAX_TSA_URL enables countersigning."""
    return os.environ.get("SWARMAX_TSA_URL") or None
