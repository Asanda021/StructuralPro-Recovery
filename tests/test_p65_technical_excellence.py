from core.cloud.collaboration_v4 import Event, apply_event, three_way
from core.windows.product_v3 import WindowsRelease, WindowsWorkspace, release_manifest, manifest_fingerprint
from core.product.technical_excellence_v1 import Evidence, DOMAINS, technical_gate

def test_windows_contract_is_deterministic_and_strict():
    r = WindowsRelease("3.0.0", "StructuralPro-3.0.0-x64.exe", "StructuralPro.exe", "A"*64, "x64", "stable", "Windows 10")
    w = WindowsWorkspace(".spx", ".bak", 30, True, True)
    manifest = release_manifest(r, w)
    assert manifest["sha256"] == "a"*64
    assert len(manifest_fingerprint(manifest)) == 64

def test_collaboration_is_fail_closed():
    event = Event("p", 2, "u", "editor", "a"*64, {"qty": 10}, "update")
    assert apply_event(1, "a"*64, event)["accepted"]
    try:
        apply_event(1, "a"*64, Event("p", 2, "u", "viewer", "a"*64, {"qty": 10}, "update"))
        assert False
    except ValueError:
        assert True

def test_three_way_conflict_is_explicit():
    result = three_way({"qty": 10}, {"qty": 11}, {"qty": 12})
    assert result["conflicts"] == ["qty"]
    assert result["requires_review"]

def test_technical_gate_reaches_near_100_only_with_verified_complete_evidence():
    evidence = [Evidence(domain=d, passed=True, evidence_id=f"test:{d}") for d in DOMAINS]
    result = technical_gate(evidence)
    assert result["score"] == 100.0
    assert result["near_100"]

def test_missing_evidence_fails_closed():
    evidence = [Evidence(domain=d, passed=True, evidence_id=f"test:{d}") for d in DOMAINS[:-1]]
    result = technical_gate(evidence)
    assert not result["near_100"]
    assert "ux" in result["missing"]
