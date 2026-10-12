"""Offline-safe product boundaries for external integrations and clients."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any

@dataclass(frozen=True)
class License:
    key: str
    product: str = "StructuralPro"
    expires_at: str | None = None
    features: tuple[str,...] = ()

def validate_license(license: License, feature: str | None = None) -> dict[str,Any]:
    if not license.key.strip(): return {"valid":False,"reason":"missing_key"}
    if feature and license.features and feature not in license.features: return {"valid":False,"reason":"feature_not_licensed"}
    if license.expires_at:
        try:
            if datetime.fromisoformat(license.expires_at) < datetime.now(): return {"valid":False,"reason":"expired"}
        except ValueError: return {"valid":False,"reason":"invalid_expiry"}
    return {"valid":True,"product":license.product,"feature":feature}

def project_fingerprint(project: dict[str,Any]) -> str:
    import json
    payload=json.dumps(project,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return sha256(payload).hexdigest()

def sync_envelope(project_id: str, version: int, payload: dict[str,Any]) -> dict[str,Any]:
    return {"project_id":str(project_id),"version":int(version),"payload":payload,"fingerprint":project_fingerprint(payload)}

def collaboration_member(user_id: str, role: str="viewer", name: str="") -> dict[str,str]:
    allowed={"owner","admin","engineer","estimator","reviewer","viewer"}
    if role not in allowed: raise ValueError("unsupported role")
    return {"user_id":str(user_id),"name":str(name),"role":role}

def add_comment(comments: list[dict[str,Any]], user_id: str, text: str, target: str="project") -> list[dict[str,Any]]:
    if not str(text).strip(): raise ValueError("comment text is required")
    out=list(comments)
    out.append({"user_id":str(user_id),"target":str(target),"text":str(text),"created_at":datetime.now().isoformat(timespec="seconds")})
    return out

def approval_state(status: str="draft", approved_by: str|None=None) -> dict[str,Any]:
    allowed={"draft","review","approved","rejected"}
    if status not in allowed: raise ValueError("invalid approval state")
    return {"status":status,"approved_by":approved_by}
