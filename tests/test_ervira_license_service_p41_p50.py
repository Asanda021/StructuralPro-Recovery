import pytest
from core.platform.license_service import LicenseEntitlement, LicenseServiceClient, LicenseServiceError


def test_entitlement_enforcement_is_exact_and_fail_closed():
    entitlement = LicenseEntitlement("lic-1", "active", "pro", ("takeoff", "reports"))
    assert entitlement.allows("takeoff")
    assert not entitlement.allows("finance")
    assert entitlement.is_edition("pro")
    assert not entitlement.is_edition("enterprise")
    assert not LicenseEntitlement("lic-2", "expired", "pro", ("takeoff",)).allows("takeoff")


def test_client_contract_sends_structuralpro_action():
    calls = []

    def transport(endpoint, body, token):
        calls.append((endpoint, body, token))
        return {"licenses": []}

    client = LicenseServiceClient("token", endpoint="https://example.test/license", transport=transport)
    assert client.status() == {"licenses": []}
    assert calls == [(
        "https://example.test/license",
        {"action": "status", "product_slug": "structuralpro"},
        "token",
    )]


def test_client_supports_full_lifecycle_actions():
    def transport(endpoint, body, token):
        return {"action": body["action"], "ok": True}

    client = LicenseServiceClient("token", transport=transport)
    assert client.issue("order-1")["action"] == "issue"
    assert client.activate("LIC-1", "device-1")["action"] == "activate"
    assert client.deactivate("activation-1")["action"] == "deactivate"
    assert client.renew("license-1", "order-2")["action"] == "renew"


def test_client_requires_access_token():
    with pytest.raises(ValueError):
        LicenseServiceClient("")


def test_remote_errors_are_exposed_as_license_errors():
    def transport(endpoint, body, token):
        raise LicenseServiceError("boom")

    client = LicenseServiceClient("token", transport=transport)
    with pytest.raises(LicenseServiceError):
        client.status()
