r"""Swarmax swarmax.tsa._der_len/_der_seq/_der_int/_der_oid/_tlv + exit_drill._encode_value/_decode_value dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory ( saf ASN.1-DER bytes + int/hex; TSA/HTTP-RFC3161/
sqlite CAGRILMAZ).

ORTAM-ANATOMI:
- _der_len(n): DER uzunluk ( kisa/uzun-form)
- _tlv(tag, body): tag-length-value
- _der_seq(*parts): SEQUENCE ( 0x30)
- _der_int(value): INTEGER ( 0x02; pozitif-only)
- _der_oid(dotted): OBJECT IDENTIFIER ( 0x06)
- _encode_value(v): bytes -> {'__bytes__': hex} isareti ( JSON-safe)
- _decode_value(v): isaretten bytes'e geri
"""
import sys

import pytest

sys.path.insert(0, "src")
from swarmax.exit_drill import _decode_value, _encode_value  # noqa: E402
from swarmax.tsa import (  # noqa: E402
    _der_int,
    _der_len,
    _der_oid,
    _der_seq,
    _tlv,
)


# == _der_len =========================================================================================

@pytest.mark.parametrize("n,hex_bek", [(0, "00"), (1, "01"), (127, "7f"),
                                       (128, "8180"), (255, "81ff"),
                                       (256, "820100"), (1000, "8203e8"),
                                       (65535, "82ffff"), (65536, "83010000")])
def test_der_len_tablo(n, hex_bek):
    """ORTAM: n<0x80 kisa-form ( tek-byte); >=0x80 uzun-form
    ( 0x80|uzunluk-bytes + deger)."""
    assert _der_len(n).hex() == hex_bek


def test_der_len_kisa_sinir():
    """ORTAM: 127 (0x7F) son-kisa-form."""
    assert _der_len(127) == b"\x7f"
    assert _der_len(128) == b"\x81\x80"


def test_der_len_uzun_form_min():
    """ORTAM: 128 -> 81 80 ( 1-uzunluk-byte)."""
    assert _der_len(128) == bytes([0x81, 0x80])


def test_der_len_uzun_iki_byte():
    """ORTAM: 256 -> 82 01 00 ( 2-uzunluk-byte)."""
    assert _der_len(256) == bytes([0x82, 0x01, 0x00])


def test_der_len_uzun_uc_byte():
    """ORTAM: 65536 -> 83 01 00 00 ( 3-uzunluk-byte)."""
    assert _der_len(65536) == bytes([0x83, 0x01, 0x00, 0x00])


def test_der_len_donut_bytes():
    assert isinstance(_der_len(5), bytes)


def test_der_len_stabil():
    assert _der_len(300) == _der_len(300)


def test_der_len_minimal():
    """ORTAM-OGRENDI: MINIMAL uzunluk-kodlamasi — 128 icin '81 80' DEGIL
    '82 00 80' ( gereksiz-sifir-byte YOK; DER minimal-kurali)."""
    assert _der_len(128) != b"\x82\x00\x80"
    assert _der_len(256) != b"\x83\x00\x01\x00"


# == _tlv ==============================================================================================

def test_tlv_temel():
    """ORTAM: tag + length + value."""
    assert _tlv(0x04, b"abc") == bytes([0x04, 0x03]) + b"abc"


def test_tlv_kisa_len():
    assert _tlv(0x02, b"\x01").hex() == "020101"


def test_tlv_uzun_len():
    """ORTAM: 200-byte body -> uzun-form length."""
    body = b"x" * 200
    assert _tlv(0x04, body) == bytes([0x04, 0x81, 200]) + body


def test_tlv_bos_body():
    """ORTAM: bos body -> length 0."""
    assert _tlv(0x30, b"").hex() == "3000"


def test_tlv_donut_bytes():
    assert isinstance(_tlv(0x04, b"a"), bytes)


def test_tlv_stabil():
    assert _tlv(0x04, b"abc") == _tlv(0x04, b"abc")


