"""Source-backed, read-only 2D takeoff overlay for Phase 7 priority 2.

This is a *measured-region overlay*, not an automatically inferred building plan.
It only renders existing area takeoffs whose PDF/CAD source and exact geometry
are validated by the original DrawingTakeoffSession and takeoff bridge.
No BOQ writes, quantities, guessed dimensions, new source approval or AI.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
from html import escape
from pathlib import Path

from core.drawings.takeoff_bridge import (
    session_to_boq_rows, verified_measurement_identities,
)
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.planar_geometry import region, decimal_text
from core.reports.decimal_values import decimal_value


def _id(value, name):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} مستند الزامی است")
    return value


def _coordinate(value):
    number = (Decimal(decimal_text(value)) if isinstance(value, Fraction)
              else decimal_value(value, field="source coordinate"))
    if abs(number) > Decimal("1e12"):
        raise ValueError("مختصات منبع خارج از محدوده است")
    return number


def _path(points):
    return "M " + " L ".join(
        f"{format(_coordinate(x),'f')} {format(_coordinate(y),'f')}"
        for x, y in points
    ) + " Z"


def build_source_backed_2d_overlay(
    snapshot: dict, *, project_id: str, revision: str, page: int,
    selected_takeoff_ids: tuple[str, ...],
) -> dict:
    """Return SVG and a provenance manifest, not a financial or drawing approval.

    The source path must still resolve to identical SHA-256 bytes. The existing
    takeoff bridge also re-checks PDF vector evidence and CAD entity reviews.
    Every selected area must have exact geometry evidence and a known member.
    Empty/quantity-only selections fail closed for this *map-required* output.
    """
    project_id = _id(project_id, "شناسه پروژه")
    revision = _id(revision, "نسخه پروژه")
    if type(page) is not int or page < 1:
        raise ValueError("صفحه منبع باید صحیح و مثبت باشد")
    if not isinstance(selected_takeoff_ids, tuple) or not selected_takeoff_ids:
        raise ValueError("انتخاب صریح متره برای نقشه‌دار الزامی است")
    if len(selected_takeoff_ids) != len(set(selected_takeoff_ids)):
        raise ValueError("شناسه برداشت تکراری است")
    if len(selected_takeoff_ids) > 1000:
        raise ValueError("برای حفظ ظرفیت، خروجی را به صفحات کوچک‌تر تقسیم کنید")
    for identity in selected_takeoff_ids:
        _id(identity, "شناسه برداشت")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot نسخه‌دار نشست لازم است")
    session = DrawingTakeoffSession.from_dict(snapshot)
    source_file = Path(session.drawing_source)
    actual_sha = hashlib.sha256(source_file.read_bytes()).hexdigest() if source_file.is_file() else ""
    if not actual_sha or actual_sha != session.source_sha256:
        raise ValueError("SHA-256 منبع نقشه تغییر کرده یا فایل موجود نیست")
    if source_file.suffix.lower() not in (".pdf", ".dxf", ".dwg"):
        raise ValueError("برای خروجی دوبعدی نیاز به PDF/DXF/DWG معتبر است")
    rows = session_to_boq_rows(
        snapshot, session_id=session.drawing_source,
        selected_item_ids=selected_takeoff_ids,
    )
    if {row["takeoff_id"] for row in rows} != set(selected_takeoff_ids):
        raise ValueError("شناسه انتخاب با نشست ویرایش‌شده تطبیق ندارد")
    if any(row["page"] != page for row in rows):
        raise ValueError("یک گزارش نقشه‌دار نمی‌تواند صفحات متفاوت را بی‌نام ادغام کند")
    if any(row["kind"] != "area" or not row.get("geometry_evidence") for row in rows):
        raise ValueError("این خروجی به هندسه سطحی و مستند نیاز دارد؛ گزارش عددی جداگانه است")
    # Original bridge checks genuine source bytes, PDF page vectors and reviewed
    # CAD handles; this operation is read-only on a local copy of each row.
    verified_measurement_identities(
        {"session": snapshot, "source_sha256": actual_sha},
        rows,
    )
    shapes, all_points = [], []
    for row in rows:
        evidence = row["geometry_evidence"]
        for name in ("floor_id", "member_id", "quantity_owner"):
            _id(evidence.get(name), name)
        if row["cad_evidence"]:
            if (row["cad_evidence"].get("floor_id") != evidence["floor_id"] or
                row["cad_evidence"].get("member_id") != evidence["member_id"]):
                raise ValueError("هویت CAD و هندسه برداشت مغایرت دارد")
        outer, holes, _, _ = region(row["geometry"], row["holes"])
        # Read back the original canonical geometry; never infer missing holes.
        for ring in (outer, *holes):
            all_points.extend((_coordinate(x), _coordinate(y)) for x, y in ring)
        d = _path(outer) + "".join(" " + _path(h) for h in holes)
        shapes.append({
            "shape_id": "takeoff:" + row["takeoff_id"],
            "takeoff_id": row["takeoff_id"],
            "member_id": evidence["member_id"],
            "floor_id": evidence["floor_id"],
            "source_ref": row["source"],
            "page": page,
            "quantity": str(row["quantity"]),
            "unit": row["unit"],
            "boq_row_id": None,
            "review_status": "requires_project_boq_crosscheck",
            "_svg_path": d,
        })
    if not all_points:
        raise ValueError("هندسه مستند موجود نیست")
    with localcontext() as ctx:
        ctx.prec = 256
        xs, ys = zip(*all_points)
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if min_x == max_x or min_y == max_y:
            raise ValueError("محدوده نقشه غیرصفر الزامی است")
        pad = max(max_x-min_x, max_y-min_y) / Decimal(20)
        box = (
            min_x-pad, min_y-pad,
            max_x-min_x+2*pad, max_y-min_y+2*pad,
        )
    view_box = " ".join(format(v, "f") for v in box)
    paths = "".join(
        '<path fill="#dbeafe" fill-opacity="0.45" stroke="#1d4ed8" '
        'stroke-width="0.7%" fill-rule="evenodd" d="'
        + escape(shape["_svg_path"], quote=True) + '"><title>'
        + escape(shape["member_id"]) + '</title></path>'
        for shape in shapes
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="720" '
        'viewBox="' + view_box + '" role="img" aria-label="محدوده برداشت مستند">'
        '<title>محدوده‌های برداشت مستند، نه پلان کامل ساختمان</title>'
        + paths + '</svg>'
    )
    for shape in shapes:
        del shape["_svg_path"]
    manifest = {
        "schema": "structuralpro.phase7.source-backed-2d-overlay.v1",
        "project_id": project_id,
        "revision": revision,
        "source_sha256": actual_sha,
        "source_format": source_file.suffix.lower().lstrip("."),
        "page": page,
        "drawing_kind": "measured_region_overlay_not_complete_plan",
        "quantity_authority": False,
        "financial_mutation": False,
        "links": shapes,
        "svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
    }
    return {"svg": svg, "manifest": manifest}
