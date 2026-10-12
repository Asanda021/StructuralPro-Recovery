"""Deterministic professional report bundle manifest and export orchestration."""
from __future__ import annotations
from pathlib import Path
import hashlib, json

def build_bundle_manifest(files, *, project_id="", revision=""):
    rows=[]
    for f in sorted(Path(x) for x in files):
        if not f.is_file(): raise FileNotFoundError(f)
        rows.append({"name":f.name,"size":f.stat().st_size,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()})
    return {"schema":"structuralpro-report-bundle-1","project_id":str(project_id),"revision":str(revision),"files":rows}

def write_bundle_manifest(files,path,**meta):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(build_bundle_manifest(files,**meta),ensure_ascii=False,sort_keys=True,indent=2),encoding="utf-8")
    return p
