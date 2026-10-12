import json
from pathlib import Path

from core.release_readiness import evaluate


def test_fail_closed_when_required_evidence_is_missing():
    result = evaluate({})
    assert result.status == "blocked"
    assert result.required_satisfied is False


def test_ready_requires_every_required_item():
    evidence = {
        "customer_artifact": True,
        "entitlement_authorization": True,
        "installation_evidence": True,
        "pricebook_provenance": True,
        "third_party_licenses": True,
    }
    result = evaluate(evidence)
    assert result.status == "ready"
    assert result.required_satisfied is True


def test_optional_items_never_unlock_release():
    evidence = {
        "customer_artifact": True,
        "entitlement_authorization": True,
        "installation_evidence": True,
        "pricebook_provenance": True,
        "third_party_licenses": True,
        "code_signing": False,
        "bundled_gguf": False,
        "dwg_runtime_terms": False,
    }
    assert evaluate(evidence).status == "ready"


def test_contract_matches_fail_closed_policy():
    contract = json.loads(
        Path("contracts/ervira/release_readiness.json").read_text(encoding="utf-8")
    )
    assert contract["policy"]["fail_closed"] is True
    assert set(contract["required_items"]) == {
        "customer_artifact",
        "entitlement_authorization",
        "installation_evidence",
        "pricebook_provenance",
        "third_party_licenses",
    }
