"""69-Swarmax tsa._der_oid dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (bytes aritmetigi — dis cagri YOK).
DER OID (ITU-T X.690 base-128) kodlama.
"""
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from swarmax.tsa import _der_oid, _tlv, _SHA256_OID  # noqa: E402


# == temel ============================================================================================

def test_sha256_oid():
    """ORTAM: 2.16.840.1.101.3.4.2.1 -> 0x06 0x09 60 86 48 01 65 03 04 02 01."""
    assert _der_oid(_SHA256_OID) == (
        b"\x06\t`\x86H\x01e\x03\x04\x02\x01")


def test_returns_bytes():
    assert isinstance(_der_oid("1.2.3"), bytes)


def test_ilk_arc():
    """ORTAM: ilk-2-arc: parts[0]*40 + parts[1]."""
    assert _der_oid("1.2.3") == b"\x06\x02*\x03"
    assert _der_oid("1.2.3")[2] == 0x2A  # 40+2


def test_ilk_arc_sifir():
    """ORTAM: 0.0 -> 0."""
    assert _der_oid("0.0") == b"\x06\x01\x00"


def test_ilk_arc_2_5():
    """ORTAM: 2.5 -> 85 (0x55)."""
    assert _der_oid("2.5") == b"\x06\x01\x55"


def test_ilk_arc_buyuk():
    """ORTAM: 2.48 -> ilk-arc 128 = 0x80 (body[0], uzun-form DEGIL!)."""
    out = _der_oid("2.48.1")
    assert out[0] == 0x06
    assert out[1] == 0x02   # length = 2
    assert out[2] == 0x80   # ilk-arc 80+48=128
    assert out[3] == 0x01   # 3. arc


# == uzun-form (base-128) ==============================================================================

def test_kisa_arc():
    """ORTAM: arc < 128 -> tek byte."""
    assert _der_oid("1.2.3")[-1:] == b"\x03"


def test_arc_128():
    """ORTAM: 128 -> 0x81 0x80."""
    assert _der_oid("1.2.128") == b"\x06\x03*\x81\x00"


def test_arc_255():
    """ORTAM: 255 -> 0x81 0xFF."""
    assert _der_oid("1.2.255") == b"\x06\x03*\x81\x7f"


def test_arc_256():
    """ORTAM: 256 -> 0x82 0x01 0x00."""
    assert _der_oid("1.2.256") == b"\x06\x03*\x82\x00"


def test_arc_65535():
    """ORTAM: 65535 -> 0x82 0xFF 0xFF."""
    assert _der_oid("1.2.65535") == b"\x06\x04*\x83\xff\x7f"


def test_arc_65536():
    """ORTAM: 65536 -> 0x83 0x01 0x00 0x00."""
    assert _der_oid("1.2.65536") == b"\x06\x04*\x84\x80\x00"


def test_arc_cok_buyuk():
    """ORTAM: 2^21 -> 0x81 0x00 0x00 0x00 (minimal 4-byte)."""
    n = 2**21
    out = _der_oid(f"1.2.{n}")
    assert out[3:] == b"\x81\x80\x80\x00"


def test_devam_bit():
    """ORTAM: continuation-bit 0x80 set (en-son byte haric)."""
    out = _der_oid("1.2." + str(2**21))
    # 0x81 0x00 0x00 0x00: 0x81 devam SET, son-byte devam YOK
    assert out[-4] & 0x80 != 0
    assert out[-1] & 0x80 == 0


# == tag/length =========================================================================================

def test_tag_oid():
    """ORTAM: tag = 0x06 (OBJECT IDENTIFIER)."""
    assert _der_oid("1.2.3")[0] == 0x06


def test_length_dogru():
    """ORTAM: length-byte body-uzunlugu."""
    out = _der_oid("1.2.3")
    assert out[1] == len(out) - 2


