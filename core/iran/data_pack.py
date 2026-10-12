"""Versioned Iranian engineering/pricing data-pack provenance boundary."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json
from typing import Iterable

@dataclass(frozen=True)
class DataPackEntry:
    code:str
    title:str
    source_id:str
    edition:str
    checksum:str=""
    license_ref:str=""

class IranDataPack:
    def __init__(self, entries:Iterable[DataPackEntry]=(), pack_version="1"):
        self.pack_version=str(pack_version); self.entries=tuple(entries); self.validate()
    def validate(self):
        seen=set()
        for e in self.entries:
            if not e.code.strip() or not e.title.strip() or not e.source_id.strip() or not e.edition.strip(): raise ValueError("data-pack provenance is incomplete")
            if e.code in seen: raise ValueError(f"duplicate data-pack code: {e.code}")
            seen.add(e.code)
        return self
    def manifest(self):
        rows=[asdict(e) for e in sorted(self.entries,key=lambda x:x.code)]
        payload={"pack_version":self.pack_version,"entries":rows}
        digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return {**payload,"digest":digest}
    @staticmethod
    def verify(manifest):
        payload={"pack_version":manifest.get("pack_version"),"entries":manifest.get("entries",[])}
        digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return digest==manifest.get("digest")
