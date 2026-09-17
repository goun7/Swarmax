"""APD — Alarm & Protection Dispatcher — paper §4.2 map + §3.3 calibration + R10/R14.

The §4.2 signal→escalation map is implemented verbatim. §3.3 discipline: during the
14-day calibration window only Info/Emergency signals fire (`loop`, `new_class`,
`escalation.age_max`); High/Critical thresholds arm only after calibration — synthetic
agents are exempt (window pre-closed, R10) so test data never pollutes real dogfood.
R10 FP budget: <= 5% of hourly evaluation cycles per agent-day (<= 1 FP/agent-day).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .classifier import Classifier
from .loop_breaker import LoopBreaker
from .statistics import EwmaState, ewma_update, jsd_divergence
from .metamorphic import MetamorphicEngine

EWMA_MULTIPLIER = 2.0  # §4.2: daily cost must ALSO exceed 2.0× EWMA-µ

# ---------------------------------------------------------------- §4.2 map

SEVERITY_ORDER = {"Info": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4, "Emergency": 5}


@dataclass(frozen=True)
class Rule:
    signal: str
    event_type: str          # escalation | report_item
    reason: str              # budget|permission|quality|unknown|drift|system_health
    sla_hours: float
    protection: str
    severity: str
    fires_during_calibration: bool   # §3.3: only Info/Emergency signals fire in-window


SIGNAL_MAP: dict[str, Rule] = {
    "loop>=2": Rule("loop>=2", "escalation", "quality", 0.5,
                    "task quarantine; loop breaker open", "Emergency", True),
    "permission.deny>0.20": Rule("permission.deny>0.20", "escalation", "permission", 4.0,
                                 "external tool permissions frozen", "Critical", False),
    "cost.daily>2x_ewma": Rule("cost.daily>2x_ewma", "escalation", "budget", 24.0,
                               "model downgrade proposal (operator-approved)", "Critical", False),
    "error.new_class_seen": Rule("error.new_class_seen", "escalation", "unknown", 24.0,
                                 "triage with new-error-pattern label", "Critical", True),
    "error.rate>0.20": Rule("error.rate>0.20", "escalation", "quality", 4.0,
                            "responsible agent's tasks triaged (R15)", "Critical", False),
    "latency.retry>=3": Rule("latency.retry>=3", "escalation", "quality", 4.0,
                             "task requeued; resource provider audited (R15)", "High", False),
    "drift.tool_distribution>0.40": Rule("drift.tool_distribution>0.40", "report_item", "drift", 168.0,
                                         "weekly report behavior-deviation item", "Medium", False),
    "drift.output_quality": Rule("drift.output_quality", "report_item", "drift", 168.0,
                                 "weekly report: end-state divergence on equivalent tasks", "Medium", False),
    "escalation.age_max>24": Rule("escalation.age_max>24", "escalation", "system_health", 2.0,
                                  "self-escalation; PagerDuty/SMS (R14)", "Emergency", True),
}


@dataclass
class Alarm:
    signal: str
    event_type: str
    reason: str
    severity: str
    sla_hours: float
    protection: str
    suppressed: bool = False   # §3.3: blocked by calibration window (recorded, not escalated)


@dataclass
class FpBudget:
    """R10: false positives per agent-day over hourly cycles; budget ratio <= 5%."""
    cycles: int = 0
    false_positives: int = 0

    def record_cycle(self, false_positive: bool = False) -> None:
        self.cycles += 1
        if false_positive:
            self.false_positives += 1

    @property
    def ratio(self) -> float:
        return self.false_positives / self.cycles if self.cycles else 0.0

    @property
    def within_budget(self) -> bool:
        return self.ratio <= 0.05


@dataclass
class CalibrationWindow:
    """§3.3: 14 days per agent; synthetic agents start pre-closed (R10/§7.3)."""
    days: int = 14
    closed: bool = False
    opened_at: datetime = field(default_factory=datetime.utcnow)

    def closed_by(self) -> datetime:
        return self.opened_at + timedelta(days=self.days)


class FleetApd:
    """Owns per-agent detector state and maps facts onto the §4.2 map."""

    def __init__(self) -> None:
        self.ewma: dict[str, EwmaState] = {}
        self.classifiers: dict[str, Classifier] = {}
        self.loop_breakers: dict[str, LoopBreaker] = {}
        self.metamorphic = MetamorphicEngine()
        self.windows: dict[str, CalibrationWindow] = {}
        self.fp_budget = FpBudget()
        self.audit_notes: list[str] = []   # baseline_audit entries (§3.3, R5)

    # -- state accessors -----------------------------------------------------
    def window_for(self, agent_id: str, *, synthetic: bool = False) -> CalibrationWindow:
        if agent_id not in self.windows:
            self.windows[agent_id] = CalibrationWindow(closed=synthetic)
        return self.windows[agent_id]

    def classifier_for(self, agent_id: str) -> Classifier:
        return self.classifiers.setdefault(agent_id, Classifier())

    def loop_breaker_for(self, task_id: str) -> LoopBreaker:
        return self.loop_breakers.setdefault(task_id, LoopBreaker())

    # -- fact evaluators (compose §3.2 primitives) ---------------------------
    def fact_cost_spike(self, agent_id: str, daily_cost: float, *, calibrated: bool) -> bool:
        """§4.2 conjunctive rule: Z > 2.5 AND daily > 2.0× EWMA-µ."""
        state = self.ewma.setdefault(agent_id, EwmaState())
        state.calibrated = calibrated
        result = ewma_update(state, daily_cost)
        return bool(result.alarm and result.mu > 0 and daily_cost > EWMA_MULTIPLIER * result.mu)

    def fact_error_class(self, agent_id: str, error_class: str, *,
                         loop_detected: bool = False) -> tuple[str, bool]:
        """Classify (loop passthrough) + observe; returns (class, first_seen?)."""
        if loop_detected:
            return "loop", False
        classified = self.classifier_for(agent_id).classify(error_class)
        is_new = self.classifier_for(agent_id).observe(classified)
        return classified, is_new

    @staticmethod
    def fact_tool_drift(p7d_counts: dict[str, float], q24h_counts: dict[str, float]) -> bool:
        return jsd_divergence(p7d_counts, q24h_counts).band == "alarm"

    def fact_loop(self, task_id: str, tool_name: str, arguments: object) -> bool:
        return self.loop_breaker_for(task_id).feed(tool_name, arguments)

    def fact_new_class(self, agent_id: str, error_class: str) -> bool:
        return self.classifier_for(agent_id).observe(error_class)

    def fact_output_quality(self, task_template: str, end_state: dict) -> bool:
        violation = self.metamorphic.observe_end_state(task_template, end_state)
        if violation:
            self.audit_notes.append(f"drift.output_quality:{task_template}")
        return violation

    # -- §4.2 mapping --------------------------------------------------------
    def evaluate(self, facts: dict[str, bool], agent_id: str) -> list[Alarm]:
        """Map evaluated facts onto SIGNAL_MAP under §3.3 calibration discipline."""
        window = self.window_for(agent_id)
        alarms: list[Alarm] = []
        for signal, fired in facts.items():
            if not fired or signal not in SIGNAL_MAP:
                continue
            rule = SIGNAL_MAP[signal]
            suppressed = not window.closed and not rule.fires_during_calibration
            if suppressed:
                self.audit_notes.append(f"calibration_suppressed:{agent_id}:{signal}")
            alarms.append(Alarm(
                signal=rule.signal, event_type=rule.event_type, reason=rule.reason,
                severity=rule.severity, sla_hours=rule.sla_hours,
                protection=rule.protection, suppressed=suppressed,
            ))
        return alarms

    # -- R14: ticket aging / self-escalation ---------------------------------
    @staticmethod
    def fact_ticket_aging(created_at: datetime, now: datetime, *, limit_h: float = 24.0) -> bool:
        return (now - created_at) > timedelta(hours=limit_h)
