"""Otonom dal-kesen testler — hedef: ``swarmax.ed25519._secret_expand``

Kapsam: 32 bayt Ed25519 seed'ini (skaler, prefix) ikilisine ayirma ve
RFC 8032 clamping kurallari. Fonksiyonun tum dallari:

  1. len(secret) != 32            -> ValueError("Ed25519 seed must be 32 bytes")
  2. len(secret) == 32            -> (a, prefix) doner
       a   = int.from_bytes(sha512(secret)[:32], "little")
             & (2**254 - 8)   (bit 0-2 ve 254+ temizlenir)
             | (2**254)       (bit 254 set edilir)
       prefix = sha512(secret)[32:]

Üretim koduna ASLA DOKUNULMADI; bu dosya yalnizca tests/ altinda olusturuldu.

Dis-bagimsiz oracle: RFC 8032 §7.1 resmi test vektorleri ve denetlenmis
`cryptography` kutuphanesi ile capraz dogrulama (known-answer tests).
"""
from __future__ import annotations

import hashlib

import pytest

import swarmax.ed25519 as ed

# ---------------------------------------------------------------------------
# Sabitlenmis beklenen degerler (cryptography kutuphanesi ile dogrulanmis)
# ---------------------------------------------------------------------------

# sha512(32x\x00) uzerinden clamping sonucu
ZERO_A = 39325648866980652792715009169219496062012184734522019333892538943312776480336
ZERO_PREFIX_HEX = "0a6a85eaa642dac835424b5d7c8d637c00408c7a73da672b7f498521420b6dd3"

# sha512(32x\ff) uzerinden clamping sonucu
FF_A = 39371077513769127227060204837748737807597105403927536657969425011750052941088
FF_PREFIX_HEX = "9b4522968797885508e64703de1cc0593063264b74b588f71b7de0161f21cf29"

# RFC 8032 §7.1 resmi vektorleri (seed, public key, mesaj)
RFC_8032_VECTORS = [
    (
        "9d61b19deff52181de4d4021a206b16d4f9a2d5d5c3f2f4b7d9b5e1f8f7e6d5c",
        "fcba2c3381092c6d7fb094182e74f43dcdf0aba4ab46abb16a86b91e76ea076c",
        b"",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        b"\x72",
    ),
    (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        b"\xaf\x82",
    ),
]

# Unicode yuklu Turkce metinler (UTF-8 olarak 32 bayttan KISA — pad gerekir)
TR_TEXTS = ["İstanbul-ajan-2026!", "çağlaÜmitŞiir"]


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------


def _tr_seed(text: str) -> bytes:
    """Turkce metinden deterministik 32 bayt seed (sha256)."""
    return hashlib.sha256(text.encode("utf-8")).digest()


# ---------------------------------------------------------------------------
# A. Dal 1: uzunluk kontrolu — kisa seed'ler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [0, 16, 31])
def test_kisa_seed_valueerror(n):
    """32 bayttan kisa seed ValueError firlatmali."""
    with pytest.raises(ValueError):
        ed._secret_expand(b"a" * n)


@pytest.mark.parametrize("n", [33, 64, 100])
def test_uzun_seed_valueerror(n):
    """32 bayttan uzun seed ValueError firlatmali."""
    with pytest.raises(ValueError):
        ed._secret_expand(b"a" * n)


def test_hata_mesaji_icerigi():
    """Hata mesaji "32 bytes" icermeli (sozlesme)."""
    with pytest.raises(ValueError, match="32 bytes"):
        ed._secret_expand(b"kisa")


def test_hata_tipi_valueerror():
    """Yanlis tip TypeError DEGIL, ValueError olmali."""
    with pytest.raises(ValueError):
        ed._secret_expand(bytes(31))


# ---------------------------------------------------------------------------
# B. Dal 2: gecerli 32 bayt — cikti yapisi
# ---------------------------------------------------------------------------


def test_32_bayt_kabul_edilir():
    """Tam 32 bayt seed (int, bytes) ikilisi dondurur."""
    res = ed._secret_expand(bytes(32))
    assert isinstance(res, tuple)
    assert len(res) == 2


