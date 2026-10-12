"""Privacy-safe, offline diagnostics and support-bundle contract."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, platform
from typing import Mapping, Sequence
SENSITIVE_KEYS=frozenset({"token","password","secret","api_key","apikey","authorization","access_token","private_key"})
@dataclass(frozen=True)
class DiagnosticEvent:
    code:str; severity:str="error"; message:str=""; component:str=""; details:Mapping[str,str]|None=None
    def sanitized(self)->dict:
        d={k:"<redacted>" if k.casefold() in SENSITIVE_KEYS else str(v) for k,v in (self.details or {}).items()}
        return {"code":self.code,"severity":self.severity,"message":self.message,"component":self.component,"details":d}
def collect_runtime_facts()->dict:
    return {"platform":platform.system(),"python":platform.python_version(),"architecture":platform.machine()}
def build_support_bundle(events:Sequence[DiagnosticEvent],app_version:str,runtime:Mapping[str,str]|None=None)->dict:
    payload={"schema_version":"v1","app_version":app_version,"runtime":dict(runtime or collect_runtime_facts()),"events":[e.sanitized() for e in events]}
    canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    payload["sha256"]=hashlib.sha256(canonical).hexdigest()
    return payload
def validate_support_bundle(bundle:Mapping)->list[str]:
    errors=[]
    if bundle.get("schema_version")!="v1": errors.append("unsupported schema_version")
    if not str(bundle.get("app_version","")).strip(): errors.append("app_version is required")
    if not isinstance(bundle.get("events"),list): errors.append("events must be a list")
    digest=bundle.get("sha256")
    if not isinstance(digest,str) or len(digest)!=64: errors.append("invalid sha256")
    return errors
