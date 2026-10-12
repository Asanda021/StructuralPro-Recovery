"""P321-P330 deterministic update/release trust boundary."""
from __future__ import annotations
import hashlib, json
from typing import Mapping
from .updates import validate_update, verify_bytes, canonical_manifest
from .release_security import find_embedded_secret_candidates

REQUIRED=("version","channel","sha256","size")

def manifest_digest(manifest:Mapping)->str:
    raw=canonical_manifest({k:v for k,v in manifest.items() if k!="manifest_sha256"}).encode()
    return hashlib.sha256(raw).hexdigest()

def validate_release_manifest(current_version:str, manifest:Mapping, *,
                              channel:str="stable", artifact:bytes|None=None)->list[str]:
    errors=[]
    for key in REQUIRED:
        if key not in manifest: errors.append(f"missing {key}")
    if errors: return errors
    errors.extend(validate_update(current_version,manifest,channel=channel))
    if artifact is not None and not verify_bytes(artifact,str(manifest["sha256"]),int(manifest["size"])):
        errors.append("artifact bytes do not match manifest")
    digest=str(manifest.get("manifest_sha256",""))
    if digest and digest.casefold()!=manifest_digest(manifest).casefold():
        errors.append("manifest integrity mismatch")
    return errors

def build_release_manifest(version:str,channel:str,data:bytes,metadata:Mapping|None=None)->dict:
    if not version.strip(): raise ValueError("version is required")
    if channel not in {"stable","beta"}: raise ValueError("invalid channel")
    m={"version":version,"channel":channel,"sha256":hashlib.sha256(data).hexdigest(),
       "size":len(data),"metadata":dict(sorted((metadata or {}).items()))}
    m["manifest_sha256"]=manifest_digest(m)
    return m

def release_trust_ready(current_version:str,manifest:Mapping,*,channel:str="stable",
                        artifact:bytes|None=None)->bool:
    if find_embedded_secret_candidates(): return False
    return not validate_release_manifest(current_version,manifest,channel=channel,artifact=artifact)
