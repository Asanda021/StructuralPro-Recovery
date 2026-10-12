"""Offline-first synchronization primitives."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import json

@dataclass(frozen=True)
class SyncRecord:
    record_id:str; entity_type:str; entity_id:str; operation:str; payload:dict[str,Any]
    base_version:int; version:int; device_id:str; timestamp:str
    def __post_init__(self):
        if not self.record_id.strip() or not self.entity_type.strip() or not self.entity_id.strip(): raise ValueError("sync identity is required")
        if self.operation not in {"upsert","delete"}: raise ValueError("unsupported sync operation")
        if self.base_version<0 or self.version<=self.base_version: raise ValueError("invalid version transition")
        if not self.device_id.strip() or not isinstance(self.payload,dict): raise ValueError("invalid sync record")
        parsed=datetime.fromisoformat(self.timestamp.replace("Z","+00:00"))
        if parsed.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        object.__setattr__(self,"timestamp",parsed.astimezone(timezone.utc).isoformat())
    def key(self): return (self.entity_type,self.entity_id)
    def to_dict(self): return self.__dict__.copy()
    @classmethod
    def from_dict(cls,v): return cls(**v)
    def canonical_json(self): return json.dumps(self.to_dict(),ensure_ascii=False,sort_keys=True,separators=(",",":"))

@dataclass(frozen=True)
class Conflict:
    key:tuple[str,str]; local:SyncRecord; remote:SyncRecord
class ConflictResolution(str,Enum):
    LOCAL="local"; REMOTE="remote"; MERGE="merge"
@dataclass(frozen=True)
class _State:
    payload:dict[str,Any]; version:int; deleted:bool=False

class SyncEngine:
    def __init__(self,device_id:str):
        if not device_id.strip(): raise ValueError("device_id is required")
        self.device_id=device_id; self._state={}; self._outbox=[]
    def state(self,key):
        item=self._state.get(key)
        return None if item is None or item.deleted else dict(item.payload)
    def version(self,key): return self._state.get(key,_State({},0)).version
    def outbox(self): return tuple(self._outbox)
    def apply_local(self,entity_type,entity_id,payload,operation="upsert",timestamp="1970-01-01T00:00:00+00:00"):
        key=(entity_type,entity_id); current=self._state.get(key,_State({},0)); v=current.version+1
        r=SyncRecord(f"{self.device_id}:{entity_type}:{entity_id}:{v}",entity_type,entity_id,operation,dict(payload),current.version,v,self.device_id,timestamp)
        self._apply(r); self._outbox.append(r); return r
    def receive(self,remote):
        key=remote.key(); current=self._state.get(key,_State({},0))
        if remote.version<=current.version:
            return Conflict(key,self._record(key,current),remote) if remote.version==current.version and remote.device_id!=self.device_id else None
        if remote.base_version!=current.version: return Conflict(key,self._record(key,current),remote)
        self._apply(remote); return None
    def resolve(self,conflict,resolution):
        if resolution==ConflictResolution.LOCAL: return conflict.local
        if resolution==ConflictResolution.REMOTE: self._apply(conflict.remote); return conflict.remote
        merged=dict(conflict.local.payload)
        for k,v in conflict.remote.payload.items():
            if k in merged and merged[k]!=v: raise ValueError(f"non-disjoint conflict field: {k}")
            merged[k]=v
        key=conflict.key; v=max(conflict.local.version,conflict.remote.version)+1
        r=SyncRecord(f"{self.device_id}:{key[0]}:{key[1]}:{v}",key[0],key[1],"upsert",merged,self.version(key),v,self.device_id,conflict.remote.timestamp)
        self._apply(r); self._outbox.append(r); return r
    def acknowledge(self,record_id): self._outbox=[r for r in self._outbox if r.record_id!=record_id]
    def _apply(self,r): self._state[r.key()]=_State(dict(r.payload),r.version,r.operation=="delete")
    def _record(self,key,state): return SyncRecord(f"state:{key[0]}:{key[1]}:{state.version}",key[0],key[1],"delete" if state.deleted else "upsert",dict(state.payload),max(0,state.version-1),state.version,"local-state","1970-01-01T00:00:00+00:00")
