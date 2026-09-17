"""RFC 8439 ChaCha20-Poly1305 AEAD — verified against the RFC test vectors.

Pure stdlib. Used to encrypt data-subject payloads so GDPR Art. 17 erasure is
crypto-shredding: destroying the subject's 256-bit key makes every ciphertext
permanently undecryptable without rewriting any ledger row.
"""
from __future__ import annotations

import hashlib
import hmac
import struct


def _rotl(v: int, c: int) -> int:
    return ((v << c) & 0xFFFFFFFF) | (v >> (32 - c))


def _quarter(s: list, a: int, b: int, c: int, d: int) -> None:
    s[a] = (s[a] + s[b]) & 0xFFFFFFFF; s[d] ^= s[a]; s[d] = _rotl(s[d], 16)
    s[c] = (s[c] + s[d]) & 0xFFFFFFFF; s[b] ^= s[c]; s[b] = _rotl(s[b], 12)
    s[a] = (s[a] + s[b]) & 0xFFFFFFFF; s[d] ^= s[a]; s[d] = _rotl(s[d], 8)
    s[c] = (s[c] + s[d]) & 0xFFFFFFFF; s[b] ^= s[c]; s[b] = _rotl(s[b], 7)


def _chacha20_block(key: bytes, counter: int, nonce: bytes) -> bytes:
    assert len(key) == 32 and len(nonce) == 12
    consts = [0x61707865, 0x3320646E, 0x79622D32, 0x6B206574]
    k = list(struct.unpack("<8I", key))
    n = list(struct.unpack("<3I", nonce))
    state = consts + k + [counter] + n
    w = state[:]
    for _ in range(10):
        _quarter(w, 0, 4, 8, 12); _quarter(w, 1, 5, 9, 13)
        _quarter(w, 2, 6, 10, 14); _quarter(w, 3, 7, 11, 15)
        _quarter(w, 0, 5, 10, 15); _quarter(w, 1, 6, 11, 12)
        _quarter(w, 2, 7, 8, 13); _quarter(w, 3, 4, 9, 14)
    out = [(w[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
    return struct.pack("<16I", *out)


def _poly1305_mac(key: bytes, msg: bytes) -> bytes:
    r_lo, r_hi = struct.unpack("<2Q", key[:16])
    r_lo &= 0x0FFFFFFC0FFFFFFF          # RFC 8439 §2.5 clamp
    r_hi &= 0x0FFFFFFC0FFFFFFC
    s_lo, s_hi = struct.unpack("<2Q", key[16:32])
    p = (1 << 130) - 5
    acc = 0
    for i in range(0, len(msg), 16):
        block = msg[i:i + 16]
        n = int.from_bytes(block + b"\x01", "little")
        acc = ((acc + n) * ((r_hi << 64) | r_lo)) % p
    acc += s_lo | (s_hi << 64)
    return (acc & ((1 << 128) - 1)).to_bytes(16, "little")


def _pad16(data: bytes) -> bytes:
    return b"" if len(data) % 16 == 0 else b"\x00" * (16 - len(data) % 16)


class ChaCha20Poly1305:
    """AEAD_chacha20_poly1305 with 96-bit nonces (RFC 8439 §2.8)."""

    def __init__(self, key: bytes):
        if not isinstance(key, (bytes, bytearray)) or len(key) != 32:
            raise ValueError("key must be 32 bytes")
        self._key = bytes(key)

    def _tag(self, ciphertext: bytes, aad: bytes, nonce: bytes) -> bytes:
        mac_key = _chacha20_block(self._key, 0, nonce)[:32]
        mac_data = (aad + _pad16(aad) + ciphertext + _pad16(ciphertext)
                    + struct.pack("<QQ", len(aad), len(ciphertext)))
        return _poly1305_mac(mac_key, mac_data)

    def encrypt(self, nonce: bytes, data: bytes, aad: bytes = b"") -> bytes:
        if len(nonce) != 12:
            raise ValueError("nonce must be 12 bytes")
        keystream = b"".join(
            _chacha20_block(self._key, 1 + i, nonce)
            for i in range(len(data) // 64 + 1)
        )[:len(data)]
        ct = bytes(a ^ b for a, b in zip(data, keystream))
        return ct + self._tag(ct, aad, nonce)

    def decrypt(self, nonce: bytes, ciphertext_and_tag: bytes, aad: bytes = b"") -> bytes:
        if len(nonce) != 12:
            raise ValueError("nonce must be 12 bytes")
        if len(ciphertext_and_tag) < 16:
            raise ValueError("ciphertext too short")
        ct, tag = ciphertext_and_tag[:-16], ciphertext_and_tag[-16:]
        if not hmac.compare_digest(self._tag(ct, aad, nonce), tag):
            raise ValueError("authentication failed")
        keystream = b"".join(
            _chacha20_block(self._key, 1 + i, nonce)
            for i in range(len(ct) // 64 + 1)
        )[:len(ct)]
        return bytes(a ^ b for a, b in zip(ct, keystream))


def b64e(b: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def b64d(s: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    """RFC 5869 HKDF-SHA256 (extract+expand) for master->subject key derivation."""
    prk = hmac.new(salt or b"\x00" * 32, ikm, hashlib.sha256).digest()
    okm, t, i = b"", b"", 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
        i += 1
    return okm[:length]
