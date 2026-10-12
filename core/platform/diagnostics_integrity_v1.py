"""P301-P310 deterministic diagnostics/support-bundle integrity boundary."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import Mapping, Sequence

REQUIRED_EVENT_FIELDS=("code","severity","message","component")
ALLOWED_SEVERITIES=frozenset({"info","warning","error","critical"})

@dataclass(frozen=True)
class DiagnosticRecord:
    code:str
    severity:str="error"
    message:str=""
    component:str=""
    details:Mapping[str,str]|None=None

    def canonical(self)->dict:
        if not self.code.strip(): raise ValueError("event code is required")
        if self.severity not in ALLOWED_SEVERITIES: raise ValueError("invalid severity")
        details={str(k):str(v) for k,v in (self.details or {}).items()}
        return {"code":self.code,"severity":self.severity,"message":self.message,
                "component":self.component,"details":details}

def build_bundle(records:Sequence[DiagnosticRecord], app_version:str,
                 runtime:Mapping[str,str]) -> dict:
    if not app_version.strip(): raise ValueError("app_version is required")
    if not isinstance(runtime, Mapping): raise ValueError("runtime must be a mapping")
    events=[r.canonical() for r in records]
    payload={"schema_version":"v2","app_version":app_version,
             "runtime":dict(sorted((str(k),str(v)) for k,v in runtime.items())),
             "events":events}
    canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,
                          separators=(",",":")).encode()
    return {**payload,"sha256":hashlib.sha256(canonical).hexdigest()}

def validate_bundle(bundle:Mapping)->list[str]:
    errors=[]
    if bundle.get("schema_version")!="v2": errors.append("unsupported schema_version")
    if not str(bundle.get("app_version","")).strip(): errors.append("app_version is required")
    if not isinstance(bundle.get("runtime"),dict): errors.append("runtime must be a dict")
    events=bundle.get("events")
    if not isinstance(events,list): errors.append("events must be a list")
    else:
        for i,event in enumerate(events):
            if not isinstance(event,dict): errors.append(f"event[{i}] must be a dict"); continue
            for field in REQUIRED_EVENT_FIELDS:
                if not str(event.get(field,"")).strip(): errors.append(f"event[{i}] missing {field}")
            if event.get("severity") not in ALLOWED_SEVERITIES: errors.append(f"event[{i}] invalid severity")
    digest=bundle.get("sha256")
    if not isinstance(digest,str) or len(digest)!=64: errors.append("invalid sha256")
    return errors

def bundle_fingerprint(bundle:Mapping)->str:
    clean={k:v for k,v in bundle.items() if k!="sha256"}
    canonical=json.dumps(clean,ensure_ascii=False,sort_keys=True,
                          separators=(",",":")).encode()
    return hashlib.sha256(canonical).hexdigest()

def verify_bundle(bundle:Mapping)->bool:
    if validate_bundle(bundle): return False
    return bundle.get("sha256")==bundle_fingerprint(bundle)
