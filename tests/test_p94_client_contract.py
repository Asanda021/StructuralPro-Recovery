import pytest
from core.platform.clients import ClientRequest, ClientResponse, ProductClient

def req(platform="windows", project_id="P1", action="open_project"):
    return ClientRequest("R1", platform, action, project_id, {})

def test_request_payload_and_response_data_are_typed():
    with pytest.raises(TypeError, match="payload"):
        ClientRequest("R1", "windows", "x", "P1", [])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="response data"):
        ClientResponse("R1", True, [])  # type: ignore[arg-type]

def test_product_client_rejects_cross_platform_requests():
    response=ProductClient("windows").request(req("android"))
    assert not response.ok and response.error=="request platform mismatch"

def test_product_client_enforces_active_project_identity():
    client=ProductClient("windows"); client.open_project("P1")
    response=client.request(req(project_id="P2"))
    assert not response.ok and response.error=="request project mismatch"

def test_product_client_routes_open_project_through_shared_contract():
    response=ProductClient("windows").request(req())
    assert response.ok and response.data=={"id":"P1","platform":"windows"}

def test_product_client_uses_provider_handler_and_fails_closed():
    seen=[]
    def handler(request):
        seen.append(request.request_id); return {"accepted": True}
    client=ProductClient("android", request_handler=handler)
    response=client.request(req("android", "P1", "sync"))
    assert response.ok and response.data=={"accepted": True} and seen==["R1"]
    failing=ProductClient("android", request_handler=lambda request: (_ for _ in ()).throw(RuntimeError("boom")))
    failed=failing.request(req("android", "P1", "sync"))
    assert not failed.ok and failed.error=="request failed: RuntimeError"

def test_unsupported_action_is_explicit():
    response=ProductClient("telegram").request(req("telegram", "P1", "unknown"))
    assert not response.ok and response.error=="unsupported client action"
