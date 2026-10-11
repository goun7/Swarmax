"""test_ed25519_crypto_dallar.py — 6-fonksiyon dal-kesen test suite.

ORTAM-ANATOMI (swarmax/ed25519.py, RFC 8032 pure-Python Ed25519):
  _sha512(s)            -> hashlib.sha512(s).digest()                      (L16)
  _sha512_modq(s)       -> int.from_bytes(_sha512(s),"little") % Q          (L27)
  secret_to_public(sk)  -> a,_ = _secret_expand(sk); point_compress(_point_mul(a,G))  (L89)
  generate_seed()       -> os.urandom(32)                                  (L113)
  sign(sk,msg)          -> Rs || int.to_bytes(s,32,"little"); s=(r+h*a)%Q  (L117)
  verify(pk,msg,sig)    -> _point_equal(sB, R + hA) — NON-COFACTORED       (L128)

ORTAM-OGRENDILER:
  (1) sign/verify/secret_to_public cryptography 50.0.2 ile BITES-ESIT
      (RFC 8032 uyumlu, real Ed25519 — test vektorleri canli uretilir).
  (2) QUIRK/CHARACTERIZATION: verify NON-COFACTORED (sB == R + hA, [8]sKATLI
      YOK). Kimlik-noktasi (x=0,y=1) public-key ile R=sG, s=sig[32:] imzasi
      HERHANGI bir mesajda DOGRULANIR (hA = identity, sB == R) — cryptography
      DE kabul eder (EdDSA'nin degenerate-key ozelligi, swarmax'a ozel DEGIL).
  (3) verify: len(pk)!=32 veya len(sig)!=64 -> False; s >= Q -> False;
      dekompres-edilemeyen pk/R -> None -> False.
  (4) sign deterministik (EdDSA) — ayni (sk,msg) hep ayni 64 bayt.
  (5) generate_seed os.urandom(32) passthrough — monkeypatch ile kanitli.
  (6) _sha512_modq her zaman [0, Q) araliginda (reduksiyon garantisi).

Kural-1: SADECE yeni test dosyasi; production DOKUNULMADI. Kural-4: saf
in-memory crypto (network/subprocess YASAK). --noconftest ZORUNLU (conftest
HTTP sunucusu baslatir).
"""
import hashlib
import os
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax import ed25519 as E  # noqa: E402

pytest.importorskip("cryptography", reason="cross-validation oracle icin gerekli")
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

Q = 2**252 + 27742317777372353535851937790883648493
P = 2**255 - 19

# --- sabit vektorler (probe ile toplanmis, cryptography ile teyit) ----------
SHA512_EMPTY = ("cf83e1357eefb8bdf1542850d66d8007"
                "d620e4050b5715dc83f4a921d36ce9ce"
                "47d0d13c5d85f2b0ff8318d2877eec2f"
                "63b931bd47417a81a538327af927da3e")
SHA512_ABC = ("ddaf35a193617abacc417349ae204131"
              "12e6fa4e89a97ea20a9eeee64b55d39a"
              "2192992a274fc1a836ba3c23a3feebbd"
              "454d4423643ce80e2a9ac94fa54ca49f")

SEEDS = [
    bytes(range(32)),
    bytes(32),
    bytes([0xFF] * 32),
    bytes([i % 7 for i in range(32)]),
    bytes([i * 7 % 251 for i in range(32)]),
    bytes.fromhex("9d61b19deff5a99b96e0b2c64fbd1e1c4e34cae2b2fe9d3b44c1d1e1e1e1e1e1"),
    bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"),
    bytes.fromhex("c5aa8df43f9f837bedb7445f0d0cd6bde5e0e9d3f4e8b7b2b1a5c4e8f6a2b0c8"),
]
MESSAGES = [
    b"",
    b"x",
    b"hello world",
    b"a" * 1000,
    b"\x00" * 256,
    bytes(range(256)),
    "Türkçe metin — ğüşöçıİ".encode("utf-8"),
    "日本語テスト🚀".encode("utf-8"),
    os.urandom(4096),
]


