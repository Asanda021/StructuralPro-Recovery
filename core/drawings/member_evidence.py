"""Unapproved evidence index for beam, column, grade-beam and foundation sheets.

Works on CAD TEXT/MTEXT entities or searchable PDF pages. Never interprets
raster-only scans, extracts quantities from neighboring rows, or commits takeoff.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from core.drawings.beam_detail_match import (
    cad_beam_evidence, pdf_beam_evidence, normalize_label, _unambiguous_member_statement,
)

_SUPPORTED = {
    "beam": ("length", "width", "depth"),
    "column": ("width", "depth", "height"),
    "tie_beam": ("length", "width", "depth"),
    "isolated_footing": ("length", "width", "thickness"),
    "strip_footing": ("length", "width", "thickness"),
    "mat_footing": ("length", "width", "thickness"),
}
_LABELS = {
    "length": ("طول", "LENGTH"),
    "width": ("عرض", "WIDTH"),
    "depth": ("عمق", "DEPTH"),
    "height": ("ارتفاع", "HEIGHT"),
    "thickness": ("ضخامت", "THICKNESS"),
}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_UNITS = {"MM": 0.001, "CM": 0.01, "M": 1.0,
          "میلی‌متر": 0.001, "میلی متر": 0.001, "میلیمتر": 0.001,
          "سانتی‌متر": 0.01, "سانتی متر": 0.01, "سانتیمتر": 0.01,
          "متر": 1.0}
_UNIT_PATTERN = r"(?:MM|CM|M|میلی[‌ ]?متر|سانتی[‌ ]?متر|متر)"
_FLOAT_PATTERN = r"[0-9]+(?:\.[0-9]+)?"


def explicit_member_dimensions(text: str, kind: str, tag: str) -> dict[str, float] | None:
    """Only a fully explicit same-row dimension schedule can propose geometry.

    No B/H interpretation, 30x50 guess, unknown unit or default quantities.
    """
    if kind not in _SUPPORTED:
        raise KeyError(kind)
    text = _unambiguous_member_statement(text, tag)
    if text is None:
        return None
    values: dict[str, float] = {}
    for key in _SUPPORTED[kind]:
        labels = "|".join(re.escape(x) for x in _LABELS[key])
        regex = rf"(?<!\w)(?:{labels})\s*[:=]\s*({_FLOAT_PATTERN})\s*({_UNIT_PATTERN})(?!\w)"
        found = list(re.finditer(regex, text, re.I | re.UNICODE))
        if len(found) != 1:
            return None
        raw, unit = found[0].groups()
        multiplier = _UNITS.get(unit.upper() if unit.isascii() else unit)
        if multiplier is None:
            return None
        number = float(raw) * multiplier
        if not math.isfinite(number) or number <= 0:
            return None
        values[key] = number
    return values


def index_member_evidence(
    kind: str, member_id: str, *, drawing_sha256: str,
    cad_document: Any = None, cad_region: tuple | None = None,
    cad_scene_origin: tuple | None = None, pdf_engine: Any = None,
) -> dict[str, Any]:
    """Produce strictly source-bound references for engineer selection.

    CAD source and PDF source must be distinguished; page-wide PDF text is
    not marked as located, even if a viewport was selected on another page.
    """
    if kind not in _SUPPORTED:
        raise KeyError(f"عضو پشتیبانی‌نشده: {kind}")
    if (cad_document is None) == (pdf_engine is None):
        raise ValueError("دقیقاً یک منبع CAD یا PDF معتبر باید انتخاب شود")
    sha = str(drawing_sha256 or "")
    if len(sha) != 64 or any(x not in "0123456789abcdefABCDEF" for x in sha):
        raise ValueError("SHA-256 منبع نقشه نامعتبر است")
    if cad_document is not None:
        candidates = cad_beam_evidence(
            cad_document, member_id, region=cad_region,
            scene_origin=cad_scene_origin, page=1)
    else:
        candidates = tuple(
            entry for page in range(1, pdf_engine.page_count + 1)
            for entry in pdf_beam_evidence(pdf_engine.text(page), member_id, page=page)
        )
    rows = []
    for candidate in candidates:
        data = candidate.to_dict()
        data["beam_tag"] = normalize_label(member_id)  # shared legacy validator key
        data["drawing_sha256"] = sha.lower()
        data["proposed_geometry"] = explicit_member_dimensions(candidate.text, kind, member_id)
        data["quantity_approved"] = False
        data["requires_review"] = True
        rows.append(data)
    return {"kind": kind, "member_id": normalize_label(member_id),
            "candidates": rows, "status": "no_match" if not rows else "needs_explicit_selection",
            "ready_for_boq": False, "quantity_approved": False,
            "searchable_text_only": True}
