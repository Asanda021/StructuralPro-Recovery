import pytest

from core.sync.session import SyncAuthenticator, SyncSession


def test_session_requires_account_and_device():
    with pytest.raises(ValueError, match="account_id"):
        SyncSession("", "dev-1")
    with pytest.raises(ValueError, match="device_id"):
        SyncSession("acct-1", "")


def test_session_requires_matching_device():
    session = SyncSession("acct-1", "dev-1", "token")
    assert session.require_auth() is session
    assert session.require_device("dev-1") is session
    with pytest.raises(PermissionError, match="device binding"):
        session.require_device("dev-2")


def test_authenticator_returns_device_bound_authenticated_session():
    calls = []

    def authenticate(account_id, secret, device_id):
        calls.append((account_id, secret, device_id))
        return "token-1"

    session = SyncAuthenticator(authenticate).login("acct-1", "secret", "dev-1")
    assert session.authenticated
    assert session.device_id == "dev-1"
    assert calls == [("acct-1", "secret", "dev-1")]


def test_authenticator_fails_closed_without_device_or_token():
    with pytest.raises(ValueError, match="device_id"):
        SyncAuthenticator(lambda *_: "token").login("acct-1", "secret", "")

    with pytest.raises(PermissionError, match="authentication failed"):
        SyncAuthenticator(lambda *_: "").login("acct-1", "secret", "dev-1")
