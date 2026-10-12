"""Authenticated, device-bound sync session contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SyncSession:
    account_id: str
    device_id: str
    access_token: str | None = None

    def __post_init__(self):
        if not self.account_id.strip():
            raise ValueError("account_id is required")
        if not self.device_id.strip():
            raise ValueError("device_id is required")

    @property
    def authenticated(self):
        return bool(self.access_token)

    def require_auth(self):
        if not self.authenticated:
            raise PermissionError("sync authentication required")
        return self

    def require_device(self, device_id: str):
        if not device_id or device_id != self.device_id:
            raise PermissionError("sync device binding mismatch")
        return self


class SyncAuthenticator:
    """Provider-neutral authentication boundary with explicit device binding."""

    def __init__(self, authenticate: Callable[[str, str, str], str]):
        self._authenticate = authenticate

    def login(self, account_id, secret, device_id):
        if not device_id or not device_id.strip():
            raise ValueError("device_id is required")
        token = self._authenticate(account_id, secret, device_id)
        if not token:
            raise PermissionError("sync authentication failed")
        return SyncSession(account_id, device_id, token)
