"""Dependency-light BIM round-trip manifest; native IFC is optional and never faked."""
from __future__ import annotations
import copy, json, hashlib
from pathlib import Path

def normalize_registry(registry):
    data=registry.export_dict() if hasattr(registry,"export_dict") else registry
    return copy.deepcopy(data)

def roundtrip_manifest(registry):
    data=normalize_registry(registry)
    encoded=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return {"schema":"structuralpro-bim-roundtrip-1","digest":hashlib.sha256(encoded).hexdigest(),"registry":data}

def write_manifest(registry,path):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(roundtrip_manifest(registry),ensure_ascii=False,sort_keys=True,indent=2),encoding="utf-8")
    return p

def verify_manifest(manifest):
    if manifest.get("schema")!="structuralpro-bim-roundtrip-1": return False
    data=manifest.get("registry")
    if data is None: return False
    encoded=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return manifest.get("digest")==hashlib.sha256(encoded).hexdigest()