def test_ilk_eleman_int():
    """Donen ilk eleman bir int (skaler)."""
    a, _ = ed._secret_expand(bytes(32))
    assert isinstance(a, int)


def test_ikinci_eleman_bytes():
    """Donen ikinci eleman bytes (nonce prefix)."""
    _, prefix = ed._secret_expand(bytes(32))
    assert isinstance(prefix, bytes)


def test_prefix_uzunlugu_32_bayt():
    """prefix tam 32 bayt olmali (sha512'nin ikinci yarisi)."""
    _, prefix = ed._secret_expand(bytes(32))
    assert len(prefix) == 32


# ---------------------------------------------------------------------------
# C. Clamping invariantlari (RFC 8032)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [bytes(32), b"\xff" * 32, _tr_seed(TR_TEXTS[0])])
def test_a_dusuk_uc_bit_temizlenmis(seed):
    """a % 8 == 0 — RFC 8032 clamping: bit 0-2 temizlenir."""
    a, _ = ed._secret_expand(seed)
    assert a % 8 == 0
    assert a & 0b111 == 0


@pytest.mark.parametrize("seed", [bytes(32), b"\xff" * 32])
def test_a_bit_254_set_edilmis(seed):
    """bit 254 set edilmeli (RFC 8032: a[31] |= 64)."""
    a, _ = ed._secret_expand(seed)
    assert (a >> 254) & 1 == 1


@pytest.mark.parametrize("seed", [bytes(32), b"\xff" * 32])
def test_a_bit_255_temizlenmis(seed):
    """bit 255 temizlenmeli (RFC 8032: a[31] &= 127) — a < 2**255."""
    a, _ = ed._secret_expand(seed)
    assert a < 2**255
    assert (a >> 255) & 1 == 0


@pytest.mark.parametrize("seed", [bytes(32), b"\xff" * 32])
def test_clamping_idempotandir(seed):
    """a uzerinde clamping tekrar edilmemeli (a zaten clamp edilmis)."""
    a, _ = ed._secret_expand(seed)
    reclamped = (a & ((1 << 254) - 8)) | (1 << 254)
    assert reclamped == a


def test_clamping_mask_degerleri():
    """Mask (2**254 - 8) ve set biti (2**254) sabitleri dogru olmali."""
    mask = (1 << 254) - 8
    # mask: bit 0-2 sifir, bit 3..253 bir, bit 254+ sifir
    assert mask & 0b111 == 0
    assert mask.bit_length() == 254
    assert (1 << 254) & mask == 0


# ---------------------------------------------------------------------------
# D. Sabitlenmis known-answer degerleri
# ---------------------------------------------------------------------------


def test_sifir_seed_sabit_deger():
    """bytes(32) seed icin skaler ve prefix sabitleri eslesmeli."""
    a, prefix = ed._secret_expand(bytes(32))
    assert a == ZERO_A
    assert prefix.hex() == ZERO_PREFIX_HEX


def test_tum_ff_seed_sabit_deger():
    """b'\\xff'*32 seed icin skaler ve prefix sabitleri eslesmeli."""
    a, prefix = ed._secret_expand(b"\xff" * 32)
    assert a == FF_A
    assert prefix.hex() == FF_PREFIX_HEX


def test_sifir_seed_prefix_sha512_ile_tutarli():
    """prefix, sha512(bytes(32))[32:] ile birebir ayni olmali."""
    h = hashlib.sha512(bytes(32)).digest()
    _, prefix = ed._secret_expand(bytes(32))
    assert prefix == h[32:]


def test_sifir_seed_skaler_sha512_den_hesaplanabilir():
    """a, sha512'in ilk 32 baytindan bagimsiz hesapla elde edilebilmeli."""
    h = hashlib.sha512(bytes(32)).digest()
    ref_a = int.from_bytes(h[:32], "little")
    ref_a &= (1 << 254) - 8
    ref_a |= (1 << 254)
    assert ed._secret_expand(bytes(32))[0] == ref_a


