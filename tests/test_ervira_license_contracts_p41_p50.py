import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = [f"p{i}" for i in range(41, 51)]


def load(i):
    return json.loads((ROOT / "contracts" / "ervira" / f"p{i}.json").read_text(encoding="utf-8"))


def test_license_contracts_are_implemented_but_not_release_ready():
    for i in range(41, 51):
        d = load(i)
        assert d["product_id"] == "structuralpro"
        assert d["parent_platform"] == "ERVIRA"
        assert d["version"] == "0.1.0"
        assert d["runtime_status"] == "implemented"
        assert d["release_ready"] is False


def test_license_service_contract_is_ervira_and_has_lifecycle_actions():
    d = load(41)
    assert d["license_service"]["provider"] == "ERVIRA"
    assert set(d["license_service"]["actions"]) == {
        "status", "issue", "activate", "deactivate", "renew"
    }


def test_issuance_requires_paid_order():
    assert load(42)["issuance"]["requires_paid_order"] is True


def test_activation_and_deactivation_require_runtime_identifiers():
    assert load(43)["activation"]["requires_license_key"] is True
    assert load(43)["activation"]["requires_device_id"] is True
    assert load(44)["deactivation"]["requires_activation_id"] is True


def test_renewal_is_payment_gated_and_expiration_is_fail_closed():
    assert load(45)["renewal"]["requires_paid_renewal_order"] is True
    assert load(46)["expiration"]["client_fail_closed"] is True


def test_revocation_and_entitlement_boundaries_are_defined():
    assert set(load(47)["revocation"]["statuses"]) == {"suspended", "revoked"}
    assert set(load(48)["edition_entitlement"]["editions"]) == {
        "light", "standard", "pro", "enterprise"
    }
    assert load(49)["feature_entitlement"]["enforcement_implemented"] is True


def test_final_license_gate_has_verification():
    d = load(50)
    assert d["e2e_verification"]["verification_implemented"] is True
    assert d["release_ready"] is False
