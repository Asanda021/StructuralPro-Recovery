"""Production acceptance for P116-P120: portability, audit, backup, search and integrity."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json, tempfile, zipfile
from pathlib import Path
from typing import Any, Iterable
SCHEMA="structuralpro.project.bundle.v1"
def canonical_json(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def project_bundle(project):
    if not isinstance(project,dict) or not str(project.get("id","")).strip(): raise ValueError("project id is required")
    payload={"schema":SCHEMA,"project":project}
    return {**payload,"sha256":sha256(canonical_json(payload)).hexdigest()}
def verify_project_bundle(bundle):
    if not isinstance(bundle,dict) or bundle.get("schema")!=SCHEMA or "project" not in bundle: return False
    return bundle.get("sha256")==sha256(canonical_json({"schema":SCHEMA,"project":bundle["project"]})).hexdigest()
@dataclass(frozen=True)
class AuditEvent:
    event_id:str; actor:str; action:str; target:str; timestamp:str; details:dict; prev_hash:str=""
    def payload(self): return {"event_id":self.event_id,"actor":self.actor,"action":self.action,"target":self.target,"timestamp":self.timestamp,"details":self.details,"prev_hash":self.prev_hash}
    def digest(self): return sha256(canonical_json(self.payload())).hexdigest()
def append_audit(events,actor,action,target,details=None):
    event=AuditEvent(f"E{len(events)+1:06d}",actor,action,target,datetime.now(timezone.utc).isoformat(),details or {},events[-1].digest() if events else "")
    events.append(event); return event
def verify_audit_chain(events):
    prev=""
    for i,e in enumerate(events,1):
        if e.event_id!=f"E{i:06d}" or e.prev_hash!=prev: return False
        prev=e.digest()
    return True
def write_backup(path,project,events=()):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); bundle=project_bundle(project)
    audit=[e.payload()|{"hash":e.digest()} for e in events]
    manifest={"schema":"structuralpro.backup.v1","project_sha256":bundle["sha256"],"audit_count":len(audit)}
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json",canonical_json(bundle)); z.writestr("audit.json",canonical_json(audit)); z.writestr("manifest.json",canonical_json(manifest))
    return path
def restore_backup(path):
    with zipfile.ZipFile(path) as z:
        bundle=json.loads(z.read("project.json")); audit=json.loads(z.read("audit.json")); manifest=json.loads(z.read("manifest.json"))
    if not verify_project_bundle(bundle): raise ValueError("project integrity check failed")
    if manifest.get("project_sha256")!=bundle["sha256"]: raise ValueError("manifest mismatch")
    return {"project":bundle["project"],"project_sha256":bundle["sha256"],"audit":audit,"manifest":manifest}
def search_project(project,query,fields=("id","name","description")):
    q=str(query).strip().casefold()
    if not q:return []
    out=[]
    for collection in ("takeoffs","boq","drawings","model_objects","project_materials","project_resources"):
        for row in project.get(collection,[]) or []:
            if isinstance(row,dict) and any(q in str(row.get(f,"")).casefold() for f in fields): out.append({"collection":collection,"item":row})
    return out
def validate_project_integrity(project):
    errors=[]; seen=set()
    if not str(project.get("id","")).strip(): errors.append("missing project id")
    for collection in ("takeoffs","boq","drawings","model_objects"):
        for row in project.get(collection,[]) or []:
            oid=str(row.get("id") or row.get("object_id") or "")
            if oid and (collection,oid) in seen: errors.append(f"duplicate id {collection}:{oid}")
            if oid: seen.add((collection,oid))
    return {"valid":not errors,"errors":errors,"sha256":sha256(canonical_json(project)).hexdigest()}
def run_all():
    project={"id":"P116-120","name":"Acceptance","description":"production fixture","takeoffs":[{"id":"T1","description":"بتن فونداسیون","quantity":10}],"boq":[{"id":"B1","description":"میلگرد","quantity":500}],"drawings":[{"id":"D1","name":"Foundation Plan"}]}
    events=[]; append_audit(events,"qa","create","P116-120",{"source":"acceptance"}); append_audit(events,"qa","update","T1",{"quantity":[10,12]})
    with tempfile.TemporaryDirectory() as td:
        bundle=project_bundle(project); backup=write_backup(Path(td)/"project.spbackup",project,events); restored=restore_backup(backup)
        tampered={**bundle,"project":{**project,"name":"tampered"}}
        return {"P116":{"verified":verify_project_bundle(bundle),"tamper_rejected":not verify_project_bundle(tampered)},"P117":{"chain_valid":verify_audit_chain(events),"count":len(events)},"P118":{"restored":restored["project"]==project,"manifest_ok":restored["project_sha256"]==bundle["sha256"]},"P119":{"hits":len(search_project(project,"بتن")),"deterministic":search_project(project,"بتن")==search_project(project,"بتن")},"P120":{"valid":validate_project_integrity(project)["valid"],"errors":validate_project_integrity(project)["errors"]}}
