"""Pure-Python Ed25519 (RFC 8032) — stdlib-only F2 signing (paper §12.1, §14 R1).

Compact reference-style implementation (extended twisted-Edwards coordinates).
Slow in pure Python by design trade-off: F0's rule is zero runtime dependencies;
signing volume (ledger seals) is tiny, so this is the right cost point.
"""
from __future__ import annotations

import hashlib
import os

P = 2**255 - 19
Q = 2**252 + 27742317777372353535851937790883648493


def _sha512(s: bytes) -> bytes:
    return hashlib.sha512(s).digest()


def _modp_inv(x: int) -> int:
    return pow(x, P - 2, P)


D = -121665 * _modp_inv(121666) % P


def _sha512_modq(s: bytes) -> int:
    return int.from_bytes(_sha512(s), "little") % Q


def _point_add(Pt, Qt):
    A = (Pt[1] - Pt[0]) * (Qt[1] - Qt[0]) % P
    B = (Pt[1] + Pt[0]) * (Qt[1] + Qt[0]) % P
    C = 2 * Pt[3] * Qt[3] * D % P
    Dd = 2 * Pt[2] * Qt[2] % P
    E, F, G, Hh = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, G * Hh % P, F * G % P, E * Hh % P)


def _point_mul(s: int, Pt):
    Qp = (0, 1, 1, 0)  # identity
    while s > 0:
        if s & 1:
            Qp = _point_add(Qp, Pt)
        Pt = _point_add(Pt, Pt)
        s >>= 1
    return Qp


def _point_equal(Pt, Qt) -> bool:
    if (Pt[0] * Qt[2] - Qt[0] * Pt[2]) % P != 0:
        return False
    if (Pt[1] * Qt[2] - Qt[1] * Pt[2]) % P != 0:
        return False
    return True


def _modp_recover_x(y: int, sign_bit: int) -> int | None:
    if y >= P:
        return None
    x2 = (y * y - 1) * _modp_inv(D * y * y + 1)
    if x2 == 0:
        return 0 if not sign_bit else None
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * pow(2, (P - 1) // 4, P) % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != sign_bit:
        x = P - x
    return x


_Gy = 4 * _modp_inv(5) % P
_Gx = _modp_recover_x(_Gy, 0)
G = (_Gx, _Gy, 1, _Gx * _Gy % P)


def _secret_expand(secret: bytes) -> tuple[int, bytes]:
    if len(secret) != 32:
        raise ValueError("Ed25519 seed must be 32 bytes")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= (1 << 254)
    return a, h[32:]


def secret_to_public(secret: bytes) -> bytes:
    a, _ = _secret_expand(secret)
    return point_compress(_point_mul(a, G))


def point_compress(Pt) -> bytes:
    zinv = _modp_inv(Pt[2])
    x = Pt[0] * zinv % P
    y = Pt[1] * zinv % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def point_decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign_bit = y >> 255
    y &= (1 << 255) - 1
    x = _modp_recover_x(y, sign_bit)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


def generate_seed() -> bytes:
    return os.urandom(32)


def sign(secret: bytes, msg: bytes) -> bytes:
    a, prefix = _secret_expand(secret)
    A = point_compress(_point_mul(a, G))
    r = _sha512_modq(prefix + msg)
    R = _point_mul(r, G)
    Rs = point_compress(R)
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % Q
    return Rs + int.to_bytes(s, 32, "little")


def verify(public: bytes, msg: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    A = point_decompress(public)
    if not A:
        return False
    Rs = signature[:32]
    R = point_decompress(Rs)
    if not R:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= Q:
        return False
    h = _sha512_modq(Rs + public + msg)
    sB = _point_mul(s, G)
    hA = _point_mul(h, A)
    return _point_equal(sB, _point_add(R, hA))
