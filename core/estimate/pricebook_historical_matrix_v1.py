from __future__ import annotations
import json
from hashlib import sha256
YEARS=tuple(range(1399,1405))
DISCIPLINES=("ابنیه","تاسیسات مکانیکی","تاسیسات برقی","مرمت بناهای تاریخی")
def required_cells(): return tuple((y,d) for y in YEARS for d in DISCIPLINES)
def validate_cells(cells):
    expected=set(required_cells()); actual={(int(c["year"]),str(c["discipline"])) for c in cells}
    missing=sorted(expected-actual); duplicates=len(cells)!=len(actual)
    bad=[c for c in cells if not c.get("sha256") or not c.get("source_url") or not c.get("local_path") or int(c.get("row_count",0))<=0]
    if missing or duplicates or bad: raise ValueError(f"incomplete official matrix: missing={missing}, duplicates={duplicates}, invalid={len(bad)}")
    fp=sha256("|".join(sorted(f'{c["year"]}|{c["discipline"]}|{c["sha256"]}|{c["row_count"]}' for c in cells)).encode()).hexdigest()
    return {"complete":True,"cells":len(cells),"fingerprint":fp}
def load_manifest(path):
    with open(path,encoding="utf-8") as f: data=json.load(f)
    return validate_cells(data.get("cells",data))
