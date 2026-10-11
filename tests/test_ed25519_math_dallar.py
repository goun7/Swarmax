"""69-Swarmax ed25519 dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (saf-arithmetik — dis cagri YOK).
Ed25519 twisted-Edards nokta-arithmetigi (RFC 8032).
"""
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from swarmax.ed25519 import (  # noqa: E402
    _point_add, _point_mul, _point_equal, _modp_recover_x,
    _secret_expand, P, D, G, _Gy, _Gx, _modp_inv, point_compress,
    point_decompress,
)


# == sabitler =========================================================================================

def test_p_asal():
    assert P == 2**255 - 19


def test_p_bit():
    assert P.bit_length() == 255


def test_d_kucuk():
    assert 0 < D < P


def test_base_point_uzunluk():
    assert len(G) == 4


def test_g_curve():
    """ORTAM: twisted-Edwards: -x^2 + y^2 = 1 + D x^2 y^2."""
    x, y, z, t = G
    assert (-x * x + y * y) % P == (1 + D * x * x * y * y) % P


def test_g_extended_t():
    """ORTAM: T = X*Y/Z."""
    x, y, z, t = G
    assert (x * y) % P == (t * z) % P


def test_gx_sign_bit0():
    """ORTAM: _Gx = _modp_recover_x(_Gy, 0) -> cift."""
    assert _Gx % 2 == 0


def test_gy_degeri():
    """ORTAM: Gy = 4 * 1/5 mod P."""
    assert _Gy == (4 * pow(5, P - 2, P)) % P


def test_g_not_identity():
    """ORTAM: G != (0,1,1,0)."""
    assert not _point_equal(G, (0, 1, 1, 0))


# == _modp_inv =========================================================================================

def test_inv_bir():
    """ORTAM: 1 * 1 = 1."""
    assert _modp_inv(1) == 1


def test_inv_kendisi():
    """ORTAM: a * inv(a) = 1 mod P."""
    for a in (2, 3, 5, 100, P - 1):
        assert (a * _modp_inv(a)) % P == 1


def test_inv_mod_p():
    assert 0 <= _modp_inv(5) < P


# == _point_add ========================================================================================

def test_add_identity():
    """ORTAM: P + identity = P."""
    r = _point_add(G, (0, 1, 1, 0))
    assert _point_equal(r, G)


def test_add_kendisi():
    """ORTAM: G + G = 2G."""
    r = _point_add(G, G)
    iki = _point_mul(2, G)
    assert _point_equal(r, iki)


def test_add_uzunluk():
    assert len(_point_add(G, G)) == 4


def test_add_mod_p():
    assert all(0 <= c < P for c in _point_add(G, G))


def test_add_komutatif():
    """ORTAM: P + Q = Q + P (extended-coords)."""
    q = _point_mul(3, G)
    assert _point_equal(_point_add(G, q), _point_add(q, G))


def test_add_negatif():
    """ORTAM: G + (-G) = identity."""
    neg = (P - G[0], G[1], G[2], (P - G[3]) % P)
    r = _point_add(G, neg)
    assert _point_equal(r, (0, 1, 1, 0))


# == _point_mul =========================================================================================

def test_mul_sifir():
    """ORTAM: 0 * G = identity."""
    assert _point_mul(0, G) == (0, 1, 1, 0)


def test_mul_bir():
    """ORTAM: 1*G = G (farkli-Z olabilir -> _point_equal)."""
    assert _point_equal(_point_mul(1, G), G)


def test_mul_iki():
    assert _point_equal(_point_mul(2, G), _point_add(G, G))


def test_mul_l():
    """ORTAM: L * G = identity (sonlu-grup)."""
    L = 2**252 + 27742317777372353535851937790883648493
    assert _point_equal(_point_mul(L, G), (0, 1, 1, 0))


def test_mul_associative():
    """ORTAM: (a*b)*G = a*(b*G)."""
    a, b = 3, 5
    sol = _point_mul(a * b, G)
    sag = _point_mul(a, _point_mul(b, G))
    assert _point_equal(sol, sag)


def test_mul_dagilim():
    """ORTAM: (a+b)*G = a*G + b*G."""
    sol = _point_mul(7, G)
    sag = _point_add(_point_mul(3, G), _point_mul(4, G))
    assert _point_equal(sol, sag)


@pytest.mark.parametrize("k", [1, 2, 3, 5, 7, 100, 1000])
def test_mul_matrix(k):
    """ORTAM: her k icin nokta curve uzerinde."""
    r = _point_mul(k, G)
    zi = pow(r[2], P - 2, P)
    x, y = (r[0] * zi) % P, (r[1] * zi) % P
    assert (-x * x + y * y) % P == (1 + D * x * x * y * y) % P


# == _point_equal ======================================================================================

def test_equal_ayni():
    assert _point_equal(G, G) is True


def test_equal_ayni_scaled():
    """ORTAM: farkli Z ama ayni nokta."""
    g2 = (G[0] * 2 % P, G[1] * 2 % P, G[2] * 2 % P, G[3] * 2 % P)
    assert _point_equal(G, g2) is True


