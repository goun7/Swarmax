"""Metric primitive tests — §3.2 formulas, R3/R4 disciplines, oracle, FP budget."""
import pytest

from swarmax.metrics.statistics import (
    CusumState, EwmaState, cusum_update, ewma_update, jsd_divergence,
    mad_robust_z, psi,
)
from swarmax.metrics.loop_breaker import LoopBreaker, call_hash
from swarmax.metrics.classifier import Classifier, PRESEEN_CLASSES
from swarmax.metrics.metamorphic import MetamorphicEngine, OUTPUT_QUALITY_BUDGET
from swarmax.metrics.apd import FleetApd, FpBudget

# ---------------------------------------------------------------- EWMA (§3.2-1)

def test_ewma_cold_start_no_alarm_without_calibration():
    state = EwmaState()
    for c in [12.0] * 40 + [42.0]:
        r = ewma_update(state, c)  # calibrated=False -> never armed
    assert not r.armed and not r.alarm


def test_ewma_arms_after_30_obs_and_fires_on_spike():
    import random
    rng = random.Random(5)
    state = EwmaState(calibrated=True)
    costs = [rng.uniform(11.0, 13.0) for _ in range(30)]
    results = [ewma_update(state, c) for c in costs]
    assert not results[0].armed          # < 30 observations
    assert results[29].armed            # armed exactly at 30 (R3)
    spike = ewma_update(state, 42.0)
    assert spike.armed and spike.alarm and spike.z is not None and spike.z > 2.5


# ---------------------------------------------------------------- JSD (§3.2-2)

def test_jsd_identical_windows_healthy():
    r = jsd_divergence({"a": 5, "b": 3}, {"a": 5, "b": 3})
    assert r.value is not None and r.value < 0.20 and r.band == "healthy"


def test_jsd_drifted_window_alarms():
    r = jsd_divergence({"a": 5, "b": 3, "c": 2}, {"z": 10})
    assert r.band == "alarm" and r.value > 0.40


def test_jsd_empty_window_is_warming_up_never_infinite():
    r = jsd_divergence({}, {"a": 1})
    assert r.value is None and r.band == "warming_up"


# ---------------------------------------------------------------- MAD (§3.2-4)

def test_mad_flags_outlier():
    r = mad_robust_z([10.0, 10.0, 10.0, 12.0, 14.0, 40.0])
    assert r.alarm and abs(r.robust_z) > 3.0


def test_mad_stable_series_no_alarm():
    r = mad_robust_z([10.0, 10.0, 10.0, 10.0, 10.0])
    assert not r.alarm


# ---------------------------------------------------- Page-Hinkley / PSI (§3.2-5)

def test_cusum_detects_persistent_shift():
    state = CusumState()
    alarms = [cusum_update(state, x, mu0=10.0).alarm for x in [14.0] * 8]
    assert any(alarms)


def test_cusum_quiet_on_stable_series():
    state = CusumState()
    alarms = [cusum_update(state, x, mu0=10.0).alarm for x in [10.0] * 50]
    assert not any(alarms)


def test_psi_large_shift():
    r = psi({"ok": 90, "fail": 10}, {"ok": 40, "fail": 60})
    assert r.large_shift and r.value > 0.25


# ---------------------------------------------------------------- loop breaker

def test_loop_breaker_opens_on_3_identical_calls():
    b = LoopBreaker()
    assert not b.feed("sql_query", {"table": "users"})
    assert not b.feed("sql_query", {"table": "users"})
    assert b.feed("sql_query", {"table": "users"})
    assert b.opened


def test_loop_breaker_silent_on_varied_calls():
    b = LoopBreaker()
    for i in range(5):
        assert not b.feed("sql_query", {"table": f"users_{i}"})


def test_call_hash_is_order_stable():
    assert call_hash("t", {"a": 1, "b": 2}) == call_hash("t", {"b": 2, "a": 1})
    assert call_hash("t", {"a": 1}) != call_hash("u", {"a": 1})


# ---------------------------------------------------------------- classifier

def test_classifier_maps_known_signatures():
    c = Classifier()
    assert c.classify("request timeout after 30s") == "timeout"
    assert c.classify("schema drift: unexpected field") == "schema_drift"
    assert c.classify("partial response: truncated body") == "partial_response"
    assert c.classify("???") == "unknown"


def test_new_class_seen_fires_once():
    c = Classifier()
    c.seen |= PRESEEN_CLASSES
    assert c.observe("timeout") is False          # pre-seen mechanical class
    assert c.observe("schema_drift") is True      # novel chaos class
    assert c.observe("schema_drift") is False


# ---------------------------------------------------------------- metamorphic

def test_metamorphic_flags_end_state_divergence():
    m = MetamorphicEngine()
    assert not m.observe_end_state("tmpl", {"records_created": 3})
    assert m.observe_end_state("tmpl", {"records_created": 0})
    assert not m.observe_end_state("tmpl", {"records_created": 0})


def test_metamorphic_ignores_key_order():
    m = MetamorphicEngine()
    m.observe_end_state("tmpl", {"a": 1, "b": 2})
    assert not m.observe_end_state("tmpl", {"b": 2, "a": 1})


def test_shadow_rerun_budget_overrun_recorded():
    m = MetamorphicEngine()
    for _ in range(100):
        m.record_traffic(1)
    assert m.can_shadow_rerun()          # 1/100 = exactly the 1% budget
    m.note_shadow_rerun("t1")
    assert not m.can_shadow_rerun()      # a second rerun would be 2/100
    m.note_shadow_rerun("t2")            # taken anyway -> recorded as overrun
    assert m.budget_overruns == ["t2"]


# ---------------------------------------------------------------- FP budget (R10)

def test_fp_budget_within_5_percent():
    b = FpBudget()
    for i in range(24):
        b.record_cycle(false_positive=(i == 0))  # 1 FP / 24 cycles = 4.2%
    assert b.within_budget


def test_fp_budget_exceeded():
    b = FpBudget()
    for i in range(24):
        b.record_cycle(false_positive=(i in (0, 1)))  # 8.3%
    assert not b.within_budget
