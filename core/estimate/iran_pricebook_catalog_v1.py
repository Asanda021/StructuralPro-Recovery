from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class PricebookSource:
    discipline: str
    year: int
    title: str
    source: str
    format: str
    verified_at: str

RECENT_ABNIEH_YEARS=(1399,1400,1401,1402,1403,1404)

def validate(sources):
    if not sources: raise ValueError("pricebook sources required")
    seen=set()
    for s in sources:
        if s.discipline!="ابنیه": raise ValueError("unsupported discipline")
        if s.year < 1300 or s.year > 1500: raise ValueError("invalid year")
        if not all((s.title,s.source,s.format,s.verified_at)): raise ValueError("incomplete source")
        k=(s.discipline,s.year,s.format)
        if k in seen: raise ValueError("duplicate pricebook source")
        seen.add(k)

def coverage(sources):
    validate(sources)
    years=sorted({s.year for s in sources})
    return {"discipline":"ابنیه","years":years,"count":len(years),
            "recent_catalog_complete": all(y in years for y in RECENT_ABNIEH_YEARS)}

def fingerprint(sources):
    validate(sources)
    p="|".join(sorted(f"{s.discipline}|{s.year}|{s.title}|{s.source}|{s.format}|{s.verified_at}" for s in sources))
    return sha256(p.encode()).hexdigest()
