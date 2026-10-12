"""P51 — Production launch readiness contracts.

Evidence-first release gate. This module records observed readiness evidence and
never invents operational capacity, uptime, customer demand, or deployment facts.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Literal

Status = Literal["pass", "fail", "unknown"]
Severity = Literal["critical", "high", "medium", "low"]

@dataclass(frozen=True)
class ReadinessEvidence:
    gate: str
    status: Status
    source: str
    observed: str
    severity: Severity = "high"
    note: str = ""

@dataclass(frozen=True)
class LaunchGate:
    gate: str
    required: bool = True
    minimum_status: Status = "pass"

@dataclass(frozen=True)
class LaunchDecision:
    decision: Literal["go", "no_go", "needs_evidence"]
    blocking_gates: tuple[str, ...]
    unknown_gates: tuple[str, ...]
    fingerprint: str

def _payload(obj: object) -> dict:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: getattr(obj, k) for k in obj.__dataclass_fields__}
    raise TypeError("expected dataclass")

def fingerprint_evidence(evidence: Iterable[ReadinessEvidence]) -> str:
    evidence = tuple(evidence)
    for item in evidence:
        if not item.gate or not item.source or not item.observed:
            raise ValueError("readiness evidence requires gate, source and observed")
    rows = [_payload(x) for x in evidence]
    rows.sort(key=lambda x: (x["gate"], x["observed"], x["source"]))
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()

def evaluate_launch(gates: Iterable[LaunchGate], evidence: Iterable[ReadinessEvidence]) -> LaunchDecision:
    gates = tuple(gates)
    evidence = tuple(evidence)
    by_gate: dict[str, list[ReadinessEvidence]] = {}
    for item in evidence:
        if not item.gate or not item.source or not item.observed:
            raise ValueError("readiness evidence requires gate, source and observed")
        by_gate.setdefault(item.gate, []).append(item)

    blocking, unknown = [], []
    for gate in gates:
        items = by_gate.get(gate.gate, [])
        if not items:
            if gate.required:
                unknown.append(gate.gate)
            continue
        if gate.required and not any(x.status == gate.minimum_status for x in items):
            if any(x.status == "unknown" for x in items):
                unknown.append(gate.gate)
            else:
                blocking.append(gate.gate)

    if blocking:
        decision = "no_go"
    elif unknown:
        decision = "needs_evidence"
    else:
        decision = "go"
    return LaunchDecision(decision, tuple(sorted(blocking)), tuple(sorted(unknown)),
                          fingerprint_evidence(evidence))
