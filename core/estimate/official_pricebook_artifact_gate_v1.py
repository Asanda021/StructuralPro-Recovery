"""P99 — official artifact materialization/identity gate.

The gate downloads nothing implicitly. CI/workflows provide the artifact URL, then
this module proves the bytes are non-HTML, non-empty and hash-addressable.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path

def validate_artifact(path,expected_sha256=None,min_bytes=1024):
    p=Path(path)
    if not p.exists() or p.stat().st_size<min_bytes: raise ValueError("official artifact missing or too small")
    head=p.read_bytes()[:512].lstrip().lower()
    if b"<html" in head or b"<!doctype" in head: raise ValueError("official artifact resolved to HTML")
    digest=sha256(p.read_bytes()).hexdigest()
    if expected_sha256 and digest.lower()!=expected_sha256.lower(): raise ValueError("official artifact sha256 mismatch")
    return {"path":str(p),"bytes":p.stat().st_size,"sha256":digest}

def materialize_manifest(artifacts):
    if not artifacts: raise ValueError("artifact manifest is empty")
    required={"year","discipline","source","path","sha256"}
    for a in artifacts:
        if not required.issubset(a): raise ValueError("artifact manifest entry incomplete")
    return {"count":len(artifacts),"artifacts":sorted(artifacts,key=lambda x:(x["year"],x["discipline"]))}
