"""Project-wide quality control and integrity validation."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
import math

@dataclass(frozen=True)
class QCIssue:
    severity: str
    code: str
    message: str
    entity: str
    entity_id: str = ""
    field: str = ""

    def to_dict(self):
        return asdict(self)

_COLLECTIONS = ("floors","drawings","takeoffs","boq","estimates","reports","statements","finance","tasks","daily_reports","resources","materials","meetings")

def _id(row):
    return str(row.get("id") or row.get("project_id") or "").strip()

def _finite_number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False

def validate_project(project: dict) -> dict:
    issues: list[QCIssue] = []
    if not isinstance(project, dict):
        return {"valid": False, "ready": False, "issues": [QCIssue("error","invalid_project","Project must be a mapping","project").to_dict()]}
    if not str(project.get("id") or project.get("project_id") or "").strip():
        issues.append(QCIssue("error","missing_project_id","Project identifier is required","project","","id"))
    if not str(project.get("name") or "").strip():
        issues.append(QCIssue("error","missing_project_name","Project name is required","project","","name"))
    seen: dict[str,str] = {}
    for collection in _COLLECTIONS:
        rows = project.get(collection, [])
        if rows is None:
            continue
        if not isinstance(rows, list):
            issues.append(QCIssue("error","invalid_collection","Collection must be a list",collection,"",collection))
            continue
        for index,row in enumerate(rows):
            if not isinstance(row, dict):
                issues.append(QCIssue("error","invalid_entity","Entity must be a mapping",collection,str(index)))
                continue
            rid = _id(row)
            if rid:
                key = rid
                if key in seen:
                    issues.append(QCIssue("error","duplicate_id",f"Duplicate identifier: {rid}",collection,rid,"id"))
                else:
                    seen[key] = collection
            for field in ("quantity","current_quantity","contract_quantity","amount","price","unit_price","total"):
                if field in row and row[field] is not None and (not _finite_number(row[field]) or float(row[field]) < 0):
                    issues.append(QCIssue("error","invalid_number",f"Invalid non-negative number in {field}",collection,rid,field))
            for field in ("date","planned_start","planned_end","actual_start","actual_end"):
                if row.get(field):
                    try:
                        datetime.fromisoformat(str(row[field]).replace("Z","+00:00"))
                    except ValueError:
                        issues.append(QCIssue("error","invalid_date",f"Invalid date in {field}",collection,rid,field))
    # Common reference checks: only validate references that are explicitly present.
    known = {str(project.get("id") or project.get("project_id") or "")}
    for collection in _COLLECTIONS:
        for row in project.get(collection,[]) or []:
            if isinstance(row,dict) and row.get("project_id") and str(row["project_id"]) not in known:
                issues.append(QCIssue("error","broken_reference",f"Unknown project reference: {row['project_id']}",collection,_id(row),"project_id"))
    errors = [x for x in issues if x.severity == "error"]
    return {"valid": not errors, "ready": not errors, "issues": [x.to_dict() for x in issues], "counts": {
        "error": sum(x.severity=="error" for x in issues),
        "warning": sum(x.severity=="warning" for x in issues),
        "info": sum(x.severity=="info" for x in issues),
    }}

def missing_data(project: dict) -> list[dict]:
    missing=[]
    if not str(project.get("name") or "").strip(): missing.append({"code":"missing_project_name","field":"name"})
    for field in ("client","contractor","contract_number"):
        if field in project and not str(project.get(field) or "").strip():
            missing.append({"code":f"missing_{field}","field":field})
    return missing

class ProjectIntegrity:
    def validate(self, project): return validate_project(project)
    def missing(self, project): return missing_data(project)
