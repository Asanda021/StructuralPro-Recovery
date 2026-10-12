"""ERVIRA commercial license runtime client for StructuralPro.

The desktop remains offline-first: network-backed lifecycle calls are explicit,
and all remote failures fail closed. No signing secret is stored here.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable
from urllib import request


DEFAULT_ENDPOINT = "https://mbbaihvuhhmkzmuawvxg.supabase.co/functions/v1/structuralpro-license"


@dataclass(frozen=True)
class LicenseEntitlement:
    license_id: str
    status: str
    edition: str | None
    features: tuple[str, ...]
    expires_at: str | None = None

    def allows(self, feature: str) -> bool:
        return bool(feature) and self.status == "active" and feature in self.features

    def is_edition(self, edition: str) -> bool:
        return bool(edition) and self.status == "active" and self.edition == edition


class LicenseServiceError(RuntimeError):
    pass


class LicenseServiceClient:
    """Small HTTP boundary; authentication is supplied by the host application."""

    def __init__(
        self,
        access_token: str,
        endpoint: str | None = None,
        transport: Callable[[str, dict, str], dict] | None = None,
    ):
        if not access_token.strip():
            raise ValueError("access_token is required")
        self._token = access_token
        self._endpoint = endpoint or os.getenv("ERVIRA_LICENSE_ENDPOINT", DEFAULT_ENDPOINT)
        self._transport = transport or self._default_transport

    def _default_transport(self, endpoint: str, body: dict, token: str) -> dict:
        payload = json.dumps(body).encode("utf-8")
        req = request.Request(
            endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=15) as response:
                raw = response.read().decode("utf-8")
        except Exception as exc:
            raise LicenseServiceError("license service unavailable") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LicenseServiceError("license service returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise LicenseServiceError("license service returned invalid payload")
        if "error" in data:
            raise LicenseServiceError(str(data["error"]))
        return data

    def _call(self, action: str, **payload: object) -> dict:
        return self._transport(
            self._endpoint,
            {"action": action, "product_slug": "structuralpro", **payload},
            self._token,
        )

    def status(self) -> dict:
        return self._call("status")

    def issue(self, order_id: str) -> dict:
        return self._call("issue", order_id=order_id)

    def activate(self, license_key: str, device_id: str) -> dict:
        return self._call("activate", license_key=license_key, device_id=device_id)

    def deactivate(self, activation_id: str) -> dict:
        return self._call("deactivate", activation_id=activation_id)

    def renew(self, license_id: str, order_id: str) -> dict:
        return self._call("renew", license_id=license_id, order_id=order_id)
