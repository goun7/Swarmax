"""Synthetic fleet emitter — paper §7.3 and §7 F1 (8 injection scenarios).

All emitted rows carry synthetic=True so real dogfood is never polluted (§7.3, R10):
synthetic agents are created with the calibration window pre-closed.

Event dicts match the SQLite columns (schema/sqlite_v1.sql + migration 002).
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

SYNTHETIC = True
TOOLS_BASELINE = {"web_search": 5, "sql_query": 3, "email_send": 2}  # per-hour shape


def _ts(day: datetime, hour: int) -> datetime:
    return day + timedelta(hours=hour)


def _task_event(agent_id: str, task_id: str, ts: datetime, *, cost: float,
                latency_ms: int, error_class: str | None = None,
                status: str = "ok", retry_count: int = 0,
                task_template: str | None = None,
                end_state: dict | None = None) -> dict:
    # call-unique id: same-second bursts must not collide on the PK
    return {
        "event_id": f"evt_{agent_id}_{task_id}_{time.time_ns()}",
        "agent_id": agent_id, "task_id": task_id, "session_id": f"sess_{task_id}",
        "model_name": "gpt-4o-mini", "input_tokens": 900, "output_tokens": 350,
        "cost_usd": cost, "latency_ms": latency_ms,
        "error_class": error_class, "status": status, "synthetic": SYNTHETIC, "ts": ts,
        "retry_count": retry_count, "ttft_s": 0.4,
        "task_template": task_template,
        "end_state_json": json.dumps(end_state, sort_keys=True) if end_state else None,
    }


def _guard_event(agent_id: str, task_id: str, ts: datetime, tool_name: str,
                 arguments: dict, *, event_type: str = "tool_call",
                 decision: str | None = None) -> dict:
    return {
        "event_id": f"grd_{agent_id}_{task_id}_{time.time_ns()}_{tool_name}",
        "agent_id": agent_id, "task_id": task_id, "event_type": event_type,
        "decision": decision, "tool_name": tool_name,
        "arguments_json": json.dumps(arguments, sort_keys=True),
        "synthetic": SYNTHETIC, "ts": ts,
    }


@dataclass
class ScenarioResult:
    """What the engine MUST detect for 8/8 acceptance (severity + SLA from §4.2)."""
    scenario: str
    expected_signals: tuple[str, ...]


# ------------------------------------------------------------------ baseline

def emit_baseline_day(agent_id: str, day: datetime, rng: random.Random,
                      *, daily_cost: float = 12.0) -> tuple[list[dict], list[dict]]:
    """One calm day: ~10 tasks across the baseline tool mix, cost ~= daily_cost."""
    events: list[dict] = []
    guards: list[dict] = []
    n_tasks = 10
    for i in range(n_tasks):
        ts = _ts(day, rng.randrange(8, 20))
        task_id = f"{agent_id}_t{i}"
        tools = list(TOOLS_BASELINE)
        for tool in tools:
            guards.append(_guard_event(agent_id, task_id, ts, tool, {"q": f"task-{i}"}))
        events.append(_task_event(
            agent_id, task_id, ts,
            cost=daily_cost / n_tasks * rng.uniform(0.7, 1.3),
            latency_ms=rng.randrange(800, 1600),
            # constant end-state per template: equivalent runs must NOT trip the
            # metamorphic oracle on baseline traffic (§3.2-7)
            task_template="summarize_inbox", end_state={"emails_summarized": n_tasks},
        ))
    return events, guards


# ---------------------------------------------------------------- scenarios

def emit_s1_cost_spike(agent_id: str, day: datetime, rng: random.Random):
    """(a) 3.5x token/cost spike on one day."""
    return emit_baseline_day(agent_id, day, rng, daily_cost=12.0 * 3.5)


def emit_s2_tool_drift(agent_id: str, day: datetime, rng: random.Random):
    """(b) tool distribution drift (JSD target ~0.55 > 0.40): half the calls
    migrate to tools absent from the 7d window."""
    events, guards = [], []
    for i in range(10):
        ts = _ts(day, rng.randrange(8, 20))
        task_id = f"{agent_id}_t{i}"
        # full pivot: every call lands on tools ABSENT from the 7d reference window
        # (JSD(P7d || Q24h) ~ 1.0, far above the 0.40 alarm threshold); args vary per
        # call so this is pure tool-drift, not a loop pathology (§3.2-3 stays silent)
        for j in range(3):
            guards.append(_guard_event(agent_id, task_id, ts,
                                       "scraper_v2", {"q": f"task-{i}-{j}"}))
        events.append(_task_event(agent_id, task_id, ts, cost=1.2, latency_ms=1100))
    return events, guards


def emit_s3_loop(agent_id: str, day: datetime, rng: random.Random):
    """(c) 3-repeat identical tool call -> loop breaker opens."""
    events, guards = [], []
    ts = _ts(day, 10)
    task_id = f"{agent_id}_loop"
    for _ in range(3):  # 3 consecutive identical hashes (§3.2-3)
        guards.append(_guard_event(agent_id, task_id, ts, "sql_query", {"table": "users"}))
    events.append(_task_event(agent_id, task_id, ts, cost=0.8, latency_ms=900,
                              error_class="loop", status="quarantined"))
    return events, guards


def emit_s4_new_class(agent_id: str, day: datetime, rng: random.Random):
    """(d) a first-seen error class signature."""
    events, guards = emit_baseline_day(agent_id, day, rng)
    novel = events[-1]
    novel.update(status="error", error_class="ERR_NOVEL_42",
                 task_id=f"{agent_id}_novel")
    return events, guards


def emit_s5_deny_spike(agent_id: str, day: datetime, rng: random.Random):
    """(e) permission deny-storm: > 20% deny inside the latest 1s decision window.
    §4.2 evaluates a 1-second window, so the burst must be sub-second dense."""
    events, guards = emit_baseline_day(agent_id, day, rng)
    task_id = f"{agent_id}_perm"
    ts = _ts(day, 11)
    for i in range(10):
        guards.append(_guard_event(
            agent_id, task_id, ts + timedelta(milliseconds=100 * i), "payment_refund",
            {"id": i}, event_type="permission_decision",
            decision="deny" if i % 2 == 0 else "allow",  # 50% deny in-window
        ))
    return events, guards


def emit_s7_rate_limit_wave(agent_id: str, day: datetime, rng: random.Random):
    """(g) rate-limit wave (429s) — ReliabilityBench: most harmful fault class;
    drives error.rate > 20% in the 24s window (MT-4 lambda-curve data)."""
    events, guards = [], []
    base = _ts(day, 12)
    for i in range(10):
        ts = base + timedelta(seconds=i)
        task_id = f"{agent_id}_rl{i}"
        limited = i % 2 == 0  # 50% > 20%
        events.append(_task_event(
            agent_id, task_id, ts, cost=0.4, latency_ms=600,
            error_class=None if not limited else "timeout",
            status="ok" if not limited else "error",
        ))
        guards.append(_guard_event(agent_id, task_id, ts, "http_fetch", {"url": "api.example.com"}))
    return events, guards


def emit_s8_schema_drift(agent_id: str, day: datetime, rng: random.Random):
    """(h) schema-drift + partial-response classes (ReliabilityBench chaos)."""
    events, guards = emit_baseline_day(agent_id, day, rng)
    t1, t2 = events[-2], events[-1]
    t1.update(status="error", error_class="schema drift: unexpected field 'total_cents'",
              task_id=f"{agent_id}_sd1")
    t2.update(status="error", error_class="partial response: truncated json body",
              task_id=f"{agent_id}_sd2")
    return events, guards


SCENARIOS: dict[str, callable] = {
    "S1": emit_s1_cost_spike,
    "S2": emit_s2_tool_drift,
    "S3": emit_s3_loop,
    "S4": emit_s4_new_class,
    "S5": emit_s5_deny_spike,
    "S7": emit_s7_rate_limit_wave,
    "S8": emit_s8_schema_drift,
}

EXPECTED: dict[str, ScenarioResult] = {
    "S1": ScenarioResult("S1", ("cost.daily>2x_ewma",)),          # Critical / budget / 24h
    "S2": ScenarioResult("S2", ("drift.tool_distribution>0.40",)),  # Medium / drift / weekly
    "S3": ScenarioResult("S3", ("loop>=2",)),                     # Emergency / quality / 30m
    "S4": ScenarioResult("S4", ("error.new_class_seen",)),        # Critical / unknown / 24h
    "S5": ScenarioResult("S5", ("permission.deny>0.20",)),        # Critical / permission / 4h
    "S7": ScenarioResult("S7", ("error.rate>0.20",)),             # Critical / quality / 4h
    "S8": ScenarioResult("S8", ("error.new_class_seen",)),        # Critical / unknown / 24h
}
# S6 (ticket aging) is state injected directly into hitl_escalations by the harness.


# ------------------------------------------------- MT-4 lambda-curve executor

def retrying_task(rng: random.Random, lambda_rate: float, attempts: int = 3) -> tuple[bool, int]:
    """One task against a fault-injected provider: each attempt fails w.p. lambda_rate
    (rate-limit class), up to `attempts` tries. Returns (success, retries_used).
    MT-4 acceptance: at lambda=0.1 task success drop <= 5 points vs fault-free."""
    retries = 0
    for attempt in range(attempts):
        if rng.random() >= lambda_rate:
            return True, retries
        retries += 1
    return False, retries
