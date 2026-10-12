"""Evidence-only rebar callout proposals for StructuralPro beam drawings.

No quantity, steel weight, stirrup count or cutting length is inferred.
All callouts remain unapproved engineering hints with source references.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable

from core.drawings.beam_detail_match import BeamEvidence, _beam_pattern, normalize_label

_CATEGORIES = {
    "longitudinal": r"(?:میلگرد\s+طولی|آرماتور\s+طولی|LONGITUDINAL)",
    "stirrups": r"(?:خاموت|STIRRUPS?)",
    "side_bars": r"(?:کمرکش(?:\s+تیر)?|میلگرد\s+جان|SIDE\s+BARS?)",
    "crossties": r"(?:سنجاقی|CROSS\s*TIES?)",
    "additional": r"(?:میلگرد\s+تقویتی|آرماتور\s+تقویتی|تقویتی|ADDITIONAL\s+BARS?)",
}
_MARK = re.compile(r"(?<![\w])(?:(?P<count>\d+)\s*)?[ΦØ⌀]\s*(?P<diam>\d+(?:\.\d+)?)(?![\d.])")
_SPACING = re.compile(r"@\s*(?P<gap>\d+(?:\.\d+)?)\s*(?P<unit>MM|CM|M|میلی[‌ -]?متر|سانتی[‌ -]?متر|متر)?(?![\w])", re.I)
_UNIT = {"MM": .001, "CM": .01, "M": 1.0, "میلیمتر": .001,
         "میلی متر": .001, "میلی‌متر": .001, "سانتیمتر": .01,
         "سانتی متر": .01, "سانتی‌متر": .01, "متر": 1.0}
_OTHER_BEAM = re.compile(r"(?<![\w-])[A-Z]{1,3}-?\d+(?![\w-])")


@dataclass(frozen=True)
class RebarHint:
    kind: str
    source_ref: str
    page: int
    raw_text: str
    diameter_mm: float
    count: int | None
    spacing_m: float | None
    issues: tuple[str, ...]
    requires_review: bool = True
    quantity_approved: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["issues"] = list(self.issues)
        return data


def _explicit_type(line: str) -> str | None:
    matches = [name for name, expression in _CATEGORIES.items()
               if re.search(expression, line, re.IGNORECASE | re.UNICODE)]
    return matches[0] if len(matches) == 1 else None


def propose_rebar_from_evidence(evidence: Iterable[BeamEvidence], beam_id: str) -> dict:
    """Propose only explicit beam-tagged, category-tagged, single-series callouts.

    Ø20/Φ20 are nominal diameter designations in mm. @ spacing requires
    explicit length units. Unknown cutting lengths and hook geometry block BOQ.
    """
    beam = normalize_label(beam_id)
    pattern = _beam_pattern(beam)
    result: list[RebarHint] = []
    warnings: list[str] = []
    seen = set()
    for item in evidence:
        if not isinstance(item, BeamEvidence) or not item.source_ref.strip():
            raise ValueError("مرجع متن دیتایل میلگرد معتبر نیست")
        if not isinstance(item.page, int) or isinstance(item.page, bool) or item.page < 1:
            raise ValueError("شماره صفحه دیتایل معتبر نیست")
        for fragment_no, raw in enumerate(item.text.splitlines(), 1):
            for part_no, fragment in enumerate(re.split(r"[;؛]+", raw), 1):
                line = normalize_label(fragment)
                if not pattern.search(line):
                    continue
                tags = _OTHER_BEAM.findall(line)
                if any(tag != beam for tag in tags):
                    warnings.append(f"{item.source_ref}: چند شناسه تیر در یک عبارت دیده شد")
                    continue
                kind = _explicit_type(line)
                if kind is None:
                    warnings.append(f"{item.source_ref}: نوع آرماتور صریح یا یکتا نیست")
                    continue
                marks = list(_MARK.finditer(line))
                if len(marks) != 1:
                    warnings.append(f"{item.source_ref}: مشخصات قطر یا سری میلگرد مبهم است")
                    continue
                mark = marks[0]
                diameter = float(mark.group("diam"))
                if not 0 < diameter <= 100:
                    warnings.append(f"{item.source_ref}: قطر میلگرد نامعتبر است")
                    continue
                count = int(mark.group("count")) if mark.group("count") is not None else None
                if count is not None and not 0 < count <= 100000:
                    warnings.append(f"{item.source_ref}: تعداد میلگرد نامعتبر است")
                    continue
                issues = []
                if count is None:
                    issues.append("تعداد میلگرد از دیتایل قابل اثبات نیست")
                gaps = list(_SPACING.finditer(line))
                spacing = None
                if len(gaps) > 1:
                    issues.append("چند فاصله خاموت در یک عبارت وجود دارد")
                elif len(gaps) == 1:
                    gap = gaps[0]
                    unit = gap.group("unit")
                    if unit is None:
                        issues.append("واحد فاصله خاموت مشخص نیست")
                    elif kind != "stirrups":
                        issues.append("فاصله برای این گروه میلگرد نیازمند بررسی است")
                    else:
                        factor = _UNIT.get(unit.upper() if unit.isascii() else unit)
                        if factor is None or not 0 < float(gap.group("gap")) * factor <= 10:
                            issues.append("فاصله خاموت نامعتبر است")
                        else:
                            spacing = float(gap.group("gap")) * factor
                if kind == "stirrups" and spacing is not None:
                    issues.append("تعداد خاموت از فاصله به‌تنهایی قابل محاسبه نیست")
                key = (item.source_ref, fragment_no, part_no, kind)
                if key in seen:
                    raise ValueError("منبع پیشنهاد آرماتور تکراری است")
                seen.add(key)
                result.append(RebarHint(kind, item.source_ref, item.page, fragment.strip(),
                                        diameter, count, spacing, tuple(issues)))
    by_kind = {}
    for hint in result:
        by_kind.setdefault(hint.kind, []).append(hint)
    for kind, candidates in by_kind.items():
        if len(candidates) > 1:
            warnings.append(f"{kind}: چند سری یا چند مرجع مشاهده شد؛ جمع‌زدن خودکار ممنوع")
    return {"beam_id": beam, "candidates": [hint.to_dict() for hint in result],
            "warnings": warnings, "requires_review": True,
            "quantity_approved": False, "ready_for_boq": False}