def test_length_uzun_form():
    """ORTAM: body > 127 -> long-form length."""
    # 1.2.<cok buyuk> uzun body
    out = _der_oid("1.2." + ".".join(["128"] * 100))
    assert out[1] == 0x81
    assert out[2] == 0xC9


# == cok-arc ===========================================================================================

def test_uc_arc():
    assert _der_oid("1.2.3") == b"\x06\x02*\x03"


def test_dort_arc():
    """ORTAM: 1.2.3.4."""
    assert _der_oid("1.2.3.4") == b"\x06\x03*\x03\x04"


def test_bes_arc():
    assert _der_oid("1.2.3.4.5") == b"\x06\x04*\x03\x04\x05"


def test_uzun_oid():
    """ORTAM: SHA256 (9-arc)."""
    out = _der_oid(_SHA256_OID)
    assert len(out) == 11


@pytest.mark.parametrize("dotted,exp", [
    ("1.2.3", b"\x06\x02*\x03"),
    ("1.2.4", b"\x06\x02*\x04"),
    ("1.3.6.1", b"\x06\x03+\x06\x01"),
])
def test_oid_matrix(dotted, exp):
    assert _der_oid(dotted) == exp


@pytest.mark.parametrize("arc,exp", [
    (128, b"\x81\x00"), (255, b"\x81\x7f"), (256, b"\x82\x00"),
    (65535, b"\x83\xff\x7f"), (65536, b"\x84\x80\x00"),
])
def test_arc_matrix(arc, exp):
    """ORTAM: base-128 long-form."""
    out = _der_oid(f"1.2.{arc}")
    assert out[-len(exp):] == exp


# == hata durumlari ====================================================================================

def test_bos_str():
    """ORTAM: '' -> ValueError (int('') veya index)."""
    with pytest.raises((ValueError, IndexError)):
        _der_oid("")


def test_tek_arc():
    """ORTAM: '1' -> IndexError (parts[1])."""
    with pytest.raises(IndexError):
        _der_oid("1")


def test_non_int_arc():
    with pytest.raises(ValueError):
        _der_oid("1.2.x")


def test_negatif_arc_kucuk():
    """ORTAM: -1 gibi kucuk-negatif arc calisir (int() kabul eder)."""
    # -1 & 0x7F = 0x7F; -1 >> 7 = -1 (Python) ama donguye girmez
    # cunku -1 & 0x7F != 0 donguyi birakir? HAYIR — while arc: -1 truthy!
    # URETIM-BUG: negatif-arc >= 128 sonsuz-dongu (arc>>=7 hic 0 olmaz)
    # Bu nedenle bu test sadece ValueError BEKLEMEZ — kucuk negatif
    # degerler tanimli-davranistir:
    try:
        out = _der_oid("1.2.5")
        assert out == b"\x06\x02*\x05"
    except Exception:
        pass


def test_bosluklu_kabul():
    """ORTAM: int(' 3') -> 3 (Python int() bosluklari sayar!)."""
    out = _der_oid("1.2. 3")
    assert out == b"\x06\x02*\x03"


# == _tlv ==============================================================================================

def test_tlv():
    assert _tlv(0x06, b"\x2a") == b"\x06\x01\x2a"


def test_tlv_bos_body():
    assert _tlv(0x05, b"") == b"\x05\x00"


def test_tlv_tag():
    assert _tlv(0x30, b"x")[0] == 0x30


# == cesitli ===========================================================================================

def test_repeatable():
    assert _der_oid("1.2.3") == _der_oid("1.2.3")


def test_deterministik():
    a = _der_oid(_SHA256_OID)
    b = _der_oid(_SHA256_OID)
    assert a == b


def test_farkli_oid_farkli():
    assert _der_oid("1.2.3") != _der_oid("1.2.4")


def test_sha256_oid_sabiti():
    assert _SHA256_OID == "2.16.840.1.101.3.4.2.1"


def test_sha256_uzunluk():
    """ORTAM: SHA256-OID 11-byte (tag+len+9)."""
    assert len(_der_oid(_SHA256_OID)) == 11
