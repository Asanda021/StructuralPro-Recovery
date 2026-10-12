"""Deterministic offline backup/restore integrity boundary for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json

VALID_RESULTS={"accepted","rejected"}

@dataclass(frozen=True)
class BackupEvidence:
    backup_id:str
    project_id:str
    source_revision:str
    created_at:str
    payload_fingerprint:str
    result:str="accepted"
    def __post_init__(self):
        if not self.backup_id.strip() or not self.project_id.strip() or not self.source_revision.strip():
            raise ValueError("backup identity is required")
        try: datetime.fromisoformat(self.created_at)
        except ValueError as exc: raise ValueError("created_at must be ISO-8601") from exc
        if len(self.payload_fingerprint)!=64 or any(c not in "0123456789abcdef" for c in self.payload_fingerprint.lower()):
            raise ValueError("payload_fingerprint must be SHA-256 hex")
        if self.result not in VALID_RESULTS: raise ValueError("invalid backup result")

@dataclass(frozen=True)
class RestoreEvidence:
    backup_id:str
    operator:str
    validated_at:str
    resulting_revision:str
    result:str="accepted"
    def __post_init__(self):
        if not self.backup_id.strip() or not self.operator.strip() or not self.resulting_revision.strip():
            raise ValueError("restore identity is required")
        try: datetime.fromisoformat(self.validated_at)
        except ValueError as exc: raise ValueError("validated_at must be ISO-8601") from exc
        if self.result not in VALID_RESULTS: raise ValueError("invalid restore result")

@dataclass(frozen=True)
class ProjectIntegrityEvidence:
    project_id:str
    quantity_fingerprint:str
    totals_fingerprint:str
    revision:str
    passed:bool
    def __post_init__(self):
        if not self.project_id.strip() or not self.revision.strip(): raise ValueError("project identity is required")
        for value in (self.quantity_fingerprint,self.totals_fingerprint):
            if len(value)!=64 or any(c not in "0123456789abcdef" for c in value.lower()):
                raise ValueError("integrity fingerprints must be SHA-256 hex")

def restore_allowed(backup:BackupEvidence, restore:RestoreEvidence, integrity:ProjectIntegrityEvidence, project_id:str)->bool:
    if project_id.strip()!=backup.project_id: return False
    if restore.backup_id!=backup.backup_id: return False
    if backup.result!="accepted" or restore.result!="accepted": return False
    if integrity.project_id!=project_id or not integrity.passed: return False
    if integrity.revision!=restore.resulting_revision: return False
    return True

def canonical_fingerprint(payload:dict)->str:
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
    return sha256(raw).hexdigest()