def _ref_public(seed: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _ref_sign(seed: bytes, msg: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(seed).sign(msg)


def _ref_verify(public: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(sig, msg)
        return True
    except Exception:
        return False


# ============================================================ _sha512 =======
@pytest.mark.parametrize("inp,expected", [
    (b"", SHA512_EMPTY),
    (b"abc", SHA512_ABC),
    (b"message digest",
     "107dbf389d9e9f71a3a95f6c055b9251bc5268c2be16d6c13492ea45b0199f3309e16455ab1e96118e8a905d5597b72038ddb372a89826046de66687bb420e7c"),
    (b"abcdefghijklmnopqrstuvwxyz",
     "4dbff86cc2ca1bae1e16468a05cb9881c97f1753bce3619034898faa1aabe429955a1bf8ec483d7421fe3c1646613a59ed5441fb0f321389f77f48a879c7b1f1"),
])
def test_sha512_known_answer(inp, expected):
    assert E._sha512(inp).hex() == expected


@pytest.mark.parametrize("inp", MESSAGES + [os.urandom(64) for _ in range(8)])
def test_sha512_matches_hashlib(inp):
    assert E._sha512(inp) == hashlib.sha512(inp).digest()


@pytest.mark.parametrize("inp", [b"", b"x", b"abc", os.urandom(128)])
@pytest.mark.parametrize("typ", [bytes, bytearray, memoryview])
def test_sha512_input_types(inp, typ):
    # hashlib bytes-benzeri tum girdileri kabul eder
    assert E._sha512(typ(inp)) == hashlib.sha512(typ(inp)).digest()


@pytest.mark.parametrize("inp", MESSAGES)
def test_sha512_length_is_64(inp):
    assert len(E._sha512(inp)) == 64


@pytest.mark.parametrize("inp", MESSAGES)
def test_sha512_deterministic(inp):
    assert E._sha512(inp) == E._sha512(inp)


@pytest.mark.parametrize("base", [b"", b"abc", b"hello", os.urandom(32)])
@pytest.mark.parametrize("pos", [0, 1, 31])
def test_sha512_byte_sensitive(base, pos):
    a = bytearray(base.ljust(32, b"\x00") if len(base) < 32 else base)
    if len(a) <= pos:
        a += b"\x00" * (pos + 1 - len(a))
    b2 = bytes(a)
    a[pos] ^= 0x01
    assert E._sha512(bytes(a)) != E._sha512(b2)


@pytest.mark.parametrize("text", [
    "Türkçe", "İĞÜŞÖÇ", "日本語", "🚀🎉", "café", "", "a" * 100,
])
def test_sha512_unicode_inputs(text):
    enc = text.encode("utf-8")
    assert E._sha512(enc) == hashlib.sha512(enc).digest()


def test_sha512_large_input():
    big = os.urandom(1024 * 1024)
    assert E._sha512(big) == hashlib.sha512(big).digest()


@pytest.mark.parametrize("inp", MESSAGES)
def test_sha512_hex_roundtrip(inp):
    d = E._sha512(inp)
    assert bytes.fromhex(d.hex()) == d


def test_sha512_returns_bytes_not_str():
    assert isinstance(E._sha512(b""), bytes)


# ======================================================== _sha512_modq =====
@pytest.mark.parametrize("inp", MESSAGES + [os.urandom(64) for _ in range(6)])
def test_sha512_modq_matches_definition(inp):
    assert E._sha512_modq(inp) == int.from_bytes(E._sha512(inp), "little") % Q


@pytest.mark.parametrize("inp", MESSAGES + [os.urandom(64) for _ in range(6)])
def test_sha512_modq_reduced_below_q(inp):
    assert 0 <= E._sha512_modq(inp) < Q


def test_sha512_modq_empty_known():
    assert E._sha512_modq(b"") == int.from_bytes(bytes.fromhex(SHA512_EMPTY), "little") % Q


def test_sha512_modq_abc_known():
    assert E._sha512_modq(b"abc") == int.from_bytes(bytes.fromhex(SHA512_ABC), "little") % Q


@pytest.mark.parametrize("inp", MESSAGES)
def test_sha512_modq_deterministic(inp):
    assert E._sha512_modq(inp) == E._sha512_modq(inp)


@pytest.mark.parametrize("base", [b"abc", b"hello", os.urandom(32)])
def test_sha512_modq_byte_sensitive(base):
    alt = bytes([base[0] ^ 0x01]) + base[1:]
    assert E._sha512_modq(alt) != E._sha512_modq(base)


def test_sha512_modq_returns_int():
    assert isinstance(E._sha512_modq(b""), int)


def test_sha512_modq_is_not_raw_hash_int():
    # ham SHA-512 ciktisi 512 bit — modq sonrasi 252 bitten az
    raw = int.from_bytes(E._sha512(b"hello"), "little")
    assert E._sha512_modq(b"hello") != raw
    assert E._sha512_modq(b"hello").bit_length() < Q.bit_length()


# ====================================================== secret_to_public ====
@pytest.mark.parametrize("seed", SEEDS)
def test_secret_to_public_matches_cryptography(seed):
    assert E.secret_to_public(seed) == _ref_public(seed)


@pytest.mark.parametrize("seed", SEEDS)
def test_secret_to_public_length_32(seed):
    pk = E.secret_to_public(seed)
    assert len(pk) == 32
    assert isinstance(pk, bytes)


@pytest.mark.parametrize("seed", SEEDS)
def test_secret_to_public_decompressable(seed):
    # her uretilen public-key gecerli egri noktasi (order-L alt-grup)
    pt = E.point_decompress(E.secret_to_public(seed))
    assert pt is not None
    # [8]nokta = [8]G*a ile ayni (cofactor-L alt-grubunda)
    a, _ = E._secret_expand(seed)
    assert E._point_equal(pt, E._point_mul(a, E.G))


@pytest.mark.parametrize("seed", SEEDS)
def test_secret_to_public_matches_definition(seed):
    a, _ = E._secret_expand(seed)
    assert E.secret_to_public(seed) == E.point_compress(E._point_mul(a, E.G))


@pytest.mark.parametrize("seed", SEEDS)
def test_secret_to_public_deterministic(seed):
    assert E.secret_to_public(seed) == E.secret_to_public(seed)


@pytest.mark.parametrize("bad_len", [0, 1, 16, 31, 33, 48, 64, 128])
def test_secret_to_public_rejects_non_32_seed(bad_len):
    with pytest.raises(ValueError):
        E.secret_to_public(os.urandom(bad_len))


def test_secret_to_public_all_zero_seed():
    # simetrik degil: sifir-seed gecerli bir anahtar uretir
    pk = E.secret_to_public(bytes(32))
    assert pk == _ref_public(bytes(32))
    assert pk != bytes(32)


def test_secret_to_public_high_bit_seed():
    seed = bytes([0xFF] * 32)
    assert E.secret_to_public(seed) == _ref_public(seed)


@pytest.mark.parametrize("i", range(6))
def test_secret_to_public_distinct_for_distinct_seeds(i):
    s1, s2 = os.urandom(32), os.urandom(32)
    assert s1 != s2
    assert E.secret_to_public(s1) != E.secret_to_public(s2)


def test_secret_to_public_depends_on_seed_bytes():
    seed = bytes(range(32))
    flipped = bytes([seed[0] ^ 0x80]) + seed[1:]
    assert E.secret_to_public(seed) != E.secret_to_public(flipped)


def test_secret_to_public_never_identity():
    # clamped skaler 0 olamaz (bit-254 set) -> public-key kimlik-noktasi degil
    for seed in SEEDS:
        pt = E.point_decompress(E.secret_to_public(seed))
        assert not E._point_equal(pt, (0, 1, 1, 0))


# ========================================================= generate_seed ====
@pytest.mark.parametrize("i", range(8))
def test_generate_seed_length(i):
    seed = E.generate_seed()
    assert len(seed) == 32


def test_generate_seed_returns_bytes():
    assert isinstance(E.generate_seed(), bytes)


def test_generate_seed_distinct_across_calls():
    seeds = {E.generate_seed() for _ in range(100)}
    assert len(seeds) == 100


def test_generate_seed_has_high_entropy():
    data = b"".join(E.generate_seed() for _ in range(32))
    assert len(set(data)) >= 200  # 1024 baytta en az 200 farkli bayt degeri


def test_generate_seed_bit_balance():
    seed = E.generate_seed()
    bits = sum(bin(b).count("1") for b in seed)
    assert 40 < bits < 216  # asiri dengesiz (tum-0/tum-1) degil


def test_generate_seed_uses_os_urandom(monkeypatch):
    calls = []

    def fake_urandom(n):
        calls.append(n)
        return b"\xAB" * n

    monkeypatch.setattr(os, "urandom", fake_urandom)
    assert E.generate_seed() == b"\xAB" * 32
    assert calls == [32]


def test_generate_seed_passthrough_fixed_value(monkeypatch):
    fixed = bytes(range(32))
    monkeypatch.setattr(os, "urandom", lambda n: fixed)
    assert E.generate_seed() == fixed


def test_generate_seed_feeds_secret_to_public():
    seed = E.generate_seed()
    assert len(E.secret_to_public(seed)) == 32


def test_generate_seed_is_not_str():
    assert not isinstance(E.generate_seed(), str)


# ================================================================= sign =====
@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:5] for m in MESSAGES[:5]])
def test_sign_output_length_64(seed, msg):
    assert len(E.sign(seed, msg)) == 64


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:6]])
def test_sign_matches_cryptography(seed, msg):
    assert E.sign(seed, msg) == _ref_sign(seed, msg)


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:6]])
def test_sign_deterministic(seed, msg):
    assert E.sign(seed, msg) == E.sign(seed, msg)


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:6]])
def test_sign_structure_R_decompressable(seed, msg):
    sig = E.sign(seed, msg)
    assert E.point_decompress(sig[:32]) is not None


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:6]])
def test_sign_scalar_below_q(seed, msg):
    s = int.from_bytes(sig[32:], "little") if (sig := E.sign(seed, msg)) else None
    assert 0 <= s < Q


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:6]])
def test_sign_scalar_little_endian_encoding(seed, msg):
    sig = E.sign(seed, msg)
    s = int.from_bytes(sig[32:], "little")
    assert sig[32:] == s.to_bytes(32, "little")


