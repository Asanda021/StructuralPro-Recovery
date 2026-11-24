"""Minimal printed member/dimension witnesses for the column schedule.

Deliberately standalone so the offline legacy desktop does not import the
full multidisciplinary intake and its optional modern dependencies.
Keep geometry pairing rules identical to pdf_auto_intake.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
import re

_MEMBER_MARK = re.compile(
    r"(?<![A-Za-z0-9])(?P<family>BR|BP|SC|SW|C|B|W|F|P|S)\s*[-–.]?\s*(?P<index>[1-9][0-9]{0,2})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_EXPLICIT_DIM = re.compile(
    r"(?<![A-Za-z0-9])(?P<kind>L|H|W|T)\s*[=:]\s*"
    r"(?P<value>[0-9]+(?:[.٫][0-9]+)?)\s*(?P<unit>mm|cm|m)\b",
    re.IGNORECASE,
)
_UNIT_TO_M = {"mm": Decimal("0.001"), "cm": Decimal("0.01"), "m": Decimal("1")}
_DIM_KIND = {"L": "length", "H": "height", "W": "width", "T": "thickness"}


def _span_center(span):
    x0, y0, x1, y1 = span["bbox"]
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _same_rotation(a, b):
    al = math.hypot(*a)
    bl = math.hypot(*b)
    return al > 0 and bl > 0 and (a[0] * b[0] + a[1] * b[1]) / (al * bl) >= 0.985


def _score_pair(member, dimension):
    """Geometric proximity in SAME orientation; never associate by text order."""
    if not _same_rotation(member["direction"], dimension["direction"]):
        return None
    ax, ay = _span_center(member)
    bx, by = _span_center(dimension)
    dx, dy = bx - ax, by - ay
    ux, uy = member["direction"]
    norm = math.hypot(ux, uy)
    ux, uy = ux / norm, uy / norm
    along = abs(dx * ux + dy * uy)
    across = abs(-dx * uy + dy * ux)
    if across > 38 or along > 72:
        return None
    return round(across * 1.3 + along, 6)


def _parse_pdf_lines(page):
    marks, dimensions = [], []
    for block in page.get_text("dict").get("blocks", ()):
        for line in block.get("lines", ()):
            direction = tuple(line.get("dir") or (1.0, 0.0))
            for span in line.get("spans", ()):
                raw = str(span.get("text") or "")
                if not raw.strip():
                    continue
                geom = {
                    "bbox": tuple(round(float(x), 3) for x in span["bbox"]),
                    "direction": tuple(round(float(x), 6) for x in direction),
                    "printed": raw,
                }
                for match in _MEMBER_MARK.finditer(raw):
                    marks.append({
                        **geom, "tag": match.group("family").upper() + str(int(match.group("index")))
                    })
                for match in _EXPLICIT_DIM.finditer(raw):
                    value_text = match.group("value").replace("٫", ".")
                    try:
                        value = Decimal(value_text) * _UNIT_TO_M[match.group("unit").lower()]
                    except (InvalidOperation, KeyError):
                        continue
                    if value.is_finite() and value > 0:
                        dimensions.append({
                            **geom, "quantity_kind": _DIM_KIND[match.group("kind").upper()],
                            "quantity_m": str(value), "unit": "m",
                        })
    return marks, dimensions
