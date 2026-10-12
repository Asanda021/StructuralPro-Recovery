from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class OperationalSignal:
    service: str
    environment: str
    event: str
    status: str
    source: str
    observed_at: str

@dataclass(frozen=True)
class ObservabilityAssessment:
    signal_count: int
    decision: str
    fingerprint: str

def validate_signals(signals):
    if not signals:
        raise ValueError("observability requires explicit operational evidence")
    for s in signals:
        if not all((s.service.strip(),s.environment.strip(),s.event.strip(),s.status.strip(),s.source.strip(),s.observed_at.strip())):
            raise ValueError("incomplete operational signal")
        if s.status not in {"healthy","degraded","failed","unknown"}:
            raise ValueError("unsupported operational status")

def assess(signals):
    validate_signals(signals)
    statuses={s.status for s in signals}
    decision="no_go" if "failed" in statuses else ("needs_evidence" if "unknown" in statuses or "degraded" in statuses else "go")
    payload="|".join(sorted(f"{s.service}|{s.environment}|{s.event}|{s.status}|{s.source}|{s.observed_at}" for s in signals))
    return ObservabilityAssessment(len(signals),decision,sha256(payload.encode()).hexdigest())
