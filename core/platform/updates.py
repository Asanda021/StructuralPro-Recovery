"""Offline-safe update manifest validation and rollback guard."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import Mapping
@dataclass(frozen=True)
class UpdateArtifact:
    version:str; channel:str; sha256:str; size:int; url:str=""
def _version(v:str)->tuple[int,int,int]:
    p=v.strip().split(".")
    if len(p)!=3 or any(not x.isdigit() for x in p): raise ValueError("version must use MAJOR.MINOR.PATCH")
    return tuple(map(int,p))  # type: ignore[return-value]
def validate_artifact(a:Mapping)->list[str]:
    e=[]
    try: _version(str(a.get("version","")))
    except ValueError: e.append("invalid version")
    if a.get("channel") not in {"stable","beta"}: e.append("invalid channel")
    h=str(a.get("sha256",""))
    if len(h)!=64 or any(c not in "0123456789abcdefABCDEF" for c in h): e.append("invalid sha256")
    if not isinstance(a.get("size"),int) or a.get("size")<0: e.append("invalid size")
    return e
def validate_update(current:str,artifact:Mapping,*,channel:str="stable")->list[str]:
    e=validate_artifact(artifact)
    if artifact.get("channel")!=channel: e.append("channel mismatch")
    if not e and _version(str(artifact["version"]))<=_version(current): e.append("downgrade or same-version update rejected")
    return e
def verify_bytes(data:bytes,expected_sha256:str,expected_size:int)->bool:
    return len(data)==expected_size and hashlib.sha256(data).hexdigest().casefold()==expected_sha256.casefold()
def canonical_manifest(manifest:Mapping)->str:
    return json.dumps(dict(manifest),ensure_ascii=False,sort_keys=True,separators=(",",":"))