# == _der_seq =========================================================================================

def test_der_seq_temel():
    """ORTAM: SEQUENCE tag 0x30 + icerik."""
    got = _der_seq(b"\x02\x01\x01", b"\x02\x01\x02")
    assert got.hex() == "3006020101020102"


def test_der_seq_tag():
    """ORTAM: ilk-byte her zaman 0x30 ( SEQUENCE)."""
    assert _der_seq(b"a", b"b")[0] == 0x30


def test_der_seq_bos():
    """ORTAM: bos-parca -> 30 00."""
    assert _der_seq().hex() == "3000"


def test_der_seq_tek():
    assert _der_seq(b"\x02\x01\x05").hex() == "3003020105"


def test_der_seq_uzun_icerik():
    """ORTAM: 200-byte icerik -> uzun-form length."""
    got = _der_seq(b"x" * 200)
    assert got[1:3] == b"\x81\xc8"


def test_der_seq_donut_bytes():
    assert isinstance(_der_seq(b"a"), bytes)


def test_der_seq_stabil():
    assert _der_seq(b"a", b"b") == _der_seq(b"a", b"b")


# == _der_int =========================================================================================

@pytest.mark.parametrize("v,hex_bek", [(0, "020100"), (1, "020101"),
                                       (127, "02017f"), (128, "02020080"),
                                       (255, "020200ff"), (256, "02020100"),
                                       (65535, "020300ffff"),
                                       (16777215, "020400ffffff"),
                                       (4294967296, "02050100000000")])
def test_der_int_tablo(v, hex_bek):
    """ORTAM: INTEGER tag 0x02; (bit_length+8)//8 byte ( pozitif-isaret
    padding'i icin +1-byte)."""
    assert _der_int(v).hex() == hex_bek


def test_der_int_tag():
    """ORTAM: INTEGER tag 0x02."""
    assert _der_int(1)[0] == 0x02


def test_der_int_sifir_ozel():
    """ORTAM-OGRENDI: 0 -> 02 01 00 ( OZEL-DURUM; to_bytes(0-byte)
    basarisiz olurdu)."""
    assert _der_int(0).hex() == "020100"


def test_der_int_pozitif_isaret_padding():
    """ORTAM-OGRENDI: 128 -> 02 02 00 80 — onde-SIFIR byte ZORUNLU
    ( yoksa 0x80 MSB-set = negatif-isaret yorumlanir; DER pozitif-tamsayi
    kurali)."""
    assert _der_int(128).hex() == "02020080"
    assert _der_int(255).hex() == "020200ff"
    assert _der_int(127).hex() == "02017f"  # 127 icin padding GEREKMEZ


def test_der_int_isaret_bit_limit():
    """ORTAM: 127 MSB-set DEGIL ( 0x7F) -> tek-byte; 128 MSB-set -> 2-byte."""
    assert _der_int(127)[2:] == b"\x7f"
    assert _der_int(128)[2:] == b"\x00\x80"


def test_der_int_negatif_hata():
    """ORTAM-OGRENDI: -1 -> OverflowError ( signed=False; NEGATIF
    desteklenmez — TSA nonce/imza-degerleri pozitif sayilir)."""
    with pytest.raises(OverflowError):
        _der_int(-1)


def test_der_int_donut_bytes():
    assert isinstance(_der_int(1), bytes)


def test_der_int_stabil():
    assert _der_int(42) == _der_int(42)


def test_der_int_buyuk():
    """ORTAM: 2^32 -> 02 05 01 00 00 00 00 ( 5-byte)."""
    assert _der_int(2 ** 32).hex() == "02050100000000"


# == _der_oid =========================================================================================

def test_der_oid_rsa():
    """ORTAM: 1.2.840.113549 ( RSA) -> bilinen DER degeri."""
    assert _der_oid("1.2.840.113549").hex() == "06062a864886f70d"


