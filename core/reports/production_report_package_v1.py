"""Fail-closed professional report package contract."""
from __future__ import annotations
from typing import Any
from core.reports.bundle import build_bundle_manifest

ALLOWED_FORMATS = ("pdf", "xlsx", "csv", "json")

def build_report_package(*, project_id: str, revision: str, report_data: dict[str, Any],
                         export_files: tuple[str, ...], rtl: bool = True) -> dict:
    if not str(project_id).strip() or not str(revision).strip():
        raise ValueError("project_id and revision are required")
    if not isinstance(report_data, dict) or not report_data:
        raise ValueError("report_data is required")
    if not export_files:
        raise ValueError("at least one export file is required")
    formats=[]
    for name in export_files:
        suffix=str(name).rsplit(".", 1)[-1].lower() if "." in str(name) else ""
        if suffix not in ALLOWED_FORMATS:
            raise ValueError(f"unsupported export format: {suffix or name}")
        formats.append(suffix)
    return {"schema":"structuralpro-production-report-package-1",
            "project_id":str(project_id),"revision":str(revision),
            "rtl":bool(rtl),"formats":tuple(sorted(set(formats))),
            "export_files":tuple(sorted(str(x) for x in export_files)),
            "report_data":report_data}

def validate_report_package(package: dict) -> dict:
    required=("schema","project_id","revision","rtl","formats","export_files","report_data")
    missing=[k for k in required if k not in package]
    if missing: raise ValueError(f"missing report package fields: {','.join(missing)}")
    if package["schema"] != "structuralpro-production-report-package-1":
        raise ValueError("unsupported report package schema")
    if not package["rtl"]:
        raise ValueError("production Persian report package must be RTL")
    if not package["formats"] or not set(package["formats"]).issubset(ALLOWED_FORMATS):
        raise ValueError("invalid export formats")
    return {"valid": True, "project_id": package["project_id"], "revision": package["revision"]}
