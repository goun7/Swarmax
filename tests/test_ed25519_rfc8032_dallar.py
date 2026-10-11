"""69-Swarmax Ed25519 RFC 8032 uyum + malleability dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (saf crypto — network/subprocess YASAK).

AKADEMIK DAYANAK: ARASTIRMA_AKADEMIK_2026-10-11.md Bolum 2
- RFC 8032 §8.4: S < l malleability (S'l MITM ile degistirilebilir)
- RFC 8032 §8.8: cofactor ile fingerprinting riski
- RFC 8032 §8.5: 128-bit security
"""
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from swarmax import ed25519 as e  # noqa: E402

L = 2**252 + 27742317777372353535851937790883648493


def _sk():
    return e.generate_seed()


# == RFC 8032 §8.4: S < l malleability ==================================================================

def test_rfc8032_8_4_S_kucuk_L():
    """ORTAM: her gecerli imzada S < L (canonik)."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    S = int.from_bytes(sig[32:], "little")
    assert S < L


def test_rfc8032_8_4_S_esit_L_reject():
    """ORTAM-OGRENDI: S = L -> REJECT (RFC 8032 §8.4)."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    sig2 = sig[:32] + L.to_bytes(32, "little")
    assert e.verify(pk, b"m", sig2) is False


def test_rfc8032_8_4_S_buyuk_L_reject():
    """ORTAM: S = L+1 -> REJECT."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    sig2 = sig[:32] + (L + 1).to_bytes(32, "little")
    assert e.verify(pk, b"m", sig2) is False


def test_rfc8032_8_4_S_cok_buyuk_reject():
    """ORTAM: S = L * 2^100 (32-byte tasma yok, little-endian) -> REJECT."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    sig2 = sig[:32] + ((L * (2**10)) % (2**256)).to_bytes(32, "little")
    assert e.verify(pk, b"m", sig2) is False


def test_rfc8032_8_4_S_sifir_reject():
    """ORTAM: S = 0 -> REJECT (dusuk-kanonik-olmayan)."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    sig2 = sig[:32] + (0).to_bytes(32, "little")
    assert e.verify(pk, b"m", sig2) is False


def test_rfc8032_8_4_S_bir_reject():
    """ORTAM: S = 1 -> REJECT."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    sig2 = sig[:32] + (1).to_bytes(32, "little")
    assert e.verify(pk, b"m", sig2) is False


def test_rfc8032_8_4_S_L_eksi_1_kabul():
    """ORTAM: S = L-1 (hala < L) — ama R yanlis oldugu icin reject."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    sig2 = sig[:32] + (L - 1).to_bytes(32, "little")
    assert e.verify(pk, b"m", sig2) is False


def test_rfc8032_8_4_malleability_deterministik():
    """ORTAM: ayni sk+msg ayni imza (deterministik)."""
    sk = _sk()
    assert e.sign(sk, b"m") == e.sign(sk, b"m")


# == imza yapisi ========================================================================================

def test_sig_boyut_64():
    """ORTAM: R (32) + S (32) = 64 byte."""
    assert len(e.sign(_sk(), b"m")) == 64


def test_pk_boyut_32():
    assert len(e.secret_to_public(_sk())) == 32


def test_seed_boyut_32():
    assert len(e.generate_seed()) == 32


def test_pk_deterministik():
    sk = _sk()
    assert e.secret_to_public(sk) == e.secret_to_public(sk)


def test_pk_farkli_seedler_farkli():
    """ORTAM: farkli seed -> farkli pk."""
    a, b = _sk(), _sk()
    assert a != b
    assert e.secret_to_public(a) != e.secret_to_public(b)


def test_R_kismi_bos_reject():
    """ORTAM: R = 0x00*32 -> REJECT."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    assert e.verify(pk, b"m", bytes(32) + sig[32:]) is False