def test_der_oid_sha256():
    """ORTAM: 2.16.840.1.101.3.4.2.1 ( SHA-256) — TSA sabit degeri."""
    assert _der_oid("2.16.840.1.101.3.4.2.1").hex() == \
        "0609608648016503040201"


def test_der_oid_tag():
    """ORTAM: OBJECT IDENTIFIER tag 0x06."""
    assert _der_oid("1.2.3")[0] == 0x06


def test_der_oid_ilk_arc():
    """ORTAM: ilk-2-arc tek-byte ( 1*40+2 = 42 = 0x2a)."""
    assert _der_oid("1.2.3")[2] == 42


def test_der_oid_kisa():
    """ORTAM: 1.2.840 -> 2a 86 48 ( 840 = 0x348; 0x86 0x48 base-128)."""
    assert _der_oid("1.2.840").hex() == "06032a8648"


def test_der_oid_base128_uzun_arc():
    """ORTAM: buyuk arc -> coklu-base-128 byte ( 0x80| devam biti)."""
    got = _der_oid("1.2.840.113549")
    assert 0x86 in got  # devam-bit set


def test_der_oid_donut_bytes():
    assert isinstance(_der_oid("1.2.3"), bytes)


def test_der_oid_stabil():
    assert _der_oid("1.2.840.113549") == _der_oid("1.2.840.113549")


def test_der_oid_sifir_arc():
    """ORTAM: 0.0 -> 00."""
    assert _der_oid("0.0").hex() == "060100"


def test_der_oid_iki_arc():
    """ORTAM: 2-arc OID -> sadece 1-byte govde."""
    assert len(_der_oid("1.2")) == 3  # tag + len + 1 byte


# == _encode_value ====================================================================================

def test_encode_bytes():
    """ORTAM: bytes -> {'__bytes__': hex} isareti."""
    assert _encode_value(b"\x00\xff") == {"__bytes__": "00ff"}


def test_encode_bytes_bos():
    assert _encode_value(b"") == {"__bytes__": ""}


def test_encode_bytes_ascii():
    assert _encode_value(b"abc") == {"__bytes__": "616263"}


def test_encode_passthrough_int():
    """ORTAM: bytes-DISI degerler OLDUGU-GIBI ( JSON-safe)."""
    assert _encode_value(5) == 5


def test_encode_passthrough_str():
    assert _encode_value("merhaba") == "merhaba"


def test_encode_passthrough_none():
    assert _encode_value(None) is None


def test_encode_passthrough_bool():
    assert _encode_value(True) is True


def test_encode_passthrough_float():
    assert _encode_value(1.5) == 1.5


def test_encode_passthrough_list():
    """ORTAM-OGRENDI: liste ICINDEKI bytes DONUSTURULMEZ ( sadece tep-
    teki deger; recursive DEGIL)."""
    v = _encode_value([1, b"a"])
    assert v == [1, b"a"]


def test_encode_passthrough_dict():
    """ORTAM: dict passthrough ( sadece bytes isaretlenir)."""
    assert _encode_value({"a": 1}) == {"a": 1}


def test_encode_donut():
    assert _encode_value(b"x") == {"__bytes__": "78"}


def test_encode_stabil():
    assert _encode_value(b"\x01") == _encode_value(b"\x01")


# == _decode_value ====================================================================================

def test_decode_isaret():
    """ORTAM: {'__bytes__': hex} -> bytes."""
    assert _decode_value({"__bytes__": "00ff"}) == b"\x00\xff"


def test_decode_bos_isaret():
    assert _decode_value({"__bytes__": ""}) == b""


def test_decode_isaret_turkce():
    """ORTAM: UTF-8 hex ( 'ç' = c3a7)."""
    assert _decode_value({"__bytes__": "c3a7"}) == "ç".encode()


def test_decode_passthrough_int():
    assert _decode_value(5) == 5


def test_decode_passthrough_str():
    assert _decode_value("x") == "x"


def test_decode_passthrough_none():
    assert _decode_value(None) is None


def test_decode_passthrough_dict():
    assert _decode_value({"a": 1}) == {"a": 1}


