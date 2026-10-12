"""Explicit, deterministic project schema migration registry."""
from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
from typing import Callable, Mapping
Migration=Callable[[dict],dict]
@dataclass(frozen=True)
class MigrationStep:
    source:int; target:int; migrate:Migration
class MigrationRegistry:
    def __init__(self,steps=()): self._steps={(s.source,s.target):s for s in steps}
    def path(self,current:int,target:int)->list[MigrationStep]:
        if current>target: raise ValueError("downgrade migrations are not supported")
        out=[]; v=current
        while v<target:
            candidates=[s for (a,b),s in self._steps.items() if a==v and b==v+1]
            if len(candidates)!=1: raise ValueError(f"missing migration {v}->{v+1}")
            out.append(candidates[0]); v+=1
        return out
    def migrate(self,data:Mapping,current:int,target:int)->dict:
        if not isinstance(data,Mapping): raise TypeError("data must be a mapping")
        result=deepcopy(dict(data))
        for step in self.path(current,target):
            result=step.migrate(result)
            if not isinstance(result,dict): raise ValueError("migration must return a dict")
        return result
def migrate_project(data:Mapping,current:int,target:int,registry:MigrationRegistry)->dict:
    return registry.migrate(data,current,target)
