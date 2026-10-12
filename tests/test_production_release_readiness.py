import json
from core.production_release_readiness import evaluate_evidence, write_manifest

def test_missing_required_evidence_is_fail_closed(tmp_path):
    result = evaluate_evidence(tmp_path, {})
    assert result.status == "blocked"
    assert result.ready is False

def test_real_nonempty_evidence_is_hashed(tmp_path):
    artifact = tmp_path / "installer.exe"
    artifact.write_bytes(b"real-artifact-evidence")
    result = evaluate_evidence(tmp_path, {"customer_artifact": "installer.exe"})
    item = next(x for x in result.evidence if x.key == "customer_artifact")
    assert item.present is True and len(item.sha256) == 64
    assert result.status == "blocked"

def test_all_required_evidence_unlocks_readiness(tmp_path):
    evidence = {}
    for key in ("customer_artifact","entitlement_authorization","installation_evidence","pricebook_provenance","third_party_licenses"):
        path = tmp_path / key
        path.write_text(key, encoding="utf-8")
        evidence[key] = key
    result = evaluate_evidence(tmp_path, evidence)
    assert result.status == "ready" and result.ready is True

def test_manifest_is_fail_closed(tmp_path):
    result = evaluate_evidence(tmp_path, {})
    output = tmp_path / "manifest.json"
    write_manifest(result, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["fail_closed"] is True and payload["release_ready"] is False
    assert payload["status"] == "blocked" and len(payload["evidence"]) == 8
