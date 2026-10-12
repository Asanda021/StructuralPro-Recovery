"""Fail-closed collaboration/cloud enterprise boundary for P261-P270."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,math

VALID_ROLES=frozenset({"owner","admin","editor","reviewer","viewer"})
VALID_EVENTS=frozenset({"created","updated","review_requested","approved","rejected","synced"})

@dataclass(frozen=True)
class TenantIdentity:
    tenant_id:str
    project_id:str
    user_id:str
    role:str
    def validate(self):
        if not all(x.strip() for x in (self.tenant_id,self.project_id,self.user_id)):
            raise ValueError("tenant identity is incomplete")
        if self.role not in VALID_ROLES: raise ValueError("invalid role")
        return self

@dataclass(frozen=True)
class SessionEvidence:
    session_id:str
    tenant_id:str
    user_id:str
    online:bool
    revision:int
    def validate(self):
        if not all(x.strip() for x in (self.session_id,self.tenant_id,self.user_id)):
            raise ValueError("session identity is incomplete")
        if not isinstance(self.online,bool) or not isinstance(self.revision,int) or self.revision<0:
            raise ValueError("invalid session state")
        return self

@dataclass(frozen=True)
class NotificationEvidence:
    notification_id:str
    tenant_id:str
    event:str
    recipient_id:str
    payload_hash:str
    def validate(self):
        if not all(x.strip() for x in (self.notification_id,self.tenant_id,self.recipient_id,self.payload_hash)):
            raise ValueError("notification evidence is incomplete")
        if self.event not in VALID_EVENTS: raise ValueError("invalid notification event")
        if len(self.payload_hash)!=64: raise ValueError("invalid payload hash")
        return self

@dataclass(frozen=True)
class ProviderBoundary:
    provider_id:str
    environment:str
    configured:bool
    credentials_verified:bool
    def validate(self):
        if not self.provider_id.strip() or not self.environment.strip(): raise ValueError("provider identity is incomplete")
        if not isinstance(self.configured,bool) or not isinstance(self.credentials_verified,bool):
            raise ValueError("provider state is invalid")
        if self.configured and not self.credentials_verified:
            raise ValueError("configured provider without verified credentials")
        return self

@dataclass(frozen=True)
class RecoveryEvidence:
    snapshot_id:str
    tenant_id:str
    checksum:str
    restorable:bool
    tested:bool
    def validate(self):
        if not all(x.strip() for x in (self.snapshot_id,self.tenant_id,self.checksum)):
            raise ValueError("recovery evidence is incomplete")
        if len(self.checksum)!=64: raise ValueError("invalid recovery checksum")
        if not isinstance(self.restorable,bool) or not isinstance(self.tested,bool): raise ValueError("invalid recovery state")
        if self.restorable and not self.tested: raise ValueError("restorable snapshot without recovery test")
        return self

def authorize(identity:TenantIdentity, required_roles):
    e=identity.validate()
    roles=set(required_roles)
    if not roles or not roles.issubset(VALID_ROLES): raise ValueError("invalid required roles")
    if e.role not in roles: raise PermissionError("role is not authorized")
    return True

def canonical_fingerprint(*records):
    data=[]
    for record in records:
        if hasattr(record,"validate"): record.validate()
        data.append(record.__dict__ if hasattr(record,"__dict__") else record)
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
