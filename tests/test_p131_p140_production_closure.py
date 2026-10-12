from core.acceptance.p121_p130 import security_check
from core.acceptance.p131_p140 import *

def test_p131_p140_all_green():
    result = run_all()
    assert result["all_green"] and all(result["checks"].values())

def test_p131_rejects_unknown_schema():
    assert not schema_compatible("structuralpro.unknown.v9")

def test_p132_is_order_independent():
    assert canonical_fingerprint({"b":2,"a":1}) == canonical_fingerprint({"a":1,"b":2})

def test_p133_rejects_bad_severity():
    try:
        diagnostic("E", "x", severity="bad")
        assert False
    except ValueError:
        pass

def test_p134_detects_replay_conflict():
    seen = {}
    accept_operation(seen, {"operation_id":"O1","action":"write","payload":{"x":1}})
    seen["O1"] = operation_fingerprint({"operation_id":"O1","action":"write","payload":{"x":1}})
    try:
        accept_operation(seen, {"operation_id":"O1","action":"write","payload":{"x":2}})
        assert False
    except ValueError:
        pass

def test_p135_detects_tampered_audit():
    e = audit_entry(actor="u", action="a", target="t", timestamp="t", details={}, prev_hash="")
    e["details"] = {"tampered": True}
    assert not verify_audit_chain([e])

def test_p136_fail_closed_identity():
    a = {"schema":"structuralpro.archive.v1","project_id":"P1","project_sha256":"a"*64}
    a["manifest_sha256"] = sha256(canon(a)).hexdigest()
    assert not restore_preflight(a, "P2")["ready"]

def test_p137_supports_declared_formats_only():
    assert report_manifest("P1","r1","a"*64,"xlsx")["format"] == "xlsx"

def test_p138_enforces_row_budget():
    assert performance_budget(10001)["within_budget"] is False

def test_p139_does_not_claim_external_provisioning():
    e = release_evidence("1.0.0","a"*40,{"tests":"success"},{"price_list":True})
    assert e["externals_are_claims"] is False

def test_p140_integrates_previous_gate():
    from core.acceptance.p121_p130 import run_all as previous
    assert previous()["all_green"] is True
