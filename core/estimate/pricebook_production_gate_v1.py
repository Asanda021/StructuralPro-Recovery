"""P88/P89 — production pricebook completeness and normalized ingestion gates."""
from __future__ import annotations
from hashlib import sha256
from core.estimate.item_code_normalization_v1 import code_key

REQUIRED_YEARS=tuple(range(1399,1405))
REQUIRED_DISCIPLINES=("ابنیه","تاسیسات مکانیکی","تاسیسات برقی","مرمت بناهای تاریخی")

def normalize_rows(rows):
    out=[]
    for r in rows:
        code,unit=code_key(r.item_code,r.unit)
        if not code or not unit or not r.description:
            raise ValueError("incomplete normalized pricebook row")
        out.append(r.__class__(r.year,r.discipline,code,r.description,unit,r.unit_price,r.source_sha256,r.source_file))
    return tuple(out)

def coverage_gate(rows, years=REQUIRED_YEARS, disciplines=REQUIRED_DISCIPLINES):
    if not rows: raise ValueError("pricebook dataset is empty")
    present={(r.year,r.discipline) for r in rows}
    missing=[(y,d) for y in years for d in disciplines if (y,d) not in present]
    hashes={r.source_sha256 for r in rows if r.source_sha256}
    if not hashes: raise ValueError("source provenance missing")
    return {"rows":len(rows),"missing":missing,"complete":not missing,
            "years":sorted({r.year for r in rows}),
            "disciplines":sorted({r.discipline for r in rows}),
            "source_count":len(hashes),
            "fingerprint":sha256("|".join(sorted(f"{r.year}|{r.discipline}|{r.item_code}|{r.unit}|{r.unit_price}|{r.source_sha256}" for r in rows)).encode()).hexdigest()}
