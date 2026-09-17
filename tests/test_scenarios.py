"""F1 acceptance: 8/8 injection scenarios with correct severity + SLA (§7, §4.2).

Also: MT-4 lambda-curve (rate-limit), R10 baseline FP budget, evidence sealing.
"""
import random
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from swarmax.db import connect, init_db_with_migrations
from swarmax.fleet import emitter
from swarmax.fleet.emitter import SCENARIOS, EXPECTED, ScenarioResult, retrying_task
from swarmax.metrics.apd import SIGNAL_MAP
from swarmax.pipeline import Pipeline
from swarmax.evidence import append_evidence, verify_chain

BASE = datetime(2026, 9, 1)          # baseline days: Sept 1-6
SCENARIO_DAY = datetime(2026, 9, 7)
ScenarioExpectation = ScenarioResult  # S6 has no emitter entry; expectation is inline


def fresh_pipeline() -> Pipeline:
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return Pipeline(conn)


def ingest_baseline(agent_id: str, pipe: Pipeline, *, days: int = 6) -> None:
    rng = random.Random(42)
    for d in range(days):
        events, guards = emitter.emit_baseline_day(
            agent_id, BASE + timedelta(days=d), rng)
        pipe.ingest(events, guards)


def run_scenario(name: str) -> list:
    pipe = fresh_pipeline()
    agent = f"syn-{name}"
    ingest_baseline(agent, pipe)

    if name == "S1":  # 30 calibrated EWMA observations, then the spike day
        rng = random.Random(7)
        for _ in range(30):
            pipe.evaluate_agent(agent, daily_cost=rng.uniform(11.0, 13.0))
        events, guards = SCENARIOS[name](agent, SCENARIO_DAY, random.Random(1))
        pipe.ingest(events, guards)
        return pipe.evaluate_agent(agent, daily_cost=42.0)

    if name == "S6":  # ticket aging: direct state injection (§4.2, R14)
        pipe.open_escalation(
            escalation_id=f"esc-{agent}", agent_id=agent, task_id="t-manual",
            reason="permission",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=30))
        return pipe.evaluate_agent(agent)

    events, guards = SCENARIOS[name](agent, SCENARIO_DAY, random.Random(3))
    pipe.ingest(events, guards)
    return pipe.evaluate_agent(agent)


# ---------------------------------------------------------------- 8/8 matrix

@pytest.mark.parametrize("name", ["S1", "S2", "S3", "S4", "S5", "S7", "S8"])
def test_scenario_detected_with_severity_and_sla(name):
    alarms = run_scenario(name)
    fired = {a.signal: a for a in alarms if not a.suppressed}
    for expected_signal in EXPECTED[name].expected_signals:
        assert expected_signal in fired, f"{name}: {expected_signal} not detected"
        rule = SIGNAL_MAP[expected_signal]
        alarm = fired[expected_signal]
        assert alarm.severity == rule.severity
        assert alarm.sla_hours == rule.sla_hours
        assert alarm.reason == rule.reason


def test_s6_ticket_aging_self_escalation():
    alarms = run_scenario("S6")
    fired = {a.signal: a for a in alarms if not a.suppressed}
    assert "escalation.age_max>24" in fired
    alarm = fired["escalation.age_max>24"]
    assert alarm.severity == "Emergency" and alarm.sla_hours == 2.0
    assert alarm.reason == "system_health"  # self-escalation (R14)


def test_all_eight_scenarios_detected():
    names = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    for n in names:
        alarms = run_scenario(n)
        expected = EXPECTED.get(n, ScenarioExpectation("S6", ("escalation.age_max>24",))).expected_signals
        fired = {a.signal for a in alarms if not a.suppressed}
        assert set(expected) <= fired, f"{n}: expected {expected}, fired {fired}"


def test_baseline_produces_zero_false_positives():
    """R10: <= 5% FP of hourly cycles per agent-day on calm traffic."""
    pipe = fresh_pipeline()
    agent = "syn-base"
    ingest_baseline(agent, pipe)
    rng = random.Random(11)
    fp = 0
    for cycle in range(24):  # 24 hourly evaluation cycles
        alarms = pipe.evaluate_agent(agent, daily_cost=rng.uniform(11.0, 13.0))
        escalated = [a for a in alarms if not a.suppressed]
        if escalated:
            fp += 1
        pipe.apd.fp_budget.record_cycle(bool(escalated))
    assert fp == 0
    assert pipe.apd.fp_budget.within_budget


# ---------------------------------------------------------------- MT-4 lambda curve

def test_lambda_curve_rate_limit_drop_within_5_points_at_0_1():
    rng = random.Random(2026)
    trials = 4000
    success_0 = sum(retrying_task(rng, 0.0)[0] for _ in range(trials)) / trials
    success_01 = sum(retrying_task(rng, 0.1)[0] for _ in range(trials)) / trials
    drop_points = (success_0 - success_01) * 100
    assert drop_points <= 5.0, f"MT-4 violated: {drop_points:.2f} points at lambda=0.1"


def test_lambda_curve_monotonic_degradation():
    rng = random.Random(9)
    rates = [0.0, 0.05, 0.1, 0.2, 0.4]
    curve = [sum(retrying_task(rng, r)[0] for _ in range(1000)) / 1000 for r in rates]
    assert all(curve[i] >= curve[i + 1] - 0.03 for i in range(len(curve) - 1))


# ---------------------------------------------------------------- evidence sealing

def test_escalations_sealed_into_evidence_ledger():
    pipe = run_scenario_pipeline("S3")
    alarms = [a for a in pipe.evaluate_agent("syn-S3") if not a.suppressed]
    assert alarms
    # evaluate_agent auto-persisted each alarm to the SLA queue + evidence ledger
    stored = pipe.conn.execute("SELECT COUNT(*) c FROM alarms").fetchone()["c"]
    assert stored == len(alarms)
    ok, auto_sealed = verify_chain(pipe.conn)
    assert ok and auto_sealed >= len(alarms)
    # explicit appends keep working alongside auto-sealing
    for a in alarms:
        append_evidence(pipe.conn, "escalation_created", {
            "signal": a.signal, "agent": "syn-S3", "severity": a.severity,
            "sla_hours": a.sla_hours, "protection": a.protection,
        })
    ok, checked = verify_chain(pipe.conn)
    assert ok and checked >= 2 * len(alarms)
    with pytest.raises(sqlite3.IntegrityError):
        with pipe.conn:
            pipe.conn.execute("UPDATE evidence_ledger SET event_type='tampered'")


def run_scenario_pipeline(name: str) -> Pipeline:
    pipe = fresh_pipeline()
    agent = f"syn-{name}"
    ingest_baseline(agent, pipe)
    events, guards = SCENARIOS[name](agent, SCENARIO_DAY, random.Random(5))
    pipe.ingest(events, guards)
    return pipe
