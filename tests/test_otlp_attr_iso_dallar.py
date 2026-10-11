"""swarmax.otlp._attr_map + _iso_from_ns dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (time.time_ns MONKEYPATCH, dis cagri YOK).
OTLP KeyValue list -> dict + nanos -> ISO-string.
"""
import sys
import time

import pytest

sys.path.insert(0, "src")
from swarmax.otlp import _attr_map, _iso_from_ns  # noqa: E402


# == _attr_map: temel ============================================================================

def test_bos_list():
    assert _attr_map([]) == {}


def test_none_list():
    """ORTAM: attributes or [] — None Kabul."""
    assert _attr_map(None) == {}


def test_tek_string():
    r = _attr_map([{"key": "a", "value": {"stringValue": "x"}}])
    assert r == {"a": "x"}


def test_tek_int():
    r = _attr_map([{"key": "a", "value": {"intValue": 5}}])
    assert r == {"a": 5}


def test_tek_double():
    r = _attr_map([{"key": "a", "value": {"doubleValue": 1.5}}])
    assert r == {"a": 1.5}


def test_tek_bool():
    r = _attr_map([{"key": "a", "value": {"boolValue": True}}])
    assert r == {"a": True}


def test_tek_bytes():
    """ORTAM: bytesValue DESTEKLENMEZ -> None (kind-list'te YOK)."""
    r = _attr_map([{"key": "a", "value": {"bytesValue": "bw=="}}])
    assert r == {"a": None}


def test_returns_dict():
    assert isinstance(_attr_map([]), dict)


# == _attr_map: oncelik ==========================================================================

def test_string_int_oncelik():
    """ORTAM: stringValue intValue'dan ONCE."""
    r = _attr_map([{"key": "a", "value": {"intValue": 5,
                                           "stringValue": "x"}}])
    assert r == {"a": "x"}


def test_int_double_oncelik():
    r = _attr_map([{"key": "a", "value": {"doubleValue": 1.5,
                                           "intValue": 5}}])
    assert r == {"a": 5}


def test_kind_sirasi():
    """ORTAM: stringValue, intValue, ... sira."""
    r = _attr_map([{"key": "a", "value": {"boolValue": False,
                                           "doubleValue": 1.0,
                                           "intValue": 9,
                                           "stringValue": "s"}}])
    assert r == {"a": "s"}


def test_sadece_bool():
    r = _attr_map([{"key": "a", "value": {"boolValue": False}}])
    assert r == {"a": False}


# == _attr_map: arrayValue =======================================================================

def test_array_value():
    r = _attr_map([{"key": "a", "value": {
        "arrayValue": {"values": [{"stringValue": "x"},
                                  {"stringValue": "y"}]}}}])
    assert r == {"a": ["x", "y"]}


def test_array_bos():
    r = _attr_map([{"key": "a", "value": {"arrayValue": {"values": []}}}])
    assert r == {"a": []}


def test_array_int_eleman():
    """ORTAM: array elemanlari stringValue bekler — yoksa None."""
    r = _attr_map([{"key": "a", "value": {
        "arrayValue": {"values": [{"intValue": 5}]}}}])
    assert r == {"a": [None]}


def test_array_karisik():
    r = _attr_map([{"key": "a", "value": {
        "arrayValue": {"values": [{"stringValue": "x"},
                                  {"intValue": 5}]}}}])
    assert r == {"a": ["x", None]}


# == _attr_map: edge =============================================================================

def test_key_yok():
    """ORTAM: key yoksa None-anahtar."""
    r = _attr_map([{"value": {"stringValue": "x"}}])
    assert r == {None: "x"}


def test_value_yok():
    """ORTAM: value yoksa {} -> None."""
    r = _attr_map([{"key": "a"}])
    assert r == {"a": None}


def test_value_bos():
    r = _attr_map([{"key": "a", "value": {}}])
    assert r == {"a": None}


def test_value_none():
    """ORTAM: value=None -> TypeError ('in' NoneType)."""
    with pytest.raises(TypeError):
        _attr_map([{"key": "a", "value": None}])


def test_turkce_key():
    r = _attr_map([{"key": "Türkçe", "value": {"stringValue": "x"}}])
    assert r == {"Türkçe": "x"}


