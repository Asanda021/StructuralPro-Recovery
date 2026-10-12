"""P45 — evidence-first project collaboration contracts."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json

_ROLES={"owner","admin","editor","reviewer","viewer"}
@dataclass(frozen=True)
class Member:
    user_id:str; role:str
@dataclass(frozen=True)
class Activity:
    activity_id:str; user_id:str; action:str; entity_id:str; source_id:str

def _text(*v):
    if any(not isinstance(x,str) or not x.strip() for x in v): raise ValueError("collaboration identity is incomplete")

def validate_members(members:list[Member])->tuple[Member,...]:
    seen=set(); out=[]
    for m in members:
        _text(m.user_id,m.role)
        if m.role not in _ROLES: raise ValueError("invalid collaboration role")
        if m.user_id in seen: raise ValueError("duplicate collaborator")
        seen.add(m.user_id); out.append(m)
    if not out: raise ValueError("at least one collaborator is required")
    if sum(m.role=="owner" for m in out)!=1: raise ValueError("exactly one owner is required")
    return tuple(out)

def record_activity(activity:Activity)->dict[str,str]:
    _text(activity.activity_id,activity.user_id,activity.action,activity.entity_id,activity.source_id)
    return activity.__dict__.copy()

def approval_state(*,review_id:str,reviewer_id:str,decision:str,source_id:str)->dict[str,str]:
    _text(review_id,reviewer_id,decision,source_id)
    if decision not in {"pending","approved","rejected","changes_requested"}: raise ValueError("invalid review decision")
    return {"review_id":review_id,"reviewer_id":reviewer_id,"decision":decision,"source_id":source_id}

def collaboration_fingerprint(project_id:str,members:list[Member],activities:list[Activity])->str:
    _text(project_id)
    payload={"project_id":project_id,"members":[m.__dict__ for m in validate_members(members)],"activities":[record_activity(a) for a in activities]}
    return sha256(json.dumps(payload,sort_keys=True,separators=(",",":" )).encode()).hexdigest()
