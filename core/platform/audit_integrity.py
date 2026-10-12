"""Tamper-evident audit event hash chain."""
from __future__ import annotations
import hashlib,json
from typing import Mapping,Any,Iterable
GENESIS="0"*64
def event_digest(event:Mapping[str,Any],previous_hash:str=GENESIS)->str:
    payload={"previous_hash":previous_hash,"event":dict(event)}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()
def seal_events(events:Iterable[Mapping[str,Any]])->list[dict[str,Any]]:
    previous=GENESIS; sealed=[]
    for event in events:
        item=dict(event); item["previous_hash"]=previous; item["hash"]=event_digest(event,previous)
        sealed.append(item); previous=item["hash"]
    return sealed
def verify_chain(events:Iterable[Mapping[str,Any]])->bool:
    previous=GENESIS
    for item in events:
        if item.get("previous_hash")!=previous:return False
        base={k:v for k,v in item.items() if k not in {"previous_hash","hash"}}
        if item.get("hash")!=event_digest(base,previous):return False
        previous=item["hash"]
    return True
