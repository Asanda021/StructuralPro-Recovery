from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class IranPriceEvidence:
    item_code: str
    description: str
    unit: str
    rate: float
    currency: str
    source: str
    list_name: str
    version: str
    effective_date: str
    observed_at: str

def validate(evidence):
    if not evidence: raise ValueError("price evidence required")
    keys=set()
    for x in evidence:
        if not all((x.item_code,x.description,x.unit,x.currency,x.source,x.list_name,x.version,x.effective_date,x.observed_at)): raise ValueError("incomplete price evidence")
        if x.rate < 0: raise ValueError("negative rate")
        k=(x.item_code,x.unit,x.currency,x.version)
        if k in keys: raise ValueError("duplicate price evidence")
        keys.add(k)

def fingerprint(evidence):
    validate(evidence)
    payload="|".join(sorted(f"{x.item_code}|{x.description}|{x.unit}|{x.rate}|{x.currency}|{x.source}|{x.list_name}|{x.version}|{x.effective_date}|{x.observed_at}" for x in evidence))
    return sha256(payload.encode()).hexdigest()
