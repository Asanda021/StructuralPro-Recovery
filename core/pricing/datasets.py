"""Verified local price-dataset ingestion boundary."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .catalog import PriceCatalog

def load_dataset(path: str|Path, *, expected_year: int|None=None, expected_group: str|None=None) -> tuple[PriceCatalog,dict[str,Any]]:
    p=Path(path)
    data=json.loads(p.read_text(encoding="utf-8"))
    meta=data.get("metadata",{})
    if expected_year is not None and int(meta.get("year",-1))!=int(expected_year): raise ValueError("dataset year mismatch")
    if expected_group is not None and str(meta.get("group"))!=expected_group: raise ValueError("dataset group mismatch")
    if not meta.get("source") or not meta.get("verified"): raise ValueError("dataset source must be verified")
    c=PriceCatalog()
    c.import_csv(data["csv"])
    return c,meta

def export_dataset(catalog: PriceCatalog, path: str|Path, *, year:int, group:str, source:str, verified:bool=True):
    payload={"metadata":{"year":int(year),"group":group,"source":source,"verified":bool(verified)},
             "csv":catalog.export_csv(year)}
    Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
