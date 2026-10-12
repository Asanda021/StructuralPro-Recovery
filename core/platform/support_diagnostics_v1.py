"""Deterministic support diagnostics with secret redaction."""
from __future__ import annotations

import json
from typing import Any, Mapping

_REDACTED = "<redacted>"
_SECRET_MARKERS = ("password", "passwd", "secret", "token", "api_key", "apikey", "private_key", "credential")


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(marker in normalized for marker in _SECRET_MARKERS)


def redact_diagnostics(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _REDACTED if _is_secret_key(str(key)) else redact_diagnostics(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [redact_diagnostics(item) for item in value]
    return value


def diagnostics_snapshot(payload: Mapping[str, Any]) -> str:
    """Return a stable JSON snapshot safe for support evidence."""
    return json.dumps(redact_diagnostics(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
