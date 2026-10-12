"""Production hardening checks: deterministic, offline and fail-closed."""
from __future__ import annotations
import importlib, time

REQUIRED_MODULES=("core.engineering.deep_quantity","core.drawings.production_workflow","core.bim.roundtrip",
                  "core.pipeline.production","core.iran.data_pack","core.reports.bundle","core.revisions.impact")

def run_hardening_checks():
    rows=[]
    for name in REQUIRED_MODULES:
        start=time.perf_counter()
        try: importlib.import_module(name); ok=True; error=""
        except Exception as exc: ok=False; error=str(exc)
        rows.append({"module":name,"ok":ok,"seconds":time.perf_counter()-start,"error":error})
    return {"ok":all(x["ok"] for x in rows),"checks":rows,"offline":True,"fail_closed":True}
