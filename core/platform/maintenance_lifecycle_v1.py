"""Deterministic maintenance lifecycle and transition guard."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

STATES = ("draft", "active", "maintenance", "retired")
_ALLOWED: Mapping[str, tuple[str, ...]] = {
    "draft": ("active", "retired"),
    "active": ("maintenance", "retired"),
    "maintenance": ("active", "retired"),
    "retired": (),
}


@dataclass(frozen=True)
class LifecycleDecision:
    allowed: bool
    reason: str


def can_transition(current: str, target: str) -> LifecycleDecision:
    if current not in STATES or target not in STATES:
        return LifecycleDecision(False, "unknown lifecycle state")
    if current == target:
        return LifecycleDecision(True, "no-op")
    if target in _ALLOWED[current]:
        return LifecycleDecision(True, "transition allowed")
    return LifecycleDecision(False, "transition blocked")


def require_transition(current: str, target: str) -> LifecycleDecision:
    decision = can_transition(current, target)
    if not decision.allowed:
        raise RuntimeError(decision.reason)
    return decision
