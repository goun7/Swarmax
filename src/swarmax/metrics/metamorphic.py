"""Metamorphic end-state oracle — paper §3.2-7 (E8: ReliabilityBench, arXiv:2601.06112).

Equivalence of semantically-equivalent runs is defined by END-STATE equality, not text
similarity: records created, notifications sent, file hashes, etc. End-state deviation
on an equivalent task template raises `drift.output_quality`.

Budget discipline (R5): the oracle consumes <= 1% of per-agent-day traffic as shadow
reruns; overruns are recorded to the baseline_audit ledger by the caller.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

OUTPUT_QUALITY_BUDGET = 0.01  # <= 1% shadow-rerun share (§3.2-7)


@dataclass
class MetamorphicEngine:
    """task_template -> list of end-state dicts observed for that template."""
    history: dict[str, list[dict]] = field(default_factory=dict)
    shadow_reruns: int = 0
    agent_day_events: int = 0
    budget_overruns: list[str] = field(default_factory=list)

    # -- budget (R5) ---------------------------------------------------------
    def record_traffic(self, events: int = 1) -> None:
        self.agent_day_events += events

    def can_shadow_rerun(self) -> bool:
        if self.agent_day_events <= 0:
            return True
        return (self.shadow_reruns + 1) / self.agent_day_events <= OUTPUT_QUALITY_BUDGET

    def note_shadow_rerun(self, task_id: str) -> None:
        """Call after actually executing a shadow rerun. Records an audit note when the
        rerun just taken pushed the share past the budget (post-increment check)."""
        self.shadow_reruns += 1
        if self.agent_day_events and (self.shadow_reruns / self.agent_day_events) > OUTPUT_QUALITY_BUDGET:
            self.budget_overruns.append(task_id)  # caller persists to baseline_audit

    # -- equivalence ---------------------------------------------------------
    def observe_end_state(self, task_template: str, end_state: dict) -> bool:
        """Record one run's end state for a template; True = drift.output_quality.

        A violation requires an established reference (>= 1 prior run for the template)
        and a differing end-state variable among runs that are semantically equivalent.
        """
        prior = self.history.setdefault(task_template, [])
        violation = False
        if prior:
            reference = prior[-1]  # compare against the most recent run
            violation = _end_states_diverge(reference, end_state)
        prior.append(end_state)
        return violation


def _end_states_diverge(reference: dict, candidate: dict) -> bool:
    """End-state equivalence: same key set and equal values (order-free, JSON-stable)."""
    if set(reference) != set(candidate):
        return True
    for k in reference:
        rv, cv = reference[k], candidate[k]
        if isinstance(rv, (dict, list)):
            if json.dumps(rv, sort_keys=True) != json.dumps(cv, sort_keys=True):
                return True
        elif rv != cv:
            return True
    return False
