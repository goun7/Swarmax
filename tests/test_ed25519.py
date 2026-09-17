"""Ed25519 regression: RFC 8032 vectors + tamper rejection (F2 foundation)."""
from swarmax import ed25519 as e


def test_rfc8032_vector_1():
    sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    pk = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    assert e.secret_to_public(sk) == pk
    sig = e.sign(sk, b"")
    assert e.verify(pk, b"", sig)


def test_rfc8032_vector_2():
    sk = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
    pk = bytes.fromhex("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c")
    msg = bytes([0x72])
    assert e.secret_to_public(sk) == pk
    assert e.verify(pk, msg, e.sign(sk, msg))


def test_roundtrip_and_tamper_rejection():
    seed = e.generate_seed()
    public = e.secret_to_public(seed)
    msg = b"seal:root=deadbeef"
    sig = e.sign(seed, msg)
    assert e.verify(public, msg, sig)
    bad = bytearray(sig)
    bad[10] ^= 0x01
    assert not e.verify(public, msg, bytes(bad))
    assert not e.verify(public, msg + b"x", sig)
    assert not e.verify(e.secret_to_public(e.generate_seed()), msg, sig)


def test_malformed_inputs_rejected():
    seed = e.generate_seed()
    public = e.secret_to_public(seed)
    assert not e.verify(b"short", b"m", e.sign(seed, b"m"))
    assert not e.verify(public, b"m", b"short")