@pytest.mark.parametrize("bad_len", [0, 1, 31, 33, 64])
def test_sign_rejects_non_32_seed(bad_len):
    with pytest.raises(ValueError):
        E.sign(os.urandom(bad_len), b"msg")


@pytest.mark.parametrize("seed", SEEDS[:4])
def test_sign_message_sensitive(seed):
    base = b"message content"
    alt = bytes([base[0] ^ 0x01]) + base[1:]
    assert E.sign(seed, base) != E.sign(seed, alt)


@pytest.mark.parametrize("seed", SEEDS[:4])
def test_sign_key_sensitive(seed):
    other = bytes([seed[0] ^ 0x01]) + seed[1:]
    assert E.sign(seed, b"msg") != E.sign(other, b"msg")


@pytest.mark.parametrize("msg", [b"", b"a" * (1024 * 1024), os.urandom(8192)])
def test_sign_extreme_message_lengths(msg):
    seed = bytes(range(32))
    sig = E.sign(seed, msg)
    assert len(sig) == 64
    assert E.verify(E.secret_to_public(seed), msg, sig)


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:3] for m in MESSAGES[:4]])
def test_sign_R_matches_point_mul_r(seed, msg):
    # anatomi: R = r*G, r = H(prefix || msg) mod q
    _, prefix = E._secret_expand(seed)
    r = E._sha512_modq(prefix + msg)
    assert E.sign(seed, msg)[:32] == E.point_compress(E._point_mul(r, E.G))


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:3] for m in MESSAGES[:4]])
def test_sign_scalar_equation(seed, msg):
    # anatomi: s = (r + h*a) mod q
    a, prefix = E._secret_expand(seed)
    sig = E.sign(seed, msg)
    r = E._sha512_modq(prefix + msg)
    A = E.secret_to_public(seed)
    h = E._sha512_modq(sig[:32] + A + msg)
    s = int.from_bytes(sig[32:], "little")
    assert s == (r + h * a) % Q


