from core.acceptance.p121_p130 import (
    fingerprint, validate_config, security_check, archive_manifest,
)
from core.acceptance.p131_p140 import (
    schema_compatible, canonical_fingerprint, diagnostic, accept_operation,
    operation_fingerprint, audit_entry, verify_audit_chain,
)

def test_p126_deterministic_fingerprint():
    assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})

def test_p127_config_validation_fail_closed():
    assert validate_config({"environment": "production", "timeout_seconds": 30})["valid"]
    assert not validate_config({"environment": "unknown"})["valid"]

def test_p128_security_boundary():
    assert security_check({"scheme": "https", "path": "projects/P1", "project_id": "P1"})["safe"]
    assert not security_check({"scheme": "http", "path": "projects/P1", "project_id": "P1"})["safe"]
    assert not security_check({"scheme": "https", "path": "../P1", "project_id": "P1"})["safe"]

def test_p129_archive_manifest_is_verifiable():
    project = {"id": "P1", "rows": [1, 2, 3]}
    manifest = archive_manifest(project)
    assert len(manifest["manifest_sha256"]) == 64

def test_p130_previous_gate_is_green():
    from core.acceptance.p121_p130 import run_all
    result = run_all()
    assert result["all_green"] and all(result["checks"].values())

def test_p131_schema_compatibility():
    assert schema_compatible("structuralpro.exchange.v1")
    assert not schema_compatible("structuralpro.unknown.v9")

def test_p132_canonical_determinism():
    assert canonical_fingerprint({"z": 3, "a": 1}) == canonical_fingerprint({"a": 1, "z": 3})

def test_p133_structured_diagnostics():
    d = diagnostic("E001", "invalid", "$.project")
    assert d == {"code": "E001", "message": "invalid", "path": "$.project", "severity": "error"}

def test_p134_replay_conflict():
    seen = {}
    op = {"operation_id": "O1", "action": "write", "payload": {"x": 1}}
    fp = accept_operation(seen, op)
    seen["O1"] = fp
    assert accept_operation(seen, op) == fp
    try:
        accept_operation(seen, {"operation_id": "O1", "action": "write", "payload": {"x": 2}})
    except ValueError:
        pass
    else:
        raise AssertionError("conflicting replay was accepted")

def test_p135_audit_chain_integrity():
    first = audit_entry(actor="u", action="create", target="P1", timestamp="t1", details={}, prev_hash="")
    second = audit_entry(actor="u", action="update", target="P1", timestamp="t2", details={"x": 1}, prev_hash=first["hash"])
    assert verify_audit_chain([first, second])
    second["details"] = {"tampered": True}
    assert not verify_audit_chain([first, second])

def test_p126_p135_integrated_previous_gates():
    from core.acceptance.p121_p130 import run_all as p130
    from core.acceptance.p131_p140 import run_all as p140
    assert p130()["all_green"]
    assert p140()["all_green"]
