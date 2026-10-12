from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class GateEvidence:
    gate: str
    status: str
    source: str
    observed_at: str

@dataclass(frozen=True)
class E2EReadiness:
    gate_count: int
    decision: str
    fingerprint: str

def validate_gates(gates):
    if not gates:
        raise ValueError("end-to-end readiness requires evidence")
    for g in gates:
        if not all((g.gate.strip(),g.status.strip(),g.source.strip(),g.observed_at.strip())):
            raise ValueError("incomplete gate evidence")
        if g.status not in {"pass","fail","unknown"}:
            raise ValueError("unsupported gate status")

def assess_e2e(gates):
    validate_gates(gates)
    statuses={g.status for g in gates}
    decision="no_go" if "fail" in statuses else ("needs_evidence" if "unknown" in statuses else "go")
    payload="|".join(sorted(f"{g.gate}|{g.status}|{g.source}|{g.observed_at}" for g in gates))
    return E2EReadiness(len(gates),decision,sha256(payload.encode()).hexdigest())
