from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
@dataclass(frozen=True)
class ImportRequest:
    filename:str; content_type:str; year:int; discipline:str; source:str; sha256:str
@dataclass(frozen=True)
class ImportResult:
    filename:str; year:int; discipline:str; row_count:int; fingerprint:str; status:str
ALLOWED_TYPES={"xlsx","xls","csv","json","pdf"}
def validate_request(r):
    if not all((r.filename,r.content_type,r.source,r.sha256)): raise ValueError("incomplete import request")
    if r.content_type.lower() not in ALLOWED_TYPES: raise ValueError("unsupported pricebook format")
    if not 1300 <= r.year <= 1500: raise ValueError("invalid pricebook year")
    if not r.discipline.strip(): raise ValueError("discipline required")
    if len(r.sha256)!=64 or any(c not in "0123456789abcdefABCDEF" for c in r.sha256): raise ValueError("invalid file sha256")
def file_fingerprint(path): return sha256(Path(path).read_bytes()).hexdigest()
def finalize_import(request,row_count,file_sha256):
    validate_request(request)
    if row_count<=0: raise ValueError("import produced no rows")
    if file_sha256.lower()!=request.sha256.lower(): raise ValueError("file hash mismatch")
    payload=f"{request.filename}|{request.content_type}|{request.year}|{request.discipline}|{request.source}|{request.sha256.lower()}|{row_count}"
    return ImportResult(request.filename,request.year,request.discipline,row_count,sha256(payload.encode()).hexdigest(),"needs_review")
def export_manifest(result): return json.dumps(result.__dict__,ensure_ascii=False,sort_keys=True)
