import json
from types import SimpleNamespace

import pytest

from core.sync.cloud import HTTPJSONSyncProvider


def test_cloud_provider_requires_https_by_default():
    with pytest.raises(ValueError, match="HTTPS"):
        HTTPJSONSyncProvider("http://sync.example.com")


def test_cloud_provider_allows_explicit_local_http():
    provider = HTTPJSONSyncProvider(
        "http://127.0.0.1:8080",
        allow_insecure_local=True,
        timeout=3,
    )
    assert provider.timeout == 3


def test_cloud_provider_rejects_invalid_url_and_timeout():
    with pytest.raises(ValueError, match="absolute"):
        HTTPJSONSyncProvider("sync.example.com")
    with pytest.raises(ValueError, match="positive"):
        HTTPJSONSyncProvider("https://sync.example.com", timeout=0)


def test_push_validates_acknowledgements(monkeypatch):
    provider = HTTPJSONSyncProvider("https://sync.example.com")
    monkeypatch.setattr(
        provider,
        "_request",
        lambda *args, **kwargs: {"pushed": 1, "acknowledged_ids": ["a"]},
    )
    assert provider.push([{"record_id": "a"}])["acknowledged_ids"] == ["a"]

    monkeypatch.setattr(
        provider,
        "_request",
        lambda *args, **kwargs: {"pushed": 1, "acknowledged_ids": "a"},
    )
    with pytest.raises(ValueError, match="acknowledgements"):
        provider.push([])


def test_pull_rejects_non_list_and_escapes_project_id(monkeypatch):
    provider = HTTPJSONSyncProvider("https://sync.example.com")
    captured = {}

    def fake_request(method, path, payload=None):
        captured["method"] = method
        captured["path"] = path
        return [{"project_id": "p"}]

    monkeypatch.setattr(provider, "_request", fake_request)
    assert provider.pull("P/1?x=2") == [{"project_id": "p"}]
    assert captured == {"method": "GET", "path": "/sync/pull/P%2F1%3Fx%3D2"}

    monkeypatch.setattr(provider, "_request", lambda *args, **kwargs: {})
    with pytest.raises(ValueError, match="list"):
        provider.pull("P1")


def test_request_does_not_place_token_in_url(monkeypatch):
    provider = HTTPJSONSyncProvider("https://sync.example.com", token="secret")
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"pushed":0}'

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(provider._opener, "open", fake_open)
    assert provider._request("POST", "/sync/push", []) == {"pushed": 0}
    assert "secret" not in captured["url"]
    assert captured["authorization"] == "Bearer secret"
    assert captured["timeout"] == 15


def test_redirect_guard_rejects_insecure_and_cross_host_redirects():
    from core.sync.cloud import _HTTPSRedirectGuard

    guard = _HTTPSRedirectGuard()
    request = SimpleNamespace(full_url="https://sync.example.com/sync/push")
    with pytest.raises(ValueError, match="insecure redirects"):
        guard.redirect_request(request, None, 302, "Found", {}, "http://sync.example.com/login")
    with pytest.raises(ValueError, match="cross-host"):
        guard.redirect_request(request, None, 302, "Found", {}, "https://evil.example.com/login")
