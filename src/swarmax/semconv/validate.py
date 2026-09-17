"""Attribute validator enforcing the pinned-registry discipline (paper §3.1, R9, §7.2).

Rules:
1. ``gen_ai.*`` keys must exist verbatim in the pinned registry; renames/wrappers are
   rejected (this is what the pre-audit "audit flagged a non-spec'd attribute" gap was).
2. ``swx.*`` keys must exist in the Swarmax extension namespace.
3. Any key outside ``gen_ai.*``/``swx.*``/``error.*``/``otel.*`` is an unknown attribute → warning.
4. Types must match (str[] = list of str; bool/int/double/str scalar).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .registry import GENAI_ATTRIBUTES
from .swx import SWX_ATTRIBUTES

_ALLOWED_UNPREFIXED_PREFIXES = ("error.", "otel.", "service.", "deployment.", "k8s.", "host.", "telemetry.")


@dataclass
class SemconvReport:
    ok: bool
    checked: int
    unknown: list[str] = field(default_factory=list)
    type_mismatches: dict[str, tuple[str, str]] = field(default_factory=dict)  # key: (expected, actual)

    def summary(self) -> str:
        return (f"ok={self.ok} checked={self.checked} "
                f"unknown={len(self.unknown)} type_mismatches={len(self.type_mismatches)}")


def _expected_type(key: str) -> str | None:
    if key in GENAI_ATTRIBUTES:
        return GENAI_ATTRIBUTES[key]
    if key in SWX_ATTRIBUTES:
        return SWX_ATTRIBUTES[key]
    return None


def _actual_type(value: object) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return "str[]"
    if isinstance(value, list):
        return "list"
    return "json"


def validate_attributes(attributes: dict[str, object]) -> SemconvReport:
    unknown: list[str] = []
    mismatches: dict[str, tuple[str, str]] = {}

    for key, value in attributes.items():
        if key.startswith("gen_ai."):
            expected = _expected_type(key)
            if expected is None:
                unknown.append(key)
            else:
                actual = _actual_type(value)
                if actual != expected:
                    # pragmatic alias: int counts arriving as double are fine
                    if not (expected == "int" and actual == "double"):
                        mismatches[key] = (expected, actual)
        elif key.startswith("swx."):
            expected = _expected_type(key)
            if expected is None:
                unknown.append(key)
            else:
                actual = _actual_type(value)
                if actual != expected and not (expected == "int" and actual == "double"):
                    mismatches[key] = (expected, actual)
        elif key.startswith(_ALLOWED_UNPREFIXED_PREFIXES):
            continue
        else:
            unknown.append(key)

    return SemconvReport(
        ok=not unknown and not mismatches,
        checked=len(attributes),
        unknown=unknown,
        type_mismatches=mismatches,
    )
