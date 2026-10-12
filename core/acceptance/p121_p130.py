"""P121-P130 production completion gates."""
from __future__ import annotations
from hashlib import sha256
import json,re
from dataclasses import dataclass
from typing import Any
def canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
# P121: role/access policy
ROLES={"owner":{"read","write","export","admin"},"editor":{"read","write","export"},"viewer":{"read"}}
def authorize(role,action): return action in ROLES.get(role,set())
# P122: project import/export envelope
def export_project(project):
    if not project.get("id"): raise ValueError("project id required")
    payload={"schema":"structuralpro.exchange.v1","project":project}
    return {**payload,"sha256":sha256(canon(payload)).hexdigest()}
def import_project(bundle):
    if bundle.get("schema")!="structuralpro.exchange.v1": raise ValueError("unsupported schema")
    expected=sha256(canon({"schema":bundle["schema"],"project":bundle["project"]})).hexdigest()
    if bundle.get("sha256")!=expected: raise ValueError("exchange integrity failure")
    return bundle["project"]
# P123: stable API contract
def api_response(ok,data=None,error=None,request_id=""):
    if not request_id: raise ValueError("request_id required")
    if ok and error is not None: raise ValueError("success cannot contain error")
    if not ok and not error: raise ValueError("failure requires error")
    return {"schema":"structuralpro.api.v1","ok":bool(ok),"request_id":request_id,"data":data,"error":error}
# P124: diagnostic redaction
_SECRET=re.compile(r"(?i)(token|password|secret|authorization|api[_-]?key)")
def redact(value):
    if isinstance(value,dict): return {k:("***REDACTED***" if _SECRET.search(str(k)) else redact(v)) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    return value
# P125: project lifecycle
LIFECYCLE={"draft":{"validated","archived"},"validated":{"active","archived"},"active":{"frozen","archived"},"frozen":{"archived"},"archived":set()}
def transition(state,target):
    if target not in LIFECYCLE.get(state,set()): raise ValueError(f"invalid transition {state}->{target}")
    return target
# P126: deterministic calculation fingerprint
def fingerprint(inputs):
    return sha256(canon(inputs)).hexdigest()
# P127: configuration validation
def validate_config(cfg):
    errors=[]
    if cfg.get("environment") not in {"dev","test","production"}: errors.append("invalid environment")
    if cfg.get("timeout_seconds",30)<=0 or cfg.get("timeout_seconds",30)>300: errors.append("invalid timeout")
    if cfg.get("max_project_rows",10000)<1: errors.append("invalid max_project_rows")
    return {"valid":not errors,"errors":errors}
# P128: security boundary
def security_check(request):
    errors=[]
    if request.get("scheme")!="https" and not request.get("local",False): errors.append("insecure transport")
    if ".." in str(request.get("path","")).replace(chr(92), "/").split("/"): errors.append("path traversal")
    if len(str(request.get("project_id","")))>128: errors.append("project id too long")
    return {"safe":not errors,"errors":errors}
# P129: archive/recovery manifest
def archive_manifest(project):
    payload={"schema":"structuralpro.archive.v1","project_id":project.get("id"),"project_sha256":sha256(canon(project)).hexdigest()}
    return {**payload,"manifest_sha256":sha256(canon(payload)).hexdigest()}
# P130: integrated production gate
def run_all():
    p={"id":"P121-130","name":"Production Acceptance","items":[{"id":"I1","qty":10}]}
    ex=export_project(p); imported=import_project(ex)
    checks={
      "P121":authorize("editor","write") and not authorize("viewer","write"),
      "P122":imported==p,
      "P123":api_response(True,{"ok":1},request_id="R1")["schema"]=="structuralpro.api.v1",
      "P124":redact({"token":"abc","nested":{"password":"x","name":"ok"}})["token"]=="***REDACTED***",
      "P125":transition("draft","validated")=="validated",
      "P126":fingerprint({"a":1})==fingerprint({"a":1}),
      "P127":validate_config({"environment":"production","timeout_seconds":30,"max_project_rows":10000})["valid"],
      "P128":security_check({"scheme":"https","path":"projects/P1","project_id":"P1"})["safe"],
      "P129":archive_manifest(p)["manifest_sha256"]==sha256(canon({"schema":"structuralpro.archive.v1","project_id":p["id"],"project_sha256":sha256(canon(p)).hexdigest()})).hexdigest(),
      "P130": all([ex["sha256"],imported["id"]=="P121-130"])
    }
    return {"checks":checks,"all_green":all(checks.values())}
