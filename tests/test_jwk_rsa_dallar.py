"""test_jwk_rsa_dallar.py — _jwk_rsa_public dal-kesen test suite.

ORTAM-ANATOMI (swarmax/sso.py L75):
  _jwk_rsa_public(jwk: dict) -> tuple[int, int]:
    if jwk.get("kty") != "RSA": raise SsoError("JWK is not RSA")
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return n, e
  _b64url_decode(s): pad = "=" * (-len(s) % 4); urlsafe_b64decode(s + pad)

ORTAM-OGRENDILER:
  (1) Gercek RSA anahtarlari (cryptography 50.0.2) ile n/e BITES-ESIT
      (RFC 7518 JWK thumbprint matematigi — real crypto, in-memory).
  (2) kty != "RSA" veya kty YOK -> SsoError("JWK is not RSA").
  (3) "n"/"e" key yoksa KeyError (jwk["n"] direk erisim).
  (4) QUIRK/_b64url_decode: standard base64 '+' '/' KARAKTERLERI calisir
      (urlsafe_b64decode once -/_ -> +/ cevirir); ama alfabe-disi karakterler
      SILENTCE ATILIR (validate=False) — '!!!' -> b'' -> int 0.
  (5) QUIRK: len(s) % 4 == 1 -> binascii.Error (pad 3 olunca "A===" gecersiz).
  (6) big-endian: leading-zero baytlar degeri DEGISTIRMEZ.

Kural-1: SADECE yeni test dosyasi; production DOKUNULMADI. Kural-4: saf
in-memory crypto (network/subprocess YASAK). --noconftest ZORUNLU.
"""
import base64
import binascii
import os
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax import sso  # noqa: E402
from swarmax.sso import SsoError, _b64url_decode, _jwk_rsa_public  # noqa: E402

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def jwk(n_int: int, e_int: int, kty: str = "RSA") -> dict:
    nb = n_int.to_bytes((n_int.bit_length() + 7) // 8 or 1, "big")
    eb = e_int.to_bytes((e_int.bit_length() + 7) // 8 or 1, "big")
    return {"kty": kty, "n": b64u(nb), "e": b64u(eb)}


@pytest.mark.parametrize("bits", [1024, 2048, 3072])
def test_jwk_rsa_public_matches_cryptography(bits):
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    nums = key.private_numbers().public_numbers
    n_enc = nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
    e_enc = nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
    got = _jwk_rsa_public({"kty": "RSA", "n": b64u(n_enc), "e": b64u(e_enc)})
    assert got == (nums.n, nums.e)


@pytest.mark.parametrize("e_int", [3, 17, 65537, 2**32 + 1])
def test_jwk_rsa_public_small_exponents(e_int):
    n = (1 << 1024) - 1
    assert _jwk_rsa_public(jwk(n, e_int)) == (n, e_int)


@pytest.mark.parametrize("n_int", [1, 2, 255, 256, (1 << 512) - 1, (1 << 2048) - 1])
def test_jwk_rsa_public_modulus_magnitudes(n_int):
    e = 65537
    assert _jwk_rsa_public(jwk(n_int, e)) == (n_int, e)


def test_jwk_rsa_public_returns_tuple_of_two_ints():
    got = _jwk_rsa_public(jwk(12345, 65537))
    assert isinstance(got, tuple)
    assert len(got) == 2
    assert all(isinstance(x, int) for x in got)


def test_jwk_rsa_public_n_big_endian():
    # 0x00FF -> b'\x00\xff' big-endian = 255; little-endian olsa 65280 olurdu
    j = {"kty": "RSA", "n": b64u(b"\x00\xff"), "e": b64u(b"\x01")}
    assert _jwk_rsa_public(j) == (255, 1)


def test_jwk_rsa_public_e_big_endian():
    j = {"kty": "RSA", "n": b64u(b"\x01"), "e": b64u(b"\x00\x01\x00\x01")}
    assert _jwk_rsa_public(j)[1] == 65537


@pytest.mark.parametrize("kty", ["oct", "EC", "OKP", "rsa", "", "RS", None])
def test_jwk_rsa_public_rejects_wrong_kty(kty):
    with pytest.raises(SsoError, match="JWK is not RSA"):
        _jwk_rsa_public({"kty": kty, "n": "AQ", "e": "AQ"})


def test_jwk_rsa_public_rejects_missing_kty():
    with pytest.raises(SsoError):
        _jwk_rsa_public({"n": "AQ", "e": "AQ"})


def test_jwk_rsa_public_missing_n_raises_keyerror():
    with pytest.raises(KeyError):
        _jwk_rsa_public({"kty": "RSA", "e": "AQAB"})


def test_jwk_rsa_public_missing_e_raises_keyerror():
    with pytest.raises(KeyError):
        _jwk_rsa_public({"kty": "RSA", "n": "AQAB"})


def test_jwk_rsa_public_empty_dict():
    with pytest.raises(SsoError):
        _jwk_rsa_public({})


def test_jwk_rsa_public_ignores_extra_fields():
    j = jwk(999, 17)
    j["kid"] = "key-1"
    j["use"] = "sig"
    j["alg"] = "RS256"
    assert _jwk_rsa_public(j) == (999, 17)


def test_jwk_rsa_public_standard_base64_chars():
    # '+' '/' iceren standart base64 de calisir (urlsafe translation)
    raw = b"\xff\xfe\xfd\xfc"
    j = {"kty": "RSA", "n": base64.b64encode(raw).decode(),
         "e": base64.b64encode(b"\x01\x00\x01").decode()}
    assert _jwk_rsa_public(j) == (int.from_bytes(raw, "big"), 65537)


def test_jwk_rsa_public_with_explicit_padding():
    raw = b"\x01\x02\x03\x04"
    j = {"kty": "RSA", "n": base64.urlsafe_b64encode(raw).decode(),
         "e": base64.urlsafe_b64encode(b"\x03").decode()}
    assert _jwk_rsa_public(j) == (int.from_bytes(raw, "big"), 3)


def test_jwk_rsa_public_minimal_values():
    assert _jwk_rsa_public(jwk(0, 0)) == (0, 0)


def test_jwk_rsa_public_roundtrip_many_random():
    for _ in range(10):
        n = int.from_bytes(os.urandom(128), "big")
        e = int.from_bytes(os.urandom(4), "big") | 1
        assert _jwk_rsa_public(jwk(n, e)) == (n, e)


# ============================================ _b64url_decode (yardimci) =====
@pytest.mark.parametrize("raw", [b"", b"\x00", b"\xff", b"\x01\x02",
                                 b"abc", os.urandom(64)])
def test_b64url_decode_roundtrip(raw):
    assert _b64url_decode(b64u(raw)) == raw


@pytest.mark.parametrize("s,expected", [("!!!", b""), ("", b""), ("====", b"")])
def test_b64url_decode_discards_invalid_chars(s, expected):
    # QUIRK: alfabe-disi karakterler silentce atilir (validate=False)
    assert _b64url_decode(s) == expected


@pytest.mark.parametrize("s", ["A", "abcde", "x", "A" * 5])
def test_b64url_decode_len_mod4_eq1_raises(s):
    # QUIRK: len % 4 == 1 -> 3 pad -> binascii.Error
    with pytest.raises(binascii.Error):
        _b64url_decode(s)


@pytest.mark.parametrize("s,hexed", [("AB", "00"), ("ABC", "0010"),
                                     ("_A", "fc"), ("-A", "f8")])
def test_b64url_decode_short_inputs(s, hexed):
    assert _b64url_decode(s).hex() == hexed


def test_b64url_decode_returns_bytes():
    assert isinstance(_b64url_decode("AQAB"), bytes)


def test_b64url_decode_urlsafe_alphabet():
    # '-' = 62, '_' = 63 (urlsafe); '+' = 62, '/' = 63 (standart) — ayni sonuc
    assert _b64url_decode("-A") == _b64url_decode("+A")
    assert _b64url_decode("_A") == _b64url_decode("/A")
