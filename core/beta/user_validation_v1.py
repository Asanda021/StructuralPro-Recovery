"""P59 — evidence-first real-user validation contracts."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class UserValidationEvidence:
    project_id: str
    reviewer_id: str
    task: str
    expected_quantity: float
    system_quantity: float
    unit: str
    source: str
    observed_at: str
    disposition: str

@dataclass(frozen=True)
class UserValidationResult:
    project_id: str
    sample_count: int
    mean_relative_error: float
    fingerprint: str
    disposition: str

def validate_evidence(rows: tuple[UserValidationEvidence, ...]) -> None:
    if not rows:
        raise ValueError("real-user validation requires evidence")
    for row in rows:
        if not all((row.project_id.strip(), row.reviewer_id.strip(), row.task.strip(), row.unit.strip(), row.source.strip(), row.observed_at.strip(), row.disposition.strip())):
            raise ValueError("incomplete user validation evidence")
        if row.expected_quantity < 0 or row.system_quantity < 0:
            raise ValueError("quantities cannot be negative")

def evaluate(rows: tuple[UserValidationEvidence, ...]) -> UserValidationResult:
    validate_evidence(rows)
    errors=[]
    for row in rows:
        if row.expected_quantity == 0:
            if row.system_quantity != 0:
                raise ValueError("non-zero system quantity against zero reference")
            errors.append(0.0)
        else:
            errors.append(abs(row.system_quantity-row.expected_quantity)/row.expected_quantity)
    payload="|".join(sorted(f"{r.project_id}|{r.reviewer_id}|{r.task}|{r.expected_quantity}|{r.system_quantity}|{r.unit}|{r.source}|{r.observed_at}|{r.disposition}" for r in rows))
    fp=sha256(payload.encode()).hexdigest()
    dispositions={r.disposition for r in rows}
    disposition="needs_evidence" if "needs_evidence" in dispositions else ("accepted" if dispositions == {"accepted"} else "review")
    return UserValidationResult(rows[0].project_id,len(rows),sum(errors)/len(errors),fp,disposition)