# ================================================================ verify ====
@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:5] for m in MESSAGES[:6]])
def test_verify_accepts_own_signature(seed, msg):
    pk = E.secret_to_public(seed)
    assert E.verify(pk, msg, E.sign(seed, msg)) is True


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:5]])
def test_verify_cryptography_accepts_swarmax_sig(seed, msg):
    assert _ref_verify(E.secret_to_public(seed), msg, E.sign(seed, msg))


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:5]])
def test_verify_accepts_cryptography_sig(seed, msg):
    pk = E.secret_to_public(seed)
    assert E.verify(pk, msg, _ref_sign(seed, msg)) is True


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:5]])
def test_verify_tampered_message(seed, msg):
    pk = E.secret_to_public(seed)
    sig = E.sign(seed, msg)
    tampered = bytes([msg[0] ^ 0x01]) + msg[1:] if msg else b"t"
    assert E.verify(pk, tampered, sig) is False


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:4]])
@pytest.mark.parametrize("pos", [0, 15, 31, 32, 47, 63])
def test_verify_tampered_signature_byte(seed, msg, pos):
    pk = E.secret_to_public(seed)
    sig = bytearray(E.sign(seed, msg))
    sig[pos] ^= 0x01
    assert E.verify(pk, msg, bytes(sig)) is False


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:4] for m in MESSAGES[:4]])
def test_verify_wrong_public_key(seed, msg):
    sig = E.sign(seed, msg)
    other = E.secret_to_public(os.urandom(32))
    assert E.verify(other, msg, sig) is False


