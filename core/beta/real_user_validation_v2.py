from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class UserTaskEvidence:
    project_id: str
    reviewer_id: str
    task: str
    expected_quantity: float
    system_quantity: float
    unit: str
    source: str
    observed_at: str
    disposition: str

def validate(rows):
    if not rows: raise ValueError("user validation evidence required")
    for r in rows:
        if not all((r.project_id,r.reviewer_id,r.task,r.unit,r.source,r.observed_at,r.disposition)): raise ValueError("incomplete user evidence")
        if r.expected_quantity < 0 or r.system_quantity < 0: raise ValueError("negative quantity")
        if r.expected_quantity == 0 and r.system_quantity != 0: raise ValueError("nonzero system against zero reference")
        if r.disposition not in {"accepted","review","needs_evidence"}: raise ValueError("invalid disposition")

def assess(rows, tolerance=0.05):
    validate(rows)
    errors=[abs(r.system_quantity-r.expected_quantity)/r.expected_quantity if r.expected_quantity else 0 for r in rows]
    disposition="needs_evidence" if any(r.disposition=="needs_evidence" for r in rows) else ("review" if any(e>tolerance or r.disposition=="review" for e,r in zip(errors,rows)) else "accepted")
    return {"sample_count":len(rows),"mean_relative_error":sum(errors)/len(errors),"disposition":disposition,"fingerprint":fingerprint(rows)}

def fingerprint(rows):
    validate(rows)
    payload="|".join(sorted(f"{r.project_id}|{r.reviewer_id}|{r.task}|{r.expected_quantity}|{r.system_quantity}|{r.unit}|{r.source}|{r.observed_at}|{r.disposition}" for r in rows))
    return sha256(payload.encode()).hexdigest()
