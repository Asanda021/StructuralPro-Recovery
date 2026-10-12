"""ERVIRA commercial runtime boundary for StructuralPro.

All commercial authority remains in ERVIRA. The desktop never confirms payment
locally and treats remote failures as non-entitled/fail-closed.
"""
from __future__ import annotations

import json
import os
from typing import Callable
from urllib import request

DEFAULT_ENDPOINT = "https://mbbaihvuhhmkzmuawvxg.supabase.co/functions/v1/structuralpro-commerce"


class CommercialServiceError(RuntimeError):
    pass


class CommercialServiceClient:
    def __init__(
        self,
        access_token: str,
        endpoint: str | None = None,
        transport: Callable[[str, dict, str], dict] | None = None,
    ):
        if not access_token.strip():
            raise ValueError("access_token is required")
        self._token = access_token
        self._endpoint = endpoint or os.getenv("ERVIRA_COMMERCE_ENDPOINT", DEFAULT_ENDPOINT)
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
            raise CommercialServiceError("commercial service unavailable") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommercialServiceError("commercial service returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise CommercialServiceError("commercial service returned invalid payload")
        if "error" in data:
            raise CommercialServiceError(str(data["error"]))
        return data

    def _call(self, action: str, **payload: object) -> dict:
        return self._transport(
            self._endpoint,
            {"action": action, "product_slug": "structuralpro", **payload},
            self._token,
        )

    def catalog(self) -> dict:
        return self._call("catalog")

    def detail(self) -> dict:
        return self._call("detail")

    def pricing(self, plan_slug: str) -> dict:
        return self._call("pricing", plan_slug=plan_slug)

    def create_order(self, plan_slug: str) -> dict:
        return self._call("create_order", plan_slug=plan_slug)

    def checkout(self, order_id: str) -> dict:
        return self._call("checkout", order_id=order_id)

    def payment_status(self, order_id: str) -> dict:
        return self._call("payment_status", order_id=order_id)

    def cancel(self, order_id: str) -> dict:
        return self._call("cancel", order_id=order_id)

    def refund(self, order_id: str) -> dict:
        return self._call("refund", order_id=order_id)

    def upgrade(self, plan_slug: str, source_order_id: str | None = None) -> dict:
        return self._call("upgrade", plan_slug=plan_slug, source_order_id=source_order_id)

    def downgrade(self, plan_slug: str, source_order_id: str | None = None) -> dict:
        return self._call("downgrade", plan_slug=plan_slug, source_order_id=source_order_id)
