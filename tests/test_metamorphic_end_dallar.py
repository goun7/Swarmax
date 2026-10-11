"""test_metamorphic_end_dallar.py — _end_states_diverge dal-kesen suite.

ORTAM-ANATOMI (swarmax/metrics/metamorphic.py L58):
  _end_states_diverge(reference: dict, candidate: dict) -> bool:
    if set(reference) != set(candidate): return True
    for k in reference:
        rv, cv = reference[k], candidate[k]
        if isinstance(rv, (dict, list)):
            if json.dumps(rv, sort_keys=True) != json.dumps(cv, sort_keys=True):
                return True
        elif rv != cv:
            return True
    return False
  (kullanim: observe_end_state -> prior[-1] ile karsilastirir, drift icin)

ORTAM-OGRENDILER:
  (1) Ayni key-set + ayni degerler -> False (esit); key-set farki -> True
      (EKSTRA key veya EKSIK key — siradan bagimsiz, set karsilastirma).
  (2) Ic ice dict/list: json.dumps(sort_keys=True) ile KARŞILAŞTIRILIR —
      dict key SIRASI onemsiz, liste SIRASI onemli.
  (3) QUIRK: skaler degerler == ile karsilastirilir — 1 == 1.0 True (int/float
      esit sayilir, diverge YOK), True == 1 True (bool/int esit sayilir),
      "1" == 1 False (tip-disi -> diverge).
  (4) QUIRK: isinstance rv (dict,list) — rv skaler & cv dict ise rv != cv
      -> True; rv dict & cv skaler ise json.dumps ValueError DEGIL, != True.

Kural-1: SADECE yeni test dosyasi; production DOKUNULMADI. Kural-4: saf
in-memory. --noconftest ZORUNLU.
"""
import math
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.metrics.metamorphic import _end_states_diverge  # noqa: E402


@pytest.mark.parametrize("d", [
    {}, {"a": 1}, {"a": 1, "b": "x"}, {"nested": {"x": 1}}, {"l": [1, 2]},
    {"a": None, "b": True}, {"u": "Türkçe"},
])
def test_identical_dicts_do_not_diverge(d):
    assert _end_states_diverge(d, dict(d)) is False


@pytest.mark.parametrize("ref,cand", [
    ({"a": 1}, {"a": 2}),
    ({"a": 1}, {"a": 0}),
    ({"a": "x"}, {"a": "y"}),
    ({"a": 1, "b": 2}, {"a": 1, "b": 3}),
    ({"a": None}, {"a": 1}),
    ({"a": True}, {"a": False}),
])
def test_changed_scalar_values_diverge(ref, cand):
    assert _end_states_diverge(ref, cand) is True


@pytest.mark.parametrize("ref,cand", [
    ({"a": 1}, {"a": 1, "b": 2}),   # ekstra key
    ({"a": 1, "b": 2}, {"a": 1}),   # eksik key
    ({}, {"a": 1}),
    ({"a": 1}, {}),
])
def test_key_set_difference_diverges(ref, cand):
    assert _end_states_diverge(ref, cand) is True


def test_key_order_irrelevant():
    assert _end_states_diverge({"a": 1, "b": 2}, {"b": 2, "a": 1}) is False


def test_nested_dict_equal_no_diverge():
    assert _end_states_diverge({"d": {"x": 1, "y": 2}}, {"d": {"y": 2, "x": 1}}) is False


def test_nested_dict_value_change_diverges():
    assert _end_states_diverge({"d": {"x": 1}}, {"d": {"x": 2}}) is True


def test_nested_dict_extra_key_diverges():
    assert _end_states_diverge({"d": {"x": 1}}, {"d": {"x": 1, "y": 2}}) is True


def test_nested_list_equal_no_diverge():
    assert _end_states_diverge({"l": [1, 2, 3]}, {"l": [1, 2, 3]}) is False


def test_nested_list_order_sensitive():
    # QUIRK: liste SIRASI onemli (json.dumps)
    assert _end_states_diverge({"l": [1, 2]}, {"l": [2, 1]}) is True


def test_nested_list_in_dict_order_irrelevant():
    assert _end_states_diverge({"d": {"a": [1], "b": 2}},
                               {"d": {"b": 2, "a": [1]}}) is False


def test_deeply_nested_structures():
    ref = {"a": {"b": {"c": [1, {"d": "x"}]}}}
    assert _end_states_diverge(ref, {"a": {"b": {"c": [1, {"d": "x"}]}}}) is False
    assert _end_states_diverge(ref, {"a": {"b": {"c": [1, {"d": "y"}]}}}) is True


@pytest.mark.parametrize("ref,cand,expected", [
    ({"a": 1}, {"a": 1.0}, False),    # QUIRK: int == float
    ({"a": 1.0}, {"a": 1}, False),
    ({"a": True}, {"a": 1}, False),   # QUIRK: bool == int
    ({"a": 1}, {"a": True}, False),
    ({"a": False}, {"a": 0}, False),
    ({"a": "1"}, {"a": 1}, True),     # str != int
    ({"a": 1}, {"a": "1"}, True),
    ({"a": 2.5}, {"a": 2.5}, False),
])
def test_numeric_type_coercion_quirk(ref, cand, expected):
    assert _end_states_diverge(ref, cand) is expected


def test_nan_value_diverges():
    # nan != nan -> True
    assert _end_states_diverge({"a": float("nan")}, {"a": float("nan")}) is True


def test_inf_values():
    assert _end_states_diverge({"a": math.inf}, {"a": math.inf}) is False
    assert _end_states_diverge({"a": math.inf}, {"a": -math.inf}) is True


@pytest.mark.parametrize("ref,cand", [
    ({"a": 1}, {"a": {"x": 1}}),   # skaler -> dict
    ({"a": {"x": 1}}, {"a": 1}),   # dict -> skaler
    ({"a": [1]}, {"a": 1}),
    ({"a": 1}, {"a": [1]}),
])
def test_type_mismatch_between_scalar_and_container(ref, cand):
    assert _end_states_diverge(ref, cand) is True


def test_none_vs_none_no_diverge():
    assert _end_states_diverge({"a": None, "b": None},
                               {"a": None, "b": None}) is False


def test_none_vs_zero_diverges():
    assert _end_states_diverge({"a": None}, {"a": 0}) is True


def test_unicode_keys_and_values():
    assert _end_states_diverge({"Türkçe": "değer"}, {"Türkçe": "değer"}) is False
    assert _end_states_diverge({"Türkçe": "değer"}, {"Türkçe": "başka"}) is True
    assert _end_states_diverge({"🚀": 1}, {"🚀": 1}) is False


def test_empty_list_vs_empty_dict_diverge():
    assert _end_states_diverge({"a": []}, {"a": {}}) is True


def test_returns_bool():
    assert isinstance(_end_states_diverge({}, {}), bool)
    assert isinstance(_end_states_diverge({"a": 1}, {"a": 2}), bool)


def test_asymmetric_in_key_set():
    assert _end_states_diverge({"a": 1}, {"a": 1, "b": 2}) is True
    assert _end_states_diverge({"a": 1, "b": 2}, {"a": 1}) is True


def test_nested_empty_containers_equal():
    assert _end_states_diverge({"a": {}, "b": []}, {"a": {}, "b": []}) is False
    assert _end_states_diverge({"a": {}}, {"a": []}) is True


def test_large_flat_dict():
    ref = {f"k{i}": i for i in range(100)}
    assert _end_states_diverge(ref, dict(ref)) is False
    cand = dict(ref)
    cand["k50"] = 999
    assert _end_states_diverge(ref, cand) is True