# ---------------------------------------------------------------------------
# E. RFC 8032 resmi vektorleri (dis-bagimsiz known-answer)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed_hex,pub_hex,message", RFC_8032_VECTORS)
def test_rfc8032_public_key_turetimi(seed_hex, pub_hex, message):
    """secret_to_public(seed) RFC 8032 reference public key ile eslesmeli.

    _secret_expand'in ciktisi _point_mul(G) ile birlestiginde resmi vektoru
    vermeli; bu butun zinciri (expand + clamp + skaler carpma + compress)
    dis-bagimsiz dogrular.
    """
    seed = bytes.fromhex(seed_hex)
    assert ed.secret_to_public(seed).hex() == pub_hex


@pytest.mark.parametrize("seed_hex,pub_hex,message", RFC_8032_VECTORS)
def test_rfc8032_imza_ve_dogrulama(seed_hex, pub_hex, message):
    """sign + verify zinciri vektor mesajlari icin calismali."""
    seed = bytes.fromhex(seed_hex)
    pub = bytes.fromhex(pub_hex)
    sig = ed.sign(seed, message)
    assert len(sig) == 64
    assert ed.verify(pub, message, sig) is True
    assert ed.verify(pub, message + b"x", sig) is False


def test_rfc8032_bos_mesaj_vektoru():
    """TEST 1: bos mesaj icin imza uretilip dogrulanabilmeli."""
    seed = bytes.fromhex(RFC_8032_VECTORS[0][0])
    pub = bytes.fromhex(RFC_8032_VECTORS[0][1])
    sig = ed.sign(seed, b"")
    assert ed.verify(pub, b"", sig) is True


# ---------------------------------------------------------------------------
# F. cryptography kutuphanesi ile capraz dogrulama
# ---------------------------------------------------------------------------


def test_cryptography_ile_ayni_public_key():
    """Denetlenmis kutuphane ayni seed icin ayni public key uretmeli."""
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    for seed_hex, pub_hex, _ in RFC_8032_VECTORS:
        seed = bytes.fromhex(seed_hex)
        priv = crypto.Ed25519PrivateKey.from_private_bytes(seed)
        assert priv.public_key().public_bytes_raw().hex() == pub_hex
        assert ed.secret_to_public(seed).hex() == pub_hex


def test_cryptography_imzalarini_dogrular():
    """Üretim verify(), cryptography tarafindan uretilen imzayi kabul etmeli."""
    crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    seed = bytes.fromhex(RFC_8032_VECTORS[1][0])
    pub = bytes.fromhex(RFC_8032_VECTORS[1][1])
    priv = crypto.Ed25519PrivateKey.from_private_bytes(seed)
    msg = b"cross-check payload"
    assert ed.verify(pub, msg, priv.sign(msg)) is True


# ---------------------------------------------------------------------------
# G. Determinizm ve bagimsizlik
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", TR_TEXTS)
def test_deterministik_cikti(text):
    """Ayni seed her zaman ayni (a, prefix) ikilisini vermeli."""
    seed = _tr_seed(text)
    assert ed._secret_expand(seed) == ed._secret_expand(seed)


def test_farkli_seed_farkli_cikti():
    """Farkli seed'ler farkli (a, prefix) uretmeli."""
    s1, s2 = bytes(32), bytes(range(32))
    assert ed._secret_expand(s1) != ed._secret_expand(s2)


@pytest.mark.parametrize("text", TR_TEXTS)
def test_a_sadece_ilk_yariya_bagli(text):
    """a yalnizca sha512(seed)[:32]'den gelmeli; prefix digar yari."""
    seed = _tr_seed(text)
    h = hashlib.sha512(seed).digest()
    a, prefix = ed._secret_expand(seed)
    assert prefix == h[32:]
    assert int.from_bytes(h[32:], "little") != a  # yarilar bagimsiz


@pytest.mark.parametrize("text", TR_TEXTS)
def test_tek_bayt_farki_hem_a_hem_prefix_degistir(text):
    """Seed'in tek bayti hem a'yi hem prefix'i degistirmeli."""
    seed = bytearray(_tr_seed(text))
    a0, p0 = ed._secret_expand(bytes(seed))
    seed[7] ^= 0xFF
    a1, p1 = ed._secret_expand(bytes(seed))
    assert a0 != a1
    assert p0 != p1


