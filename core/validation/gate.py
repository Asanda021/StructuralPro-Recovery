"""Release validation gates for representative construction projects."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import re
import time
from typing import Any, Callable

@dataclass(frozen=True)
class ValidationResult:
    case_id:str; passed:bool; evidence:str=""; detail:str=""

@dataclass(frozen=True)
class ExpertReview:
    reviewer_id:str; case_id:str; approved:bool; notes:str=""
    def __post_init__(self):
        if not self.reviewer_id.strip() or not self.case_id.strip(): raise ValueError("reviewer and case are required")

def validation_summary(results:list[ValidationResult])->dict[str,Any]:
    failed=[r.case_id for r in results if not r.passed]
    return {"total":len(results),"passed":len(results)-len(failed),"failed":len(failed),"ready":bool(results) and not failed,
            "failed_cases":failed,"evidence_count":sum(bool(r.evidence) for r in results)}

def fingerprint_file(path:Path)->str:
    return sha256(path.read_bytes()).hexdigest()

def validate_source_fixture(path:Path,expected_suffix:str)->ValidationResult:
    try:
        if path.suffix.lower()!=expected_suffix.lower(): return ValidationResult(path.name,False,"","unexpected extension")
        if not path.is_file() or path.stat().st_size==0: return ValidationResult(path.name,False,"","missing or empty fixture")
        return ValidationResult(path.name,True,fingerprint_file(path),"source fixture readable")
    except OSError as exc: return ValidationResult(path.name,False,"",f"{type(exc).__name__}: {exc}")

def validate_pdf(path:Path)->ValidationResult:
    result=validate_source_fixture(path,".pdf")
    if not result.passed: return result
    try:
        import fitz
        doc=fitz.open(path); ok=doc.page_count>0; detail=f"pages={doc.page_count}"; doc.close()
        return ValidationResult(path.name,ok,result.evidence,detail)
    except Exception as exc: return ValidationResult(path.name,False,result.evidence,f"{type(exc).__name__}: {exc}")

def validate_dxf(path:Path)->ValidationResult:
    result=validate_source_fixture(path,".dxf")
    if not result.passed: return result
    try:
        import ezdxf
        doc=ezdxf.readfile(path); count=len(doc.modelspace())
        return ValidationResult(path.name,count>0,result.evidence,f"entities={count}")
    except Exception as exc: return ValidationResult(path.name,False,result.evidence,f"{type(exc).__name__}: {exc}")

def validate_ifc(path:Path)->ValidationResult:
    result=validate_source_fixture(path,".ifc")
    if not result.passed: return result
    text=path.read_text(encoding="utf-8",errors="strict")
    ok=text.startswith("ISO-10303-21;") and "END-ISO-10303-21;" in text and "IFCPROJECT" in text.upper()
    return ValidationResult(path.name,ok,result.evidence,"IFC envelope/project marker checked")

def security_path_gate(root:Path,requested:Path)->ValidationResult:
    try:
        root=root.resolve(); target=requested.resolve(); target.relative_to(root)
        if ".." in requested.parts: return ValidationResult(str(requested),False,"","path traversal rejected")
        return ValidationResult(str(requested),True,"","path confined to validation root")
    except (OSError,ValueError): return ValidationResult(str(requested),False,"","path escapes validation root")

def security_payload_gate(payload:dict[str,Any])->ValidationResult:
    text=json.dumps(payload,ensure_ascii=False,sort_keys=True)
    patterns=[r"-----BEGIN [A-Z ]+PRIVATE KEY-----",r"(?i)bot[_-]?token",r"(?i)api[_-]?key",r"(?i)private[_-]?key"]
    found=next((p for p in patterns if re.search(p,text)),"")
    return ValidationResult("security-payload",not bool(found),"","secret-like material rejected" if found else "no embedded secret pattern")

def measure_performance(operation:Callable[[],Any],iterations:int=1000,max_seconds:float=5.0)->ValidationResult:
    if iterations<=0 or max_seconds<=0: raise ValueError("invalid performance budget")
    start=time.perf_counter()
    for _ in range(iterations): operation()
    elapsed=time.perf_counter()-start
    return ValidationResult("performance",elapsed<=max_seconds,f"{elapsed:.6f}s",f"{iterations} iterations")

def recovery_round_trip(payload:dict[str,Any],path:Path)->ValidationResult:
    try:
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True),encoding="utf-8")
        restored=json.loads(path.read_text(encoding="utf-8"))
        return ValidationResult("recovery",restored==payload,fingerprint_file(path),"JSON export/import round-trip")
    except Exception as exc: return ValidationResult("recovery",False,"",f"{type(exc).__name__}: {exc}")

def expert_gate(reviews:list[ExpertReview],required_case_ids:set[str])->ValidationResult:
    approved={r.case_id for r in reviews if r.approved}; reviewers={r.reviewer_id for r in reviews if r.approved}
    missing=sorted(required_case_ids-approved); ok=not missing and bool(reviewers)
    return ValidationResult("expert-validation",ok,",".join(sorted(reviewers)),"all required cases approved" if ok else f"missing approvals: {missing}")
