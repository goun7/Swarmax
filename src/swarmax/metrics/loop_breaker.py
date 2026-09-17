"""Runaway-loop breaker — paper §3.2-3.

h_i = SHA256(tool_name || normalize_json(arguments))
3 consecutive identical hashes (h_i = h_{i-1} = h_{i-2}) => task quarantine
(KILL_CIRCUIT_OPEN) + guard-plane event + human escalation.

Rationale: n-gram detectability of repetition pathology —
Holtzman et al., *The Curious Case of Neural Text Degeneration*, ICLR 2020.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

KILL_CIRCUIT_OPEN = "KILL_CIRCUIT_OPEN"
LOOP_RUN_THRESHOLD = 3  # consecutive identical hashes that trip the breaker


def normalize_arguments(arguments: object) -> str:
    """Canonical JSON: sorted keys, no whitespace — hash-stable across key order."""
    return json.dumps(arguments, sort_keys=True, separators=(",", ":"))


def call_hash(tool_name: str, arguments: object) -> str:
    return hashlib.sha256(f"{tool_name}{normalize_arguments(arguments)}".encode("utf-8")).hexdigest()


@dataclass
class LoopBreaker:
    """Per-task breaker: feed each guard-plane tool_call in order."""
    hashes: list[str] = field(default_factory=list)
    opened: bool = False

    def feed(self, tool_name: str, arguments: object) -> bool:
        """Record one tool call; returns True exactly when the breaker opens."""
        if self.opened:
            return True
        h = call_hash(tool_name, arguments)
        self.hashes.append(h)
        if len(self.hashes) >= LOOP_RUN_THRESHOLD and all(
            h == self.hashes[-j] for j in (1, 2, 3)
        ):
            self.opened = True
        return self.opened
