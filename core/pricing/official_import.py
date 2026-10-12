"""Official-price-list import boundary.

The importer accepts a documented CSV/XLSX export supplied by the user or an
official publisher. It does not fabricate or silently claim official prices.
"""
from __future__ import annotations
from pathlib import Path
import csv
from core.pricing.catalog import PriceCatalog

REQUIRED={"year","group","chapter","code","description","unit","unit_price"}

def import_official_csv(path,catalog:PriceCatalog,source="official-user-supplied"):
    p=Path(path)
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if not rows: raise ValueError("price-list CSV is empty")
    missing=REQUIRED-set(rows[0])
    if missing: raise ValueError("missing columns: "+",".join(sorted(missing)))
    normalized=[]
    for row in rows:
        normalized.append({k:row[k] for k in REQUIRED})
    n=catalog.import_csv(_to_csv(normalized),replace_year=True)
    return {"rows":n,"source":source,"path":str(p),"official_verified":source.startswith("official:")}

def _to_csv(rows):
    import io
    out=io.StringIO(); w=csv.DictWriter(out,fieldnames=sorted(REQUIRED)); w.writeheader(); w.writerows(rows)
    return out.getvalue()
