import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = [f"p{i}" for i in range(41, 51)]


def load(i):
    return json.loads((ROOT / "contracts/ervira" / f"{i}.json").read_text(encoding="utf-8"))


def test_license_governance_contracts():
    for i in IDS:
        d = load(i)
        assert d["schema_version"] == "1.0"
        assert d["product_id"] == "structuralpro"
        assert d["parent_platform"] == "ERVIRA"
        assert d["source_contract"] == "contracts/product-contract.json"
        assert d["version"] == "0.1.0"
        assert d["runtime_status"] == "implemented"
        assert d["release_ready"] is False


def test_license_authority_is_ervira():
    keys = [
        "license_service",
        "issuance",
        "activation",
        "deactivation",
        "renewal",
        "expiration",
        "revocation",
        "edition_entitlement",
        "feature_entitlement",
        "e2e_verification",
    ]
    for i, key in zip(IDS, keys):
        contract = load(i)[key]
        assert contract["provider"] == "ERVIRA"
        assert contract["authority"] == "ERVIRA" if key != "license_service" else contract["identity_authority"] == "ERVIRA"


def test_entitlement_model_is_closed_until_runtime_exists():
    p48 = load("p48")["edition_entitlement"]
    p49 = load("p49")["feature_entitlement"]
    assert p48["runtime_implemented"] is True
    assert p48["editions"] == ["light", "standard", "pro", "enterprise"]
    assert p49["runtime_implemented"] is True
    assert p49["enforcement_implemented"] is True


def test_p50_e2e_gate_is_closed():
    p50 = load("p50")
    assert p50["e2e_verification"]["runtime_implemented"] is True
    assert p50["e2e_verification"]["verification_implemented"] is True
    assert p50["release_ready"] is False