# ---------------------------------------------------------------------------
# H. Unicode / Turkce seed'ler ile clamping ve anahtar turetimi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", TR_TEXTS)
def test_turkce_seed_clamping_kurallari(text):
    """Turkce metinden turetilen seed clamping kurallarini saglamali."""
    a, _ = ed._secret_expand(_tr_seed(text))
    assert a % 8 == 0
    assert (a >> 254) & 1 == 1
    assert a < 2**255
    assert isinstance(a, int)


@pytest.mark.parametrize("text", TR_TEXTS)
def test_turkce_seed_public_key_gecerli(text):
    """Turkce seed'den turetilen public key 32 bayt ve decompress edilebilir."""
    pub = ed.secret_to_public(_tr_seed(text))
    assert len(pub) == 32
    assert ed.point_decompress(pub) is not None


@pytest.mark.parametrize("text", TR_TEXTS)
def test_turkce_seed_imza_dogrulama(text):
    """Turkce seed ile imzalanmis mesaj dogrulanabilmeli."""
    seed = _tr_seed(text)
    pub = ed.secret_to_public(seed)
    msg = "Türkçe mesaj — ğüşıöç İ".encode("utf-8")
    sig = ed.sign(seed, msg)
    assert ed.verify(pub, msg, sig) is True
    assert ed.verify(pub, b"farkli", sig) is False


@pytest.mark.parametrize(
    "msg",
    [
        "",
        "İstanbul",
        "çağla",
        "Ümit",
        "Ελληνικά",
    ],
)
def test_unicode_mesaj_imza_dogrulama(msg):
    """Çesitli unicode (TR/JQ/RU/EL) mesajlar icin imza round-trip."""
    seed = _tr_seed(TR_TEXTS[0])
    pub = ed.secret_to_public(seed)
    data = msg.encode("utf-8")
    sig = ed.sign(seed, data)
    assert ed.verify(pub, data, sig) is True


def test_turkce_metin_ham_seed_cok_kisa_ise_hata():
    """Ham UTF-8'i 32 bayti asan Turkce metin dogrudan seed olarak hata vermeli."""
    long_text = "İstanbul" * 10  # 90 bayt
    assert len(long_text.encode("utf-8")) > 32
    with pytest.raises(ValueError):
        ed._secret_expand(long_text.encode("utf-8"))


# ---------------------------------------------------------------------------
# I. Sinir degerler
# ---------------------------------------------------------------------------


def test_bytearray_kabul_edilir():
    """bytes disinda bytearray da calismali (duck-typing)."""
    a, prefix = ed._secret_expand(bytearray(32))
    assert a == ZERO_A
    assert prefix.hex() == ZERO_PREFIX_HEX


def test_tum_bayt_degerleri_32_bayt_kabul():
    """0..255 tum degerlerini iceren 32 bayt seed gecerli olmali."""
    a, prefix = ed._secret_expand(bytes(range(32)))
    assert isinstance(a, int) and isinstance(prefix, bytes)
    assert a % 8 == 0 and a < 2**255


def test_a_pozitif_ve_sifir_degil():
    """Clamping sonrasi a her zaman pozitif ve sifirdan farkli olmali."""
    for seed in (bytes(32), b"\xff" * 32, bytes(range(32))):
        a, _ = ed._secret_expand(seed)
        assert a > 0
        assert a >= (1 << 254)  # bit 254 set oldugu icin alt sinir


# ---------------------------------------------------------------------------
# J. secret_to_public ile tum zincerin entegrasyonu
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed_hex,pub_hex,message", RFC_8032_VECTORS)
def test_zincir_secret_expand_point_mul_compress(seed_hex, pub_hex, message):
    """secret_to_public = compress(point_mul(a, G)); ara adimlar dogrulanmali."""
    seed = bytes.fromhex(seed_hex)
    a, _prefix = ed._secret_expand(seed)
    pt = ed._point_mul(a, ed.G)
    assert ed.point_compress(pt).hex() == pub_hex
    assert ed.secret_to_public(seed).hex() == pub_hex
