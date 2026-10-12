import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = [f"p{i}" for i in range(51, 61)]

def load(i):
    return json.loads((ROOT / "contracts/ervira" / f"{i}.json").read_text(encoding="utf-8"))

def test_commercial_contracts_are_implemented_but_not_release_ready():
    for i in IDS:
        d = load(i)
        assert d["schema_version"] == "1.0"
        assert d["product_id"] == "structuralpro"
        assert d["parent_platform"] == "ERVIRA"
        assert d["source_contract"] == "contracts/product-contract.json"
        assert d["version"] == "0.1.0"
        assert d["runtime_status"] == "implemented"
        assert d["release_ready"] is False

def test_catalog_pricing_and_order_runtime_boundaries():
    assert load("p51")["catalog"]["authority"] == "ERVIRA"
    assert load("p52")["detail"]["runtime_implemented"] is True
    assert load("p53")["pricing"]["no_invented_prices"] is True
    assert load("p54")["order_creation"]["status_on_create"] == "pending"

def test_payment_verification_and_entitlement_are_fail_closed():
    p55 = load("p55")["payment_status"]
    p56 = load("p56")["purchase_verification"]
    p57 = load("p57")["entitlement_after_purchase"]
    assert p55["fail_closed"] is True
    assert p56["no_client_side_payment_confirmation"] is True
    assert p57["grant_condition"] == "verified_paid_order"
    assert p57["license_issuance_idempotent"] is True

def test_refund_and_plan_change_boundaries():
    assert load("p58")["refund_cancellation"]["cancel_pending_only"] is True
    assert load("p58")["refund_cancellation"]["refund_requires_provider_confirmation"] is True
    assert load("p59")["upgrade_downgrade"]["entitlement_changes_after_payment"] is True

def test_p60_has_verification_gate():
    p60 = load("p60")["e2e_verification"]
    assert p60["verification_implemented"] is True
    assert p60["release_ready"] is False