@pytest.mark.parametrize("seed", SEEDS[:4])
def test_verify_cross_key_signature(seed):
    msg = b"cross-key message"
    sig = E.sign(seed, msg)
    other_seed = os.urandom(32)
    pk_other = E.secret_to_public(other_seed)
    assert E.verify(pk_other, msg, sig) is False
    assert E.verify(E.secret_to_public(seed), msg, E.sign(other_seed, msg)) is False


@pytest.mark.parametrize("bad_len", [0, 1, 16, 31, 33, 64, 128])
def test_verify_rejects_wrong_public_key_length(bad_len):
    seed = bytes(range(32))
    msg = b"msg"
    sig = E.sign(seed, msg)
    assert E.verify(os.urandom(bad_len), msg, sig) is False


@pytest.mark.parametrize("bad_len", [0, 1, 31, 32, 63, 65, 128])
def test_verify_rejects_wrong_signature_length(bad_len):
    seed = bytes(range(32))
    pk = E.secret_to_public(seed)
    assert E.verify(pk, b"msg", os.urandom(bad_len)) is False


@pytest.mark.parametrize("s_val", [Q, Q + 1, Q * 2, 2**256 - 1])
def test_verify_rejects_scalar_at_least_q(s_val):
    # gecerli R + gecerli R-uzayinda s ama s >= Q -> reddet
    pk = E.secret_to_public(bytes(range(32)))
    Rs = E.point_compress(E._point_mul(12345, E.G))
    sig = Rs + s_val.to_bytes(32, "little")
    assert E.verify(pk, b"msg", sig) is False


def test_verify_rejects_undeckodable_public_key():
    # y = 0xFF..FF >= P -> _modp_recover_x None
    pk = b"\xFF" * 32
    sig = E.sign(bytes(range(32)), b"msg")
    assert E.verify(pk, b"msg", sig) is False