def test_decode_ekstra_anahtar_passthrough():
    """ORTAM-OGRENDI: set(v) == {'__bytes__'} — TAM-ESLESME zorunlu;
    ekstra-anahtar varsa passthrough ( isaret olarak yorumlanMAZ)."""
    v = {"__bytes__": "00", "x": 1}
    assert _decode_value(v) == v
    assert not isinstance(_decode_value(v), bytes)


def test_decode_recursive_degil():
    """ORTAM-OGRENDI: IC-ICE dict'ler DECODE EDILMEZ ( recursive DEGIL —
    export/import bundle sadece tep-teki isaretleri isler)."""
    assert _decode_value({"k": {"__bytes__": "41"}}) == \
        {"k": {"__bytes__": "41"}}


def test_decode_donut_bytes():
    assert isinstance(_decode_value({"__bytes__": "41"}), bytes)


def test_decode_stabil():
    assert _decode_value({"__bytes__": "41"}) == \
        _decode_value({"__bytes__": "41"})


def test_decode_isaret_olmayan_dict():
    """ORTAM: {'__bytes__': 12345} ( hex-degil) -> fromhex ValueError."""
    with pytest.raises(ValueError):
        _decode_value({"__bytes__": "zz"})


# == round-trip =======================================================================================

@pytest.mark.parametrize("b", [b"", b"\x00", b"\xff", b"abc",
                               b"\xde\xad\xbe\xef", "çğ".encode(), b"x" * 100])
def test_round_trip_bytes(b):
    """ORTAM: encode-decode round-trip ( JSON-safe bundle)."""
    assert _decode_value(_encode_value(b)) == b


@pytest.mark.parametrize("v", [0, 1, -5, 1.5, "metin", None, True, [1, 2]])
def test_round_trip_passthrough(v):
    """ORTAM: JSON-safe degerler round-trip ( degisim-YOK)."""
    assert _decode_value(_encode_value(v)) == v


def test_round_trip_karisik():
    """ORTAM: dict icinde bytes isareti ( export_bundle satir-sema)."""
    row = {"id": 1, "blob": _encode_value(b"\x01\x02"), "ad": "x"}
    decoded = {k: _decode_value(v) for k, v in row.items()}
    assert decoded == {"id": 1, "blob": b"\x01\x02", "ad": "x"}


# == karakterizasyon ===================================================================================

def test_der_amaci():
    r"""ORTAM-OGRENDI (DOCSTACK): elle-yazilmis ASN.1-DER ( RFC 3160 TSA
icin; dis-bagimlilik YOK); _der_len kisa-form (<0x80) / uzun-form
(0x80|nbytes, MINIMAL); _der_int OZEL-DURUM 0 ( 02 01 00) ve pozitif-
isaret-padding ( 128 -> 00 80; yoksa 0x80 MSB negatif-okunur); NEGATIF
OverflowError ( signed=False); _der_oid base-128 arc-kodlamasi ( 0x80
devam-bit)."""
    assert _der_len(128).hex() == "8180"
    assert _der_int(128).hex() == "02020080"
    assert _der_int(0).hex() == "020100"
    assert _der_oid("2.16.840.1.101.3.4.2.1").hex() == "0609608648016503040201"


def test_bundle_amaci():
    r"""ORTAM-OGRENDI (DOCSTACK): export_bundle JSON-safe.dump — BLOB'lar
{'__bytes__': hex} isaretine; _decode_value TAM-ANAHTAR-ESLESME zorunlu
( ekstra-anahtar -> passthrough); RECURSIVE DEGIL ( ic-ice dict'ler
decode-EDILMEZ); bozuk-hex -> ValueError."""
    assert _encode_value(b"\x00\xff") == {"__bytes__": "00ff"}
    assert _decode_value({"__bytes__": "00ff"}) == b"\x00\xff"
    assert _decode_value({"__bytes__": "00", "x": 1}) == \
        {"__bytes__": "00", "x": 1}