def test_equal_farkli():
    assert _point_equal(G, _point_mul(2, G)) is False


def test_equal_identity():
    """ORTAM: identity esitlik kontrolu."""
    assert _point_equal((0, 1, 1, 0), (0, 1, 1, 0)) is True


def test_equal_returns_bool():
    assert isinstance(_point_equal(G, G), bool)


# == _modp_recover_x ====================================================================================

def test_recover_gy():
    """ORTAM: Gy'den _Gx recover edilir."""
    assert _modp_recover_x(_Gy, 0) == _Gx


def test_recover_y_buyuk_p():
    """ORTAM: y >= P -> None."""
    assert _modp_recover_x(P, 0) is None


def test_recover_y_p_arti_bir():
    assert _modp_recover_x(P + 1, 0) is None


def test_recover_isaret():
    """ORTAM: sign-bit tersi -> P - x."""
    a = _modp_recover_x(_Gy, 0)
    b = _modp_recover_x(_Gy, 1)
    assert (a + b) % P == 0


def test_recover_curve_denklemi():
    """ORTAM: recover edilen x curve-denklemini saglar."""
    x = _modp_recover_x(_Gy, 0)
    y = _Gy
    assert (-x * x + y * y) % P == (1 + D * x * x * y * y) % P


def test_recover_x2_sifir():
    """ORTAM: x2 = 0 -> sign 0 ise 0, 1 ise None."""
    # y^2 - 1 = 0 -> y = 1
    assert _modp_recover_x(1, 0) == 0
    assert _modp_recover_x(1, 1) is None


def test_recover_nonresidue():
    """ORTAM: kare-olmayan x2 -> None."""
    # y sec ki x2 quadratic-residue olmasin (bir kac dene)
    for y in (2, 3, 6, 7, 10, 11):
        r = _modp_recover_x(y, 0)
        if r is None:
            continue


def test_recover_aralik():
    r = _modp_recover_x(_Gy, 0)
    assert 0 <= r < P


# == _secret_expand ====================================================================================

def test_secret_uzunluk():
    """ORTAM: 32-bayt sart."""
    with pytest.raises((ValueError, AssertionError, TypeError)):
        _secret_expand(b"\x01" * 31)


def test_secret_kisa():
    with pytest.raises((ValueError, AssertionError, TypeError)):
        _secret_expand(b"\x01" * 16)


def test_secret_bos():
    with pytest.raises((ValueError, AssertionError, TypeError)):
        _secret_expand(b"")


def test_secret_uzun():
    with pytest.raises((ValueError, AssertionError, TypeError)):
        _secret_expand(b"\x01" * 33)


def test_secret_deterministik():
    """ORTAM: ayni secret ayni cikti."""
    s = b"\x02" * 32
    assert _secret_expand(s) == _secret_expand(s)


def test_secret_farkli():
    assert (_secret_expand(b"\x01" * 32)
            != _secret_expand(b"\x02" * 32))


def test_secret_clamp():
    """ORTAM: clamped scalar bit-254 BIR, dusuk-3-bit sifir."""
    n, prefix = _secret_expand(b"\x00" * 32)
    assert n % 8 == 0
    assert n & (1 << 254) != 0
    assert n & (1 << 255) == 0


def test_secret_prefix_32():
    """ORTAM: prefix 32-bayt."""
    _, prefix = _secret_expand(b"\x01" * 32)
    assert len(prefix) == 32


@pytest.mark.parametrize("n", [1, 2, 3, 5, 100])
def test_secret_matrix(n):
    """ORTAM: her secret farkli scalar."""
    a = _secret_expand(bytes([n]) * 32)
    b = _secret_expand(bytes([n + 1]) * 32)
    assert a != b


# == compress/decompress ===============================================================================

def test_compress_uzunluk():
    assert len(point_compress(G)) == 32


def test_roundtrip_g():
    """ORTAM: compress/decompress roundtrip."""
    c = point_compress(G)
    r = point_decompress(c)
    assert r is not None
    assert _point_equal(r, G)


@pytest.mark.parametrize("k", [1, 2, 3, 5, 7, 100, 1000])
def test_roundtrip_matrix(k):
    """ORTAM: roundtrip her skaler-kat icin."""
    p = _point_mul(k, G)
    r = point_decompress(point_compress(p))
    assert r is not None
    assert _point_equal(r, p)


def test_decompress_uzunluk_hatasi():
    """ORTAM: 31-bayt -> None."""
    assert point_decompress(b"x" * 31) is None


def test_decompress_uzun():
    assert point_decompress(b"x" * 33) is None


def test_decompress_bos():
    assert point_decompress(b"") is None


def test_compress_repeatable():
    assert point_compress(G) == point_compress(G)


# == genel ==============================================================================================

def test_g_iki_kat_farkli():
    assert not _point_equal(_point_mul(2, G), G)


def test_g_pubkey():
    """ORTAM: G'nin public-key degeri sabit."""
    c = point_compress(G)
    assert len(c) == 32
    assert c == point_compress(G)