@pytest.mark.parametrize("y_bytes", [b"\x00" * 32, b"\x02" + b"\x00" * 31, b"\xff" * 32])
def test_verify_rejects_non_curve_public_keys(y_bytes):
    sig = E.sign(bytes(range(32)), b"msg")
    assert E.verify(y_bytes, b"msg", sig) is False


def test_verify_rejects_undeckodable_R():
    pk = E.secret_to_public(bytes(range(32)))
    bad_r = b"\xFF" * 32
    s = int.from_bytes(E.sign(bytes(range(32)), b"msg")[32:], "little")
    assert E.verify(pk, b"msg", bad_r + s.to_bytes(32, "little")) is False


def test_verify_rejects_random_R_for_real_key():
    # gecerli R noktasi ama sG != R + hA (DLP gerektiren sahtecilik)
    pk = E.secret_to_public(bytes(range(32)))
    R = E.point_compress(E._point_mul(999, E.G))
    sig = R + (777).to_bytes(32, "little")
    assert E.verify(pk, b"msg", sig) is False


# ---- CHARACTERIZATION: kimlik-anahtar evrensel-imza quirk (non-cofactored)
IDENTITY_PK = (1).to_bytes(32, "little")  # y=1, sign=0 -> x=0 -> kimlik-noktasi


def test_verify_identity_key_is_decompressable_identity():
    pt = E.point_decompress(IDENTITY_PK)
    assert pt is not None
    assert E._point_equal(pt, (0, 1, 1, 0))


@pytest.mark.parametrize("msg", [b"message-A", b"completely-different",
                                 b"", b"\x00" * 512, os.urandom(256)])
def test_verify_identity_key_universal_signature(msg):
    # QUIRK: A = kimlik -> hA = kimlik -> sB == R yeterli; mesaj ONEMLI DEGIL
    s = 12345
    sig = E.point_compress(E._point_mul(s, E.G)) + s.to_bytes(32, "little")
    assert E.verify(IDENTITY_PK, msg, sig) is True
    # cryptography DE kabul eder (EdDSA degenerate-key ozelligi)
    assert _ref_verify(IDENTITY_PK, msg, sig)


def test_verify_identity_key_rejects_mismatched_R():
    # R != sG oldugu icin kimlik-anahtar ile bile reddeder
    s = 12345
    R = E.point_compress(E._point_mul(999, E.G))  # sG degil
    sig = R + s.to_bytes(32, "little")
    assert E.verify(IDENTITY_PK, b"msg", sig) is False


def test_verify_identity_key_rejects_large_s():
    sig = E.point_compress(E._point_mul(1, E.G)) + Q.to_bytes(32, "little")
    assert E.verify(IDENTITY_PK, b"msg", sig) is False


def test_verify_return_type_is_bool():
    seed = bytes(range(32))
    pk = E.secret_to_public(seed)
    assert E.verify(pk, b"msg", E.sign(seed, b"msg")) is True
    assert E.verify(pk, b"other", E.sign(seed, b"msg")) is False
    assert isinstance(E.verify(pk, b"msg", E.sign(seed, b"msg")), bool)


@pytest.mark.parametrize("seed", SEEDS[:3])
def test_verify_rejects_signature_replay_on_wrong_message(seed):
    sig = E.sign(seed, b"original")
    pk = E.secret_to_public(seed)
    for msg in MESSAGES:
        if msg == b"original":
            continue
        assert E.verify(pk, msg, sig) is False


@pytest.mark.parametrize("seed,msg", [(s, m) for s in SEEDS[:3] for m in MESSAGES[:5]])
def test_verify_accepts_independent_sign_paths(seed, msg):
    # sign == cryptography ve verify == cryptography (cift yonlu)
    sig = E.sign(seed, msg)
    pk = E.secret_to_public(seed)
    assert E.verify(pk, msg, sig)
    assert _ref_verify(pk, msg, sig)
    assert E.verify(pk, msg, _ref_sign(seed, msg))
