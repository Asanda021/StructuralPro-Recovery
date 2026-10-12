"""P62 — offline-first cloud collaboration/sync contract."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json

@dataclass(frozen=True)
class SyncEnvelope:
    project_id:str
    revision:int
    actor_id:str
    base_fingerprint:str
    payload_fingerprint:str
    operation:str

def make_envelope(project_id:str,revision:int,actor_id:str,base_fingerprint:str,payload:dict,operation:str)->SyncEnvelope:
    if revision < 1 or any(not isinstance(v,str) or not v.strip() for v in (project_id,actor_id,base_fingerprint,operation)):
        raise ValueError("invalid sync identity")
    if operation not in {"create","update","review","approve","archive"}: raise ValueError("invalid sync operation")
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    fp=sha256(raw.encode()).hexdigest()
    return SyncEnvelope(project_id,revision,actor_id,base_fingerprint,fp,operation)

def resolve_sync(local:SyncEnvelope, remote:SyncEnvelope)->str:
    if local.project_id != remote.project_id: raise ValueError("project mismatch")
    if remote.revision <= local.revision: return "stale_remote"
    if remote.base_fingerprint != local.payload_fingerprint: return "conflict"
    return "apply_remote"
