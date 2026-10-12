"""Cross-client parity and capability integrity boundary."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json

SUPPORTED=("windows","android","telegram")
@dataclass(frozen=True)
class CapabilityEvidence:
    capability_id:str
    platform:str
    status:str
    contract_version:str
    def __post_init__(self):
        if not self.capability_id.strip(): raise ValueError("capability_id is required")
        if self.platform not in SUPPORTED: raise ValueError("unsupported platform")
        if self.status not in {"implemented","contract","planned"}: raise ValueError("invalid capability status")
        if not self.contract_version.strip(): raise ValueError("contract_version is required")

def validate_parity(rows:list[CapabilityEvidence])->dict:
    if not rows: raise ValueError("capability evidence is required")
    grouped={}
    for row in rows:
        grouped.setdefault(row.capability_id,[]).append(row)
    for capability, items in grouped.items():
        versions={x.contract_version for x in items}
        if len(versions)!=1: raise ValueError(f"contract version mismatch: {capability}")
        if len({x.platform for x in items})!=len(items): raise ValueError(f"duplicate platform evidence: {capability}")
    return {"capabilities":len(grouped),"evidence":len(rows),"platforms":sorted({x.platform for x in rows}),"valid":True}

def parity_fingerprint(rows:list[CapabilityEvidence])->str:
    canonical=sorted(({"capability_id":x.capability_id,"platform":x.platform,"status":x.status,"contract_version":x.contract_version} for x in rows),key=lambda x:(x["capability_id"],x["platform"]))
    return sha256(json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def command_contract(platform:str, action:str, project_id:str, payload:dict)->dict:
    if platform not in SUPPORTED: raise ValueError("unsupported platform")
    if not action.strip() or not project_id.strip(): raise ValueError("request identity is required")
    if not isinstance(payload,dict): raise TypeError("payload must be a dictionary")
    return {"platform":platform,"action":action,"project_id":project_id,"payload":payload}
