"""MAST-aligned error classifier — paper §3.2-6 (E7: arXiv:2503.13657, NeurIPS 2025 D&B).

Swarmax classes and their MAST families:
- spec_ambiguity       -> Specification Issues
- interagent_mismatch  -> Inter-Agent Misalignment
- verification_fail    -> Task Verification
- tool_fail/parse/timeout/auth -> mechanical-operational (outside MAST)
- loop                 -> Inter-Agent Misalignment (circulation)
- unknown              -> first-seen sentinel (never collapses into a known class)
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAST_FAMILIES: dict[str, str] = {
    "spec_ambiguity": "Specification Issues",
    "interagent_mismatch": "Inter-Agent Misalignment",
    "verification_fail": "Task Verification",
    "tool_fail": "(mechanical-operational)",
    "parse": "(mechanical-operational)",
    "timeout": "(mechanical-operational)",
    "auth": "(mechanical-operational)",
    "schema_drift": "(mechanical-operational; ReliabilityBench chaos class)",
    "partial_response": "(mechanical-operational; ReliabilityBench chaos class)",
    "loop": "Inter-Agent Misalignment (circulation)",
    "unknown": "(sentinel)",
}
KNOWN_CLASSES = frozenset(MAST_FAMILIES) - {"unknown"}

# §4.2 triggers keyed by class
CLASS_TRIGGERS = {"loop": "loop>=2", "unknown": "new_class_seen"}

# Classes a production agent is assumed to have produced during onboarding, so only
# genuinely novel signatures (or the unknown sentinel) trip new_class_seen. Keeps
# baseline synthetic traffic from self-triggering the sentinel (§3.1 discipline).
PRESEEN_CLASSES = {"tool_fail", "parse", "timeout", "auth"}


@dataclass
class Classifier:
    """Per-agent classifier: keeps the historically seen class set (§3.1 new_class_seen)."""
    seen: set[str] = field(default_factory=set)

    def classify(self, raw_error: object, *, loop_detected: bool = False) -> str:
        """Map a raw error (string/exception/None) onto the taxonomy."""
        if loop_detected:
            return "loop"
        if raw_error is None:
            return ""  # success: no error class
        text = str(raw_error).lower()
        if "schema drift" in text or "schema_drift" in text:
            return "schema_drift"
        if "partial response" in text or "truncated" in text:
            return "partial_response"
        if "timeout" in text or "timed out" in text:
            return "timeout"
        if "auth" in text or "401" in text or "403" in text or "permission" in text:
            return "auth"
        if "parse" in text or "json" in text or "schema" in text:
            return "parse"
        if "tool" in text or "api" in text or "500" in text or "429" in text:
            return "tool_fail"
        if "verify" in text or "validation" in text or "expected" in text:
            return "verification_fail"
        if "mismatch" in text or "protocol" in text or "handoff" in text:
            return "interagent_mismatch"
        if "ambiguous" in text or "spec" in text or "unclear" in text:
            return "spec_ambiguity"
        return "unknown"

    def observe(self, error_class: str) -> bool:
        """Record an observed class; True on first-ever sight (§3.1 new_class_seen:
        "first time in the agent's historical set" — includes the `unknown` sentinel
        and any known taxonomy class this agent has never produced before)."""
        if error_class in self.seen:
            return False
        self.seen.add(error_class)
        return True
