"""Offline-first sync contract: deterministic operations, no silent conflict resolution."""
from dataclasses import dataclass

@dataclass(frozen=True)
class SyncOperation:
    entity:str; entity_id:str; revision:int; payload:dict; operation:str="upsert"

def make_operation(entity,entity_id,revision,payload,operation="upsert"):
    if revision < 1: raise ValueError("revision must be positive")
    if operation not in {"upsert","delete"}: raise ValueError("unsupported operation")
    return SyncOperation(entity,str(entity_id),revision,dict(payload),operation)

def merge(local,remote):
    if local is None:return remote,"remote"
    if remote is None:return local,"local"
    if local.revision==remote.revision and local.payload!=remote.payload:
        return None,"conflict"
    return (local,"local") if local.revision>remote.revision else (remote,"remote")
