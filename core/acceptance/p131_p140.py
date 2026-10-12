"""P131-P140 production closure contracts.

These contracts harden the deterministic/offline repository boundary. They do not
claim external services, proprietary datasets, converters, or cloud IAM.
"""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping

def canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

# P131 — versioned schema compatibility.
SCHEMAS = {"structuralpro.exchange.v1", "structuralpro.api.v1", "structuralpro.archive.v1"}
def schema_compatible(schema: str, supported: set[str] | None = None) -> bool:
    return schema in (supported or SCHEMAS)

# P132 — deterministic canonical payload.
def canonical_fingerprint(value: Any) -> str:
    return sha256(canon(value)).hexdigest()

# P133 — structured validation diagnostics.
def diagnostic(code: str, message: str, path: str = "$", severity: str = "error") -> dict[str, str]:
    if not code or not message or not path:
        raise ValueError("diagnostic fields required")
    if severity not in {"error", "warning", "info"}:
        raise ValueError("invalid diagnostic severity")
    return {"code": code, "message": message, "path": path, "severity": severity}

# P134 — idempotent operation/replay protection.
def operation_fingerprint(operation: Mapping[str, Any]) -> str:
    required = {"operation_id", "action", "payload"}
    if not required.issubset(operation):
        raise ValueError("operation_id, action and payload required")
    return canonical_fingerprint({"action": operation["action"], "payload": operation["payload"]})

def accept_operation(seen: Mapping[str, str], operation: Mapping[str, Any]) -> str:
    op_id = str(operation.get("operation_id", ""))
    if not op_id:
        raise ValueError("operation_id required")
    fp = operation_fingerprint(operation)
    previous = seen.get(op_id)
    if previous is not None and previous != fp:
        raise ValueError("operation replay conflict")
    return fp

# P135 — audit-chain completeness.
AUDIT_FIELDS = {"actor", "action", "target", "timestamp", "details", "prev_hash"}
def audit_entry(**kwargs: Any) -> dict[str, Any]:
    if set(kwargs) != AUDIT_FIELDS:
        missing = sorted(AUDIT_FIELDS - set(kwargs))
        extra = sorted(set(kwargs) - AUDIT_FIELDS)
        raise ValueError(f"audit fields invalid missing={missing} extra={extra}")
    body = dict(kwargs)
    body["hash"] = sha256(canon(body)).hexdigest()
    return body

def verify_audit_chain(entries: list[Mapping[str, Any]]) -> bool:
    previous = ""
    for entry in entries:
        if set(entry) != AUDIT_FIELDS | {"hash"}:
            return False
        body = {k: entry[k] for k in AUDIT_FIELDS}
        if entry["prev_hash"] != previous:
            return False
        if entry["hash"] != sha256(canon(body)).hexdigest():
            return False
        previous = entry["hash"]
    return True

# P136 — backup/restore preflight.
def restore_preflight(archive: Mapping[str, Any], expected_project_id: str) -> dict[str, Any]:
    required = {"schema", "project_id", "project_sha256", "manifest_sha256"}
    if not required.issubset(archive):
        return {"ready": False, "errors": ["archive manifest incomplete"]}
    if archive["schema"] != "structuralpro.archive.v1":
        return {"ready": False, "errors": ["unsupported archive schema"]}
    if archive["project_id"] != expected_project_id:
        return {"ready": False, "errors": ["project identity mismatch"]}
    body = {k: archive[k] for k in ("schema", "project_id", "project_sha256")}
    if archive["manifest_sha256"] != sha256(canon(body)).hexdigest():
        return {"ready": False, "errors": ["archive manifest integrity failure"]}
    return {"ready": True, "errors": []}

# P137 — report/export evidence manifest.
FORMATS = {"csv", "xlsx", "docx", "pdf"}
def report_manifest(project_id: str, revision: str, source_fingerprint: str, fmt: str) -> dict[str, Any]:
    if not project_id or not revision or len(source_fingerprint) != 64:
        raise ValueError("report evidence fields invalid")
    if fmt not in FORMATS:
        raise ValueError("unsupported report format")
    body = {
        "schema": "structuralpro.report-evidence.v1",
        "project_id": project_id,
        "revision": revision,
        "source_fingerprint": source_fingerprint,
        "format": fmt,
    }
    return {**body, "manifest_sha256": sha256(canon(body)).hexdigest()}

# P138 — deterministic project-size/performance budget.
def performance_budget(row_count: int, max_rows: int = 10000, batch_size: int = 500) -> dict[str, Any]:
    errors = []
    if row_count < 0:
        errors.append("row count cannot be negative")
    if max_rows < 1 or batch_size < 1:
        errors.append("invalid budget")
    if row_count > max_rows:
        errors.append("project exceeds configured row budget")
    batches = (row_count + batch_size - 1) // batch_size if row_count else 0
    return {"within_budget": not errors, "errors": errors, "batches": batches}

# P139 — release evidence, without fabricating external provisioning.
def release_evidence(version: str, commit: str, checks: Mapping[str, str], external: Mapping[str, bool] | None = None) -> dict[str, Any]:
    if not version or not commit or len(commit) != 40:
        raise ValueError("release identity invalid")
    normalized = dict(checks)
    invalid = [k for k, v in normalized.items() if v not in {"success", "failure", "pending", "not-run"}]
    if invalid:
        raise ValueError("invalid check state")
    return {
        "schema": "structuralpro.release-evidence.v1",
        "version": version,
        "commit": commit,
        "checks": normalized,
        "external_provisioning": dict(external or {}),
        "externals_are_claims": False,
    }

# P140 — integrated closure gate.
def run_all() -> dict[str, Any]:
    source = {"project": "P131-140", "rows": [{"id": i} for i in range(3)]}
    fp = canonical_fingerprint(source)
    seen: dict[str, str] = {}
    op = {"operation_id": "O1", "action": "export", "payload": source}
    op_fp = accept_operation(seen, op)
    seen["O1"] = op_fp
    a1 = audit_entry(actor="user", action="create", target="P1", timestamp="2026-10-03T00:00:00Z", details={"x": 1}, prev_hash="")
    a2 = audit_entry(actor="user", action="update", target="P1", timestamp="2026-10-03T00:01:00Z", details={"x": 2}, prev_hash=a1["hash"])
    archive = {"schema":"structuralpro.archive.v1","project_id":"P1","project_sha256":"a"*64}
    archive["manifest_sha256"] = sha256(canon({k:archive[k] for k in ("schema","project_id","project_sha256")})).hexdigest()
    checks = {
        "P131": schema_compatible("structuralpro.exchange.v1"),
        "P132": fp == canonical_fingerprint(source),
        "P133": diagnostic("E001", "invalid", "$.project")["severity"] == "error",
        "P134": accept_operation(seen, op) == op_fp,
        "P135": verify_audit_chain([a1, a2]),
        "P136": restore_preflight(archive, "P1")["ready"],
        "P137": report_manifest("P1", "r1", fp, "pdf")["format"] == "pdf",
        "P138": performance_budget(10000)["within_budget"],
        "P139": release_evidence("1.0.0", "a"*40, {"tests":"success"})["schema"] == "structuralpro.release-evidence.v1",
    }
    return {"checks": checks, "all_green": all(checks.values())}
