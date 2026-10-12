import pytest

from core.platform.commercial_service import CommercialServiceClient, CommercialServiceError


def test_client_requires_access_token():
    with pytest.raises(ValueError):
        CommercialServiceClient("")


def test_catalog_uses_structuralpro_product_boundary():
    calls = []

    def transport(endpoint, body, token):
        calls.append((endpoint, body, token))
        return {"products": []}

    client = CommercialServiceClient("token", endpoint="https://example.test/commerce", transport=transport)
    assert client.catalog() == {"products": []}
    assert calls == [(
        "https://example.test/commerce",
        {"action": "catalog", "product_slug": "structuralpro"},
        "token",
    )]


def test_full_commercial_lifecycle_actions():
    def transport(endpoint, body, token):
        return {"action": body["action"], "ok": True}

    client = CommercialServiceClient("token", transport=transport)
    assert client.detail()["action"] == "detail"
    assert client.pricing("professional")["action"] == "pricing"
    assert client.create_order("professional")["action"] == "create_order"
    assert client.checkout("order-1")["action"] == "checkout"
    assert client.payment_status("order-1")["action"] == "payment_status"
    assert client.cancel("order-1")["action"] == "cancel"
    assert client.refund("order-1")["action"] == "refund"
    assert client.upgrade("pro", "order-old")["action"] == "upgrade"
    assert client.downgrade("standard", "order-old")["action"] == "downgrade"


def test_remote_error_is_fail_closed():
    def transport(endpoint, body, token):
        raise CommercialServiceError("boom")

    client = CommercialServiceClient("token", transport=transport)
    with pytest.raises(CommercialServiceError):
        client.payment_status("order-1")
