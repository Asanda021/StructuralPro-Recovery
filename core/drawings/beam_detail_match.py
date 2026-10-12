"""Evidence-only cross-references from drawing labels to a reviewed beam.

This is a locator, not rebar recognition. Matching never approves dimensions,
reinforcement, scale or quantities. Coordinate-less PDF matches stay page-wide.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
import re
import unicodedata
from typing import Any, Iterable

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_label(value: str) -> str:
    """Keep beam tags deterministic across Persian digits and Unicode widths."""
    if not isinstance(value, str):
        raise ValueError("شناسه تیر باید متنی باشد")
    return unicodedata.normalize("NFKC", value).translate(_DIGITS).strip().upper()


def _beam_pattern(beam_id: str) -> re.Pattern:
    tag = normalize_label(beam_id)
    if not tag or not re.fullmatch(r"[\w\-]+", tag, flags=re.UNICODE):
        raise ValueError("شناسه تیر برای جستجوی نقشه معتبر نیست")
    # Do not mistake B1 for B10, B11, XB1 or B1-EXTRA.
    return re.compile(r"(?<![\w-])" + re.escape(tag) + r"(?![\w-])", re.UNICODE)


@dataclass(frozen=True)
class BeamEvidence:
    source_ref: str
    text: str
    kind: str
    page: int
    layer: str = ""
    handle: str = ""
    in_selected_region: bool = False
    located: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _inside(x: float, y: float, region: tuple[float, float, float, float]) -> bool:
    x0, y0, w, h = (float(v) for v in region)
    if not all(math.isfinite(v) for v in (x, y, x0, y0, w, h)) or w <= 0 or h <= 0:
        raise ValueError("انتخاب ناحیه نقشه نامعتبر است")
    return x0 <= x <= x0 + w and y0 <= y <= y0 + h


def cad_beam_evidence(doc: Any, beam_id: str, *,
                      region: tuple[float, float, float, float] | None = None,
                      scene_origin: tuple[float, float] | None = None,
                      page: int = 1) -> tuple[BeamEvidence, ...]:
    """Find CAD TEXT/MTEXT tags, with exact handle-based audit references.

    ``scene_origin`` is (minimum model X including margin, maximum model Y
    including margin) as used by GraphicalTakeoffDialog._render_cad.
    When either a region or transform is missing, all matches remain unlocated.
    """
    pattern = _beam_pattern(beam_id)
    if isinstance(page, bool) or int(page) != page or page < 1:
        raise ValueError("شماره صفحه نامعتبر است")
    if region is not None and scene_origin is None:
        raise ValueError("تبدیل مختصات CAD به پنجره نمایش مشخص نیست")
    if scene_origin is not None:
        if len(scene_origin) != 2 or not all(math.isfinite(float(v)) for v in scene_origin):
            raise ValueError("مختصات مبدأ نمایش CAD نامعتبر است")
    output: list[BeamEvidence] = []
    seen: set[str] = set()
    for i, entity in enumerate(getattr(doc, "entities", ())):
        if getattr(entity, "entity_type", "") not in {"TEXT", "MTEXT"}:
            continue
        data = getattr(entity, "data", {})
        raw = str(data.get("text") or "")
        if not pattern.search(normalize_label(raw)):
            continue
        handle = str(getattr(entity, "handle", "") or "")
        layer = str(getattr(entity, "layer", "") or "")
        ref = f"cad:page:{int(page)}:handle:{handle}" if handle else f"cad:page:{int(page)}:entity:{i}"
        if ref in seen:
            # Duplicated CAD handles cannot be trusted as distinct sources.
            raise ValueError("شناسه CAD تکراری است؛ ارتباط دیتایل تا بررسی نقشه متوقف شد")
        seen.add(ref)
        located = False
        selected = False
        insert = data.get("insert")
        if insert is not None and scene_origin is not None:
            try:
                x, y = (float(insert[0]), float(insert[1]))
            except (TypeError, IndexError, ValueError) as exc:
                raise ValueError("مختصات برچسب تیر در CAD نامعتبر است") from exc
            if not all(math.isfinite(v) for v in (x, y)):
                raise ValueError("مختصات برچسب تیر در CAD نامعتبر است")
            located = True
            if region is not None:
                selected = _inside(x - float(scene_origin[0]), float(scene_origin[1]) - y, region)
        output.append(BeamEvidence(ref, raw.strip(), "cad", int(page), layer,
                                   handle, selected, located))
    return tuple(output)


def pdf_beam_evidence(page_text: str, beam_id: str, *, page: int) -> tuple[BeamEvidence, ...]:
    """PDF page text has no geometry in this adapter: never claim region match."""
    pattern = _beam_pattern(beam_id)
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("صفحه PDF باید صحیح و مثبت باشد")
    if not isinstance(page_text, str):
        raise ValueError("متن PDF معتبر نیست")
    found = []
    for line_number, line in enumerate(page_text.splitlines(), 1):
        if pattern.search(normalize_label(line)):
            found.append(BeamEvidence(f"pdf:page:{page}:line:{line_number}", line.strip(),
                                      "pdf", page))
    return tuple(found)


def suggested_link(evidence: Iterable[BeamEvidence]) -> dict[str, Any]:
    """Report candidates without arbitrarily picking one or marking it reviewed."""
    items = tuple(evidence)
    spatial = tuple(item for item in items if item.in_selected_region)
    return {
        "candidates": [item.to_dict() for item in items],
        "in_region": len(spatial),
        "status": "no_match" if not items else "needs_explicit_selection",
        "requires_review": True,
        "quantity_approved": False,
    }