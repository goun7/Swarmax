"""test_semconv_type_dallar.py — _expected_type + _actual_type dal-kesen suite.

ORTAM-ANATOMI:
  _expected_type(key) (semconv/validate.py L32):
    if key in GENAI_ATTRIBUTES: return GENAI_ATTRIBUTES[key]
    if key in SWX_ATTRIBUTES:   return SWX_ATTRIBUTES[key]
    return None
  _actual_type(value) (L40):
    bool -> "bool" | int -> "int" | float -> "double" | str -> "str"
    list & all-str -> "str[]" | list -> "list" | else -> "json"

ORTAM-OGRENDILER:
  (1) _actual_type siralama KRITIK: bool once (bool int'in alt-sinifi —
      True isinstance(int) True ama bool-ilk siradan dolayi "bool").
  (2) QUIRK: bos-liste [] -> "str[]" (vacuous truth: all(...) bos listte True).
  (3) tuple/set/frozenset -> "json" (sadece list kontrol edilir).
  (4) None/bytes/dict/complex -> "json".
  (5) _expected_type: iki registry arasinda OVERLAP YOK (GENAI first wins
      olmadi ama cakisma yok); bilinmeyen key -> None; None key -> None
      (TypeError firlatmaz — `None in dict` False).

Kural-1: SADECE yeni test dosyasi; production DOKUNULMADI. Kural-4: saf
in-memory. --noconftest ZORUNLU.
"""
import math
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.semconv.validate import (  # noqa: E402
    GENAI_ATTRIBUTES,
    SWX_ATTRIBUTES,
    _actual_type,
    _expected_type,
)

ALL_REGISTERED = sorted(set(GENAI_ATTRIBUTES) | set(SWX_ATTRIBUTES))


# ======================================================== _expected_type ====
@pytest.mark.parametrize("key", list(GENAI_ATTRIBUTES))
def test_expected_type_genai_registry(key):
    assert _expected_type(key) == GENAI_ATTRIBUTES[key]


@pytest.mark.parametrize("key", list(SWX_ATTRIBUTES))
def test_expected_type_swx_registry(key):
    assert _expected_type(key) == SWX_ATTRIBUTES[key]


@pytest.mark.parametrize("key", ALL_REGISTERED)
def test_expected_type_returns_str_or_none(key):
    got = _expected_type(key)
    assert got is None or isinstance(got, str)


@pytest.mark.parametrize("key", ["gen_ai", "swx", "foo.bar", "", "GEN_AI.SYSTEM",
                                 "gen_ai.provider.name ", " gen_ai.provider.name", "unknown.attr"])
def test_expected_type_unknown_keys_return_none(key):
    assert _expected_type(key) is None


def test_expected_type_none_key_returns_none():
    # `None in dict` -> False -> None (TypeError firlatmaz)
    assert _expected_type(None) is None


def test_expected_type_case_sensitive():
    assert _expected_type("GEN_AI.SYSTEM") is None
    assert _expected_type("gen_ai.SYSTEM") is None
    # G51-5: gen_ai.system kaldirildi; gecerli bir key ile olculur
    assert _expected_type("gen_ai.provider.name") == GENAI_ATTRIBUTES["gen_ai.provider.name"]


def test_expected_type_prefix_does_not_match():
    assert _expected_type("gen_ai.") is None
    assert _expected_type("swx.") is None
    assert _expected_type("gen_ai.system.request") is None
    # G51-5: gen_ai.system upstream'den KALDIRILDI -> None (unknown)
    assert _expected_type("gen_ai.system") is None


def test_expected_type_no_registry_overlap():
    assert set(GENAI_ATTRIBUTES) & set(SWX_ATTRIBUTES) == set()


def test_expected_type_registries_nonempty():
    assert len(GENAI_ATTRIBUTES) > 10
    assert len(SWX_ATTRIBUTES) > 10


@pytest.mark.parametrize("key", ["gen_ai.provider.name", "swx.fleet.name"])
def test_expected_type_known_values(key):
    expected = {**SWX_ATTRIBUTES, **GENAI_ATTRIBUTES}[key]
    assert _expected_type(key) == expected


def test_expected_type_supports_int_key():
    # dict key str olmali; int key -> False -> None
    assert _expected_type(42) is None


