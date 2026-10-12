"""Deterministic golden-case validation for project quantities and BOQ outputs.

The validator compares authoritative produced snapshots with checked-in expected
snapshots. It never mutates project data and reports missing, unexpected and
numeric mismatches explicitly.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, math
from typing import Any, Iterable, Mapping

@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    dataset_version: str
    project: Mapping[str, Any]
    expected_quantities: tuple[Mapping[str, Any], ...] = ()
    expected_boq: tuple[Mapping[str, Any], ...] = ()
    tolerances: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.dataset_version.strip():
            raise ValueError("case_id and dataset_version are required")
        values = dict(self.tolerances or {})
        for name, value in values.items():
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"invalid tolerance: {name}")
        object.__setattr__(self, "tolerances", values)

    def digest(self) -> str:
        payload = {
            "case_id": self.case_id, "dataset_version": self.dataset_version,
            "project": self.project,
            "expected_quantities": self.expected_quantities,
            "expected_boq": self.expected_boq, "tolerances": self.tolerances or {},
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

@dataclass(frozen=True)
class ValidationIssue:
    category: str
    key: str
    field: str
    expected: Any
    actual: Any
    delta: float | None = None
    message: str = ""

@dataclass(frozen=True)
class ValidationResult:
    case_id: str
    dataset_version: str
    passed: bool
    issues: tuple[ValidationIssue, ...]
    expected_digest: str
    @property
    def issue_count(self) -> int:
        return len(self.issues)

def _key(row: Mapping[str, Any]) -> str:
    for field in ("object_id", "item_code", "global_id", "element_id", "code", "id"):
        value = str(row.get(field) or "").strip()
        if value: return value
    return "|".join(str(row.get(k) or "").strip() for k in ("discipline","member_type","description","unit")).strip("|")

def _num(value: Any) -> float | None:
    if value is None or value == "": return None
    try: number = float(value)
    except (TypeError, ValueError): return None
    return number if math.isfinite(number) else None

def _rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result = {}
    for row in rows:
        key = _key(row)
        if not key: raise ValueError("every validation row needs a stable identity")
        if key in result: raise ValueError(f"duplicate row identity: {key}")
        result[key] = row
    return result

def _equal(expected: Any, actual: Any, tolerance: float) -> tuple[bool, float | None]:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is bool and type(actual) is bool and expected == actual, None
    for value in (expected, actual):
        try: numeric = float(value)
        except (TypeError, ValueError, OverflowError): continue
        if not math.isfinite(numeric): return False, None
    a,b = _num(expected),_num(actual)
    if a is not None or b is not None:
        if a is None or b is None: return False,None
        delta=b-a; return abs(delta)<=tolerance,delta
    return expected==actual,None

def _compare(category: str, expected: Iterable[Mapping[str, Any]], actual: Iterable[Mapping[str, Any]], tolerances: Mapping[str,float]) -> list[ValidationIssue]:
    old,new=_rows(expected),_rows(actual); issues=[]
    for key in sorted(set(old)|set(new)):
        if key not in old:
            issues.append(ValidationIssue(category,key,"__row__",None,dict(new[key]),message="unexpected row")); continue
        if key not in new:
            issues.append(ValidationIssue(category,key,"__row__",dict(old[key]),None,message="missing row")); continue
        for field in sorted(set(old[key])|set(new[key])):
            e,a=old[key].get(field),new[key].get(field)
            ok,delta=_equal(e,a,float(tolerances.get(field,tolerances.get("default",0.0))))
            if not ok:
                issues.append(ValidationIssue(category,key,field,e,a,delta,"value mismatch"))
    return issues

def validate_case(case: GoldenCase, actual_quantities: Iterable[Mapping[str, Any]], actual_boq: Iterable[Mapping[str, Any]]) -> ValidationResult:
    issues=_compare("quantities",case.expected_quantities,actual_quantities,case.tolerances or {})
    issues.extend(_compare("boq",case.expected_boq,actual_boq,case.tolerances or {}))
    return ValidationResult(case.case_id,case.dataset_version,not issues,tuple(issues),case.digest())
