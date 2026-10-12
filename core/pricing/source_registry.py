"""Price-list source provenance and import validation."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib

@dataclass(frozen=True)
class PriceSource:
    year:int; discipline:str; title:str; publisher:str; source_id:str
    revision:str=""; checksum:str=""; verified:bool=False; license_status:str="unknown"; retrieved_at:str=""; sha256:str=""

class PriceSourceRegistry:
    def __init__(self): self._sources={}
    def register(self,source:PriceSource): self._sources[(source.year,source.discipline,source.source_id)]=source
    def add(self,source:PriceSource): self.register(source); return source
    def verify_record(self,source:PriceSource,checksum:str)->bool:
        return str(checksum)==str(source.checksum or source.sha256)
    def get(self,year,discipline,source_id):
        return self._sources.get((int(year),discipline,source_id))
    def all(self): return [asdict(x) for x in self._sources.values()]
    @staticmethod
    def fingerprint(text): return hashlib.sha256(text.encode("utf-8")).hexdigest()
    @staticmethod
    def now(): return datetime.now(timezone.utc).isoformat()
    def validate_import(self,source,text,required_fields=("year","group","chapter","code","description","unit","unit_price")):
        import csv
        from io import StringIO
        rows=list(csv.DictReader(StringIO(text)))
        errors=[]
        for i,r in enumerate(rows,2):
            for f in required_fields:
                if not str(r.get(f,"")).strip(): errors.append(f"row {i}: {f} required")
            try:
                if int(r.get("year"))!=int(source.year): errors.append(f"row {i}: year mismatch")
                if float(r.get("unit_price",0))<0: errors.append(f"row {i}: negative price")
            except Exception: errors.append(f"row {i}: invalid numeric field")
        return {"valid":not errors,"rows":len(rows),"errors":errors,"sha256":self.fingerprint(text)}