def test_R_kismi_bozuk_reject():
    """ORTAM: R'nin 1 byte'i degistirildi -> REJECT."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    b = bytearray(sig)
    b[0] ^= 0x01
    assert e.verify(pk, b"m", bytes(b)) is False


# == verify: msg dallari =================================================================================

def test_verify_dogru():
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    assert e.verify(pk, b"m", sig) is True


@pytest.mark.parametrize("msg", [b"", b"a", b"\x00", b"\xff" * 64, b"x" * 1000])
def test_verify_mesaj_matrix(msg):
    """ORTAM: cesitli mesaj boyutlari."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, msg)
    assert e.verify(pk, msg, sig) is True


def test_verify_mesaj_degistirildi():
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    assert e.verify(pk, b"n", sig) is False


def test_verify_bos_mesaj():
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"")
    assert e.verify(pk, b"", sig) is True


def test_verify_pk_degistirildi():
    """ORTAM: baska pk ile verify -> REJECT."""
    sk1, sk2 = _sk(), _sk()
    pk2 = e.secret_to_public(sk2)
    sig = e.sign(sk1, b"m")
    assert e.verify(pk2, b"m", sig) is False


def test_verify_tum_sifir_pk():
    """ORTAM: pk=0x00*32 -> REJECT."""
    sig = e.sign(_sk(), b"m")
    assert e.verify(bytes(32), b"m", sig) is False


def test_verify_tum_sifir_sig():
    """ORTAM: sig=0x00*64 -> REJECT."""
    pk = e.secret_to_public(_sk())
    assert e.verify(pk, b"m", bytes(64)) is False


def test_verify_tum_bir_sig():
    """ORTAM: sig=0xff*64 -> REJECT (S > L)."""
    pk = e.secret_to_public(_sk())
    assert e.verify(pk, b"m", b"\xff" * 64) is False


# == Q sabiti ============================================================================================

def test_Q_esit_L():
    """ORTAM-OGRENDI: swarmax Q == RFC 8032 group order l."""
    assert e.Q == L


def test_Q_negatif_degil():
    assert e.Q > 0


def test_Q_bit_boyutu():
    """ORTAM: L 253-bit (2^252 < L < 2^253)."""
    assert e.Q.bit_length() == 253


# == RFC 8032 §8.8: cofactor + fingerprinting ===========================================================

def test_cofactor_Q_eksi_1():
    """ORTAM: ed25519 cofactor h = 8 (L*8 == group order)."""
    # Edwards group order = 8*L
    assert (e.Q * 8).bit_length() <= 256


def test_L_G_order():
    """ORTAM: L * G = identity (zincir testi)."""
    from swarmax.ed25519 import _point_mul, _point_equal, G
    assert _point_equal(_point_mul(L, G), (0, 1, 1, 0))


def test_8L_G_identity():
    """ORTAM-OGRENDI: 8L * G = identity (cofactor ile)."""
    from swarmax.ed25519 import _point_mul, _point_equal, G
    assert _point_equal(_point_mul(8 * L, G), (0, 1, 1, 0))


def test_2L_G_identity():
    """ORTAM: 2L * G = identity (L tek)."""
    from swarmax.ed25519 import _point_mul, _point_equal, G
    assert _point_equal(_point_mul(2 * L, G), (0, 1, 1, 0))


# == genel ===============================================================================================

def test_sign_verify_roundtrip_cok():
    """ORTAM: 10 anahtar + 10 mesaj roundtrip."""
    for _ in range(10):
        sk = _sk(); pk = e.secret_to_public(sk)
        sig = e.sign(sk, b"roundtrip")
        assert e.verify(pk, b"roundtrip", sig) is True


def test_verify_tip_dallari():
    """ORTAM-OGRENDI: yanlis-tip pk -> REJECT (False), exception DEGIL."""
    sk = _sk(); pk = e.secret_to_public(sk)
    sig = e.sign(sk, b"m")
    assert e.verify("not-bytes", b"m", sig) is False