# =========================================================== _actual_type ===
@pytest.mark.parametrize("value,expected", [
    (True, "bool"), (False, "bool"),
    (1, "int"), (0, "int"), (-1, "int"), (2**64, "int"), (-(2**64), "int"),
    (1.0, "double"), (0.0, "double"), (-1.5, "double"),
    (math.pi, "double"), (math.e, "double"),
    ("", "str"), ("hello", "str"), ("Türkçe", "str"), ("日本語", "str"),
])
def test_actual_type_scalars(value, expected):
    assert _actual_type(value) == expected


def test_actual_type_bool_before_int():
    # KRITIK: bool int'in alt-sinifi; bool-ilk siradan dolayi True -> "bool"
    assert _actual_type(True) == "bool"
    assert _actual_type(True) != "int"
    assert isinstance(True, int)  # Python gercegi


@pytest.mark.parametrize("value", [0.0, -0.0, math.inf, -math.inf])
def test_actual_type_float_specials(value):
    assert _actual_type(value) == "double"


def test_actual_type_nan_is_double():
    assert _actual_type(float("nan")) == "double"


@pytest.mark.parametrize("value,expected", [
    (["a", "b"], "str[]"), ([], "str[]"), ([""], "str[]"),
    (["Türkçe", "🚀"], "str[]"), (["a", "", "c"], "str[]"),
])
def test_actual_type_str_lists(value, expected):
    assert _actual_type(value) == expected


def test_actual_type_empty_list_is_str_array():
    # QUIRK: vacuous truth — all(...) bos listede True -> "str[]"
    assert _actual_type([]) == "str[]"


@pytest.mark.parametrize("value", [
    [1], [1, 2], [True], [1.5], [None], [{}], [[1]], [{}],
    ["a", 1], [1, "a"], ["a", None], [None, "a"],
])
def test_actual_type_mixed_lists(value):
    assert _actual_type(value) == "list"


@pytest.mark.parametrize("value", [
    tuple(), ("a", "b"), {1, 2}, frozenset(), (1,), {"a"},
])
def test_actual_type_non_list_sequences_are_json(value):
    # QUIRK: tuple/set -> "json" (sadece list kontrol edilir)
    assert _actual_type(value) == "json"


@pytest.mark.parametrize("value", [
    {}, {"a": 1}, {"a": {"b": [1, 2]}}, None, b"bytes", b"", object(),
    range(3), iter([]), lambda: None, complex(1, 2),
])
def test_actual_type_json_fallback(value):
    assert _actual_type(value) == "json"


def test_actual_type_list_of_lists():
    assert _actual_type([["a"], ["b"]]) == "list"


def test_actual_type_list_of_dicts():
    assert _actual_type([{"a": 1}]) == "list"


def test_actual_type_nested_str_list():
    assert _actual_type([["a", "b"], ["c"]]) == "list"


def test_actual_type_str_list_with_bool():
    # bool str DEGIL -> "list"
    assert _actual_type(["a", True]) == "list"


def test_actual_type_returns_str():
    for v in [True, 1, 1.0, "x", [], [1], {}, None]:
        assert isinstance(_actual_type(v), str)


@pytest.mark.parametrize("value", [True, 1, 1.0, "x", [], {}, None])
def test_actual_type_never_returns_none(value):
    assert _actual_type(value) is not None


def test_actual_type_expected_matches_for_valid_attributes():
    # registry'deki tipler Python degerleriyle uyumlu
    # G51-5 (2026-10-23): "json" tipi eklendi (upstream "any" attribute'ler)
    compat = {"str": "x", "int": 1, "double": 1.0, "bool": True,
              "str[]": ["a"], "json": {"role": "user"}}
    for key, typ in [*GENAI_ATTRIBUTES.items(), *SWX_ATTRIBUTES.items()]:
        if typ in compat:
            assert _actual_type(compat[typ]) == typ, (key, typ)


def test_actual_type_registry_type_coverage():
    types = set(GENAI_ATTRIBUTES.values()) | set(SWX_ATTRIBUTES.values())
    # G51-5 (2026-10-23): "json" eklendi (any-tip attribute'ler)
    assert types <= {"str", "int", "double", "bool", "str[]", "json"}
