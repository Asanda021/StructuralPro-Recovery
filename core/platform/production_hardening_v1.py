"""P661-P670 production hardening contracts: performance, security and reliability."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import time
from typing import Any, Mapping

@dataclass(frozen=True)
class PerformanceBudget:
    max_seconds: float
    max_items: int
    def validate(self):
        if self.max_seconds <= 0 or self.max_items <= 0:
            raise ValueError("performance budgets must be positive")
        return self

@dataclass(frozen=True)
class SecurityPolicy:
    allow_network: bool = False
    require_source: bool = True
    max_payload_bytes: int = 1_000_000
    def validate(self):
        if self.max_payload_bytes <= 0:
            raise ValueError("max_payload_bytes must be positive")
        return self

@dataclass(frozen=True)
class HealthSnapshot:
    ok: bool
    elapsed_seconds: float
    item_count: int
    errors: tuple[str, ...]
    fingerprint: str

class ProductionGuard:
    def __init__(self, performance: PerformanceBudget, security: SecurityPolicy):
        self.performance=performance.validate()
        self.security=security.validate()

    def validate_payload(self, payload: Mapping[str,Any]) -> None:
        if self.security.require_source and not str(payload.get("source_id","")).strip():
            raise PermissionError("source identity is required")
        raw=json.dumps(dict(payload),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        if len(raw)>self.security.max_payload_bytes:
            raise ValueError("payload exceeds production limit")
        if not self.security.allow_network and bool(payload.get("network_required",False)):
            raise PermissionError("network access is disabled by policy")

    def run(self, items: list[Any], worker) -> HealthSnapshot:
        if len(items)>self.performance.max_items:
            raise ValueError("item count exceeds performance budget")
        start=time.perf_counter(); errors=[]
        for item in items:
            try: worker(item)
            except Exception as exc: errors.append(type(exc).__name__+":"+str(exc))
        elapsed=time.perf_counter()-start
        ok=not errors and elapsed<=self.performance.max_seconds
        raw=json.dumps({"ok":ok,"elapsed":round(elapsed,9),"count":len(items),
                        "errors":errors},sort_keys=True,separators=(",",":")).encode()
        return HealthSnapshot(ok,elapsed,len(items),tuple(errors),sha256(raw).hexdigest())

def recover_state(snapshot: Mapping[str,Any], required_keys: tuple[str,...]) -> dict[str,Any]:
    if not isinstance(snapshot,Mapping):
        raise ValueError("recovery snapshot must be a mapping")
    missing=[k for k in required_keys if k not in snapshot]
    if missing:
        raise ValueError("recovery snapshot is incomplete: "+",".join(missing))
    return {k:snapshot[k] for k in required_keys}
