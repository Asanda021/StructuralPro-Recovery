"""P47 — explicit commercial licensing/subscription contracts.

No payment processor, price, entitlement or renewal is fabricated by this layer.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

_PLANS={"trial","standard","professional","enterprise"}
@dataclass(frozen=True)
class License:
    license_id:str; user_id:str; plan:str; starts:date; expires:date; status:str="active"

def validate_license(x:License)->License:
    if not all(isinstance(v,str) and v.strip() for v in (x.license_id,x.user_id,x.plan,x.status)): raise ValueError("license identity is incomplete")
    if x.plan not in _PLANS: raise ValueError("unknown plan")
    if x.expires < x.starts: raise ValueError("license expiry precedes start")
    if x.status not in {"active","expired","revoked","suspended"}: raise ValueError("invalid license status")
    return x

def entitlement(license:License, *, feature:str, today:date)->bool:
    validate_license(license)
    if not isinstance(feature,str) or not feature.strip(): raise ValueError("feature is required")
    if license.status != "active" or not (license.starts <= today <= license.expires): return False
    return True

def subscription_summary(licenses:list[License])->dict[str,object]:
    seen=set(); active=[]
    for x in licenses:
        validate_license(x)
        if x.license_id in seen: raise ValueError("duplicate license")
        seen.add(x.license_id); active.append(x)
    return {"licenses":len(active),"plans":sorted({x.plan for x in active}),"active":sum(x.status=="active" for x in active)}
