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


_EXPLICIT_NUMBER = r"([0-9]+(?:\.[0-9]+)?)"
_EXPLICIT_UNIT = r"(mm|cm|m|میلی[‌ -]?متر|سانتی[‌ -]?متر|متر)"


def _unambiguous_member_statement(text: str, member_id: str) -> str | None:
    """Bind dimension proposals to one explicitly tagged statement only.

    A CAD MTEXT block can contain several schedule rows. Presence of the
    selected tag somewhere in that block cannot assign the other rows' values
    to it. Multiline/shared-member statements remain manual-review evidence.
    """
    if not isinstance(text, str):
        return None
    content = normalize_label(text)
    # DXF MTEXT retains its literal paragraph marker in the CAD adapter.
    statements = [part.strip() for part in re.split(r"\\P|[\r\n;؛]+", content) if part.strip()]
    if len(statements) != 1 or not _beam_pattern(member_id).search(statements[0]):
        return None
    tag = normalize_label(member_id)
    # Letter+number identities in either script, including suffixed members.
    # Unknown shared schedules stay manual; do not select one member's values.
    tags = re.findall(r"(?<![\w-])[^\W\d_]+-?\d+(?:[\w-]*)(?![\w-])", statements[0])
    if any(candidate != tag for candidate in tags):
        return None
    return statements[0]


def parse_section_hint(text: str, beam_id: str) -> dict[str, float] | None:
    """Offer b/h only when BOTH dimensions have explicit labels and units.

    Never interpret bare `30x50` as width/depth; never infer beam length,
    bar counts, hooks or reinforcement from adjacent schedule text.
    """
    content = _unambiguous_member_statement(text, beam_id)
    if content is None:
        return None
    definitions = {
        "width_m": r"(?<![\w])(?:B|عرض(?:\s+تیر)?)",
        "depth_m": r"(?<![\w])(?:H|ارتفاع(?:\s+مقطع|\s+تیر)?)",
    }
    unit_factor = {"MM": .001, "CM": .01, "M": 1.0,
                   "میلیمتر": .001, "میلی متر": .001, "میلی‌متر": .001,
                   "سانتیمتر": .01, "سانتی متر": .01, "سانتی‌متر": .01,
                   "متر": 1.0}
    values = {}
    for name, label in definitions.items():
        regex = label + r"\s*[:=]\s*" + _EXPLICIT_NUMBER + r"\s*" + _EXPLICIT_UNIT + r"(?![\w])"
        matches = list(re.finditer(regex, content, re.UNICODE | re.IGNORECASE))
        if len(matches) != 1:
            return None
        raw, unit = matches[0].groups()
        factor = unit_factor.get(unit.upper() if unit.isascii() else unit)
        if factor is None:
            return None
        value = float(raw) * factor
        if not math.isfinite(value) or value <= 0:
            return None
        values[name] = value
    return values


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



def validate_evidence_link(source: dict[str, Any], beam_id: str) -> None:
    """Reject mismatched beam/page refs in optional persisted drawing evidence.

    This verifies metadata consistency only; the user's engineering approval and
    drawing file integrity checks remain separate, mandatory gates.
    """
    evidence = source.get("detail_evidence")
    if evidence is None:
        return
    if source.get("mode") != "drawing" or not isinstance(evidence, dict):
        raise ValueError("مرجع دیتایل باید به نقشه معتبر متصل باشد")
    tag = normalize_label(beam_id)
    if normalize_label(evidence.get("beam_tag")) != tag:
        raise ValueError("مرجع دیتایل به تیر دیگری تعلق دارد")
    text = evidence.get("text")
    if not isinstance(text, str) or not _beam_pattern(beam_id).search(normalize_label(text)):
        raise ValueError("متن مرجع دیتایل با شناسه تیر مطابقت ندارد")
    page = evidence.get("page")
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("شماره صفحه مرجع دیتایل معتبر نیست")
    kind = evidence.get("kind")
    ref = evidence.get("source_ref")
    prefix = {"cad": f"cad:page:{page}:", "pdf": f"pdf:page:{page}:"}.get(kind)
    if not prefix or not isinstance(ref, str) or not ref.startswith(prefix):
        raise ValueError("شناسه منبع دیتایل معتبر نیست")
    sha = source.get("sha256")
    if not isinstance(sha, str) or evidence.get("drawing_sha256") != sha:
        raise ValueError("اثر انگشت فایل دیتایل با نقشه انتخابی یکسان نیست")
    # A PDF detail may be on another page of the *same* SHA-256 verified file.
    # CAD modelspace in this viewer always maps to page 1.
    if kind == "cad" and page != source.get("page"):
        raise ValueError("صفحه برچسب CAD با صفحه نمایش نقشه ناسازگار است")


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
