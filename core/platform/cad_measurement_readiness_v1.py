"""Deterministic readiness contract for production CAD/PDF measurement backends.

This module does not pretend to convert DWG or render graphical PDF content.
It exposes an explicit fail-closed boundary so unsupported backends cannot
silently degrade into incorrect quantities.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class MeasurementBackendReadiness:
    dwg_converter_available: bool
    pdf_renderer_available: bool
    converter_version: str | None = None
    renderer_version: str | None = None

    def evaluate(self) -> dict[str, object]:
        reasons: list[str] = []
        if not self.dwg_converter_available:
            reasons.append("dwg_converter_unavailable")
        elif not self.converter_version:
            reasons.append("dwg_converter_version_missing")
        if not self.pdf_renderer_available:
            reasons.append("pdf_renderer_unavailable")
        elif not self.renderer_version:
            reasons.append("pdf_renderer_version_missing")
        ready = not reasons
        payload = {
            "ready": ready,
            "dwg_converter_available": self.dwg_converter_available,
            "pdf_renderer_available": self.pdf_renderer_available,
            "converter_version": self.converter_version,
            "renderer_version": self.renderer_version,
            "reasons": reasons,
        }
        payload["fingerprint"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return payload