def test_emoji_key():
    r = _attr_map([{"key": "🤖", "value": {"stringValue": "x"}}])
    assert r == {"🤖": "x"}


def test_cok_kv():
    r = _attr_map([{"key": "a", "value": {"stringValue": "x"}},
                   {"key": "b", "value": {"intValue": 2}},
                   {"key": "c", "value": {"boolValue": True}}])
    assert r == {"a": "x", "b": 2, "c": True}


def test_tekrar_eden_key():
    """ORTAM: son-kazanir (dict overwrite)."""
    r = _attr_map([{"key": "a", "value": {"stringValue": "ilk"}},
                   {"key": "a", "value": {"stringValue": "son"}}])
    assert r == {"a": "son"}


def test_repeatable():
    src = [{"key": "a", "value": {"stringValue": "x"}}]
    assert _attr_map(src) == _attr_map(src)


@pytest.mark.parametrize("kind,val", [
    ("stringValue", "x"), ("intValue", 5), ("doubleValue", 1.5),
    ("boolValue", True), ("boolValue", False), ("intValue", 0),
])
def test_kind_matrix(kind, val):
    r = _attr_map([{"key": "k", "value": {kind: val}}])
    assert r == {"k": val}


# == _iso_from_ns ================================================================================

@pytest.fixture()
def sabit_ns(monkeypatch):
    monkeypatch.setattr(time, "time_ns", lambda: 1700000000_000000000)
    return 1700000000_000000000


def test_iso_baslangic():
    """ORTAM: 1700000000 -> 2023-11-14."""
    r = _iso_from_ns(1700000000_000000000)
    assert r.startswith("2023-11-14")


def test_iso_format():
    r = _iso_from_ns(1700000000_000000000)
    assert len(r) == 26  # "YYYY-MM-DD HH:MM:SS.nnnnnn"


def test_iso_bosluk_ayirici():
    """ORTAM: 'T' DEGIL ' ' (bosluk)."""
    r = _iso_from_ns(1700000000_000000000)
    assert " " in r
    assert "T" not in r


def test_iso_nanos_alani():
    r = _iso_from_ns(1700000000_123456789)
    assert r.endswith(".123456")


def test_iso_nanos_kirpilir():
    """ORTAM: nanos//1000 — 6-basamak (mikro)."""
    r = _iso_from_ns(1700000000_999999999)
    assert r.endswith(".999999")


def test_iso_nanos_sifir():
    r = _iso_from_ns(1700000000_000000000)
    assert r.endswith(".000000")


def test_ns_sifir_time_kullanir(sabit_ns):
    """ORTAM: ns <= 0 -> time.time_ns()."""
    assert _iso_from_ns(0) == _iso_from_ns(sabit_ns)


def test_ns_negatif_time_kullanir(sabit_ns):
    assert _iso_from_ns(-1) == _iso_from_ns(sabit_ns)


def test_ns_bir_saniye(sabit_ns):
    r1 = _iso_from_ns(1700000000_000000000)
    r2 = _iso_from_ns(1700000001_000000000)
    assert r1 != r2


def test_ns_ayni_saniye_farkli_nano():
    r1 = _iso_from_ns(1700000000_000000000)
    r2 = _iso_from_ns(1700000000_000001000)
    assert r1 != r2


def test_ns_ayni_micro_ayni():
    """ORTAM: ayni mikrosaniye -> ayni string."""
    assert _iso_from_ns(1700000000_123456789) == \
        _iso_from_ns(1700000000_123456999)


def test_iso_parsable():
    from datetime import datetime
    r = _iso_from_ns(1700000000_000000000)
    assert datetime.fromisoformat(r) is not None


def test_returns_str():
    assert isinstance(_iso_from_ns(1700000000_000000000), str)


def test_repeatable():
    assert _iso_from_ns(1700000000_000000000) == \
        _iso_from_ns(1700000000_000000000)


@pytest.mark.parametrize("ns,exp", [
    (1700000000_000000000, "2023-11-14 22:13:20"),
    (1700000001_500000000, "2023-11-14 22:13:21"),
    (0, "2023-11-14 22:13:20"),
])
def test_ns_matrix(sabit_ns, ns, exp):
    assert _iso_from_ns(ns).split(".")[0] == exp
