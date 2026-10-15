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
    """Canonical JSON: sorted keys, no whitespace — hash-stable across key order.

    Karisik anahtar turleri (int+str) json.dumps(sort_keys=True) ile TypeError
    firlatir (SW-LB-1B, Py3.14) — once (tip-adi, repr) ile siralanip string
    anahtara cevrilir; anahtar-tip carpismasi ({1:a} vs {"1":a}) da boylece
    cozulur. Deger-seviyesi tuple/list carpismasi (BULGU-4) kalir.
    """

    def _key(k: object) -> str:
        return k if isinstance(k, str) else f"{type(k).__qualname__}:{k!r}"

    def _norm(obj: object) -> object:
        if isinstance(obj, dict):
            return {_key(k): _norm(v) for k, v in sorted(obj.items(), key=lambda kv: _key(kv[0]))}
        if isinstance(obj, (list, tuple)):
            return [_norm(v) for v in obj]
        return obj

    return json.dumps(_norm(arguments), separators=(",", ":"))


def call_hash(tool_name: str, arguments: object) -> str:
    """sha256(uzunluk|tool_name|normalize(arguments)) — SW-LB-1A: uzunluk-on-eki
    ayraci olmadan f"{tool}{json}" birlestirmesi belirsizdi:
    call_hash("x", 12) == call_hash("x1", 2) == sha256("x12"). Ayirac ile
    (tool,args) ciftleri tek-tarafli-cozulebilir hale gelir.
    """
    return hashlib.sha256(f"{len(tool_name)}|{tool_name}|{normalize_arguments(arguments)}".encode("utf-8")).hexdigest()


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
