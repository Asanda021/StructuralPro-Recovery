"""Reviewed *candidate* geometry for connected, rectangular, planar sloping-fill zones.

Pure takeoff, independent from AEC/SQLite/BOQ and from Work's active surfaces.
All input is explicit, string-encoded decimal metres; no slopes or materials inferred.
All output quantities are non-payable exact decimal strings, pending integration.
"""
from __future__ import annotations

import re
from decimal import Decimal

from core.commercial.exact_values import exact
from core.takeoff.slope_linear_geometry import _overlap, _text
from core.commercial.statement_amendment import number

POLICY = "planar_connected_slope_geometry_v1"
HEAD_FIELDS = frozenset({
    "policy", "surface_id", "coordinate_frame_ref", "source_ref", "source_sha256",
    "approved_by", "material_ref", "coordinate_unit", "elevation_unit", "zones",
})
ZONE_FIELDS = frozenset({
    "region_id", "physical_key", "source_ref", "approved_by", "datum_ref",
    "x_m", "y_m", "length_m", "width_m", "base_elevation_m",
    "thickness_00_m", "thickness_10_m", "thickness_01_m", "openings",
})
OPENING_FIELDS = frozenset({
    "id", "physical_key", "source_ref", "x_m", "y_m", "length_m",
    "width_m", "penetration",
})
MAX_ZONES = 64
MAX_OPENINGS = 128


def _decimal(value, label, *, signed=False, positive=False):
    # A binary float may already have lost significant digits before arrival.
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{label}: مقدار باید متن اعشاری دقیق باشد؛ float مجاز نیست")
    val = number(value, label, negative=signed)
    if positive and val <= 0:
        raise ValueError(f"{label}: مقدار باید مثبت باشد")
    return val


def _wire(value: Decimal):
    return format(value, "f")


def _rectangle(x, y, length, width):
    return (x, y, x + length, y + width)


def _surface_height(zone, x, y):
    """Top elevation z(x,y) for an exact affine plane, absolute shared axes."""
    return (zone["datum"] + zone["t00"]
            + (zone["t10"] - zone["t00"]) * (x - zone["x"]) / zone["L"]
            + (zone["t01"] - zone["t00"]) * (y - zone["y"]) / zone["W"])


def _thickness(zone, x, y):
    return _surface_height(zone, x, y) - zone["datum"]


def _connection(a, b):
    """Return two endpoints along a positive-length shared edge, else None."""
    ax0, ay0, ax1, ay1 = a["box"]
    bx0, by0, bx1, by1 = b["box"]
    if ax1 == bx0 or bx1 == ax0:
        y0, y1 = max(ay0, by0), min(ay1, by1)
        if y0 < y1:
            x = ax1 if ax1 == bx0 else ax0
            return ((x, y0), (x, y1))
    if ay1 == by0 or by1 == ay0:
        x0, x1 = max(ax0, bx0), min(ax1, bx1)
        if x0 < x1:
            y = ay1 if ay1 == by0 else ay0
            return ((x0, y), (x1, y))
    return None


@exact
def calculate_planar_slope_zones(data: dict) -> dict:
    """Integrate one or several connected planar fill regions, with full-depth voids.

    Each zone has a horizontal, explicitly documented base_elevation_m and top
    thickness t00 at its lower-left corner, t10 at its lower-right corner,
    and t01 at its upper-left corner. The fourth thickness is constrained by
    affine planarity: t11=t10+t01-t00. All four must be nonnegative.

    Neighbouring regions with positive-length shared edges must have exactly
    equal *absolute finished top elevations* at both ends of the shared edge.
    Regions joined at a single point, disconnected regions, overlaps, notches,
    partial-depth openings and non-affine grading are outside this contract.
    """
    if not isinstance(data, dict) or set(data) != HEAD_FIELDS:
        raise ValueError("قرارداد چندناحیه‌ای: کلیدهای صریح و نسخه‌دار لازم‌اند")
    if data["policy"] != POLICY:
        raise ValueError("نسخه قرارداد شیب‌بندی نامعتبر است")
    for k in ("surface_id", "coordinate_frame_ref", "source_ref", "approved_by", "material_ref"):
        _text(data[k], k)
    digest = _text(data["source_sha256"], "SHA-256 اظهارشده منبع")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise ValueError("اثر انگشت مرجع باید SHA-256 شصت‌وچهاررقمی باشد")
    if data["coordinate_unit"] != "m" or data["elevation_unit"] != "m":
        raise ValueError("واحدهای طول و تراز باید صریحاً متر باشند؛ تبدیل ضمنی ممنوع است")
    raw_zones = data["zones"]
    if not isinstance(raw_zones, list) or not (1 <= len(raw_zones) <= MAX_ZONES):
        raise ValueError("حداقل یک و حداکثر ۶۴ ناحیه الزامی است")

    zones = []
    ids, physical, sources = set(), set(), {data["source_ref"]}
    number_of_openings = 0
    for item in raw_zones:
        if not isinstance(item, dict) or set(item) != ZONE_FIELDS:
            raise ValueError("فیلدهای ناحیه شیب‌بندی باید کامل و مشخص باشند")
        rid = _text(item["region_id"], "شناسه ناحیه")
        pk = _text(item["physical_key"], "هویت فیزیکی ناحیه")
        source = _text(item["source_ref"], "منبع اختصاصی ناحیه")
        _text(item["approved_by"], "تأییدکننده اظهارشده")
        _text(item["datum_ref"], "مرجع تراز زیرکار")
        if rid in ids or pk in physical or source in sources:
            raise ValueError("هویت یا منبع ناحیه تکراری است")
        ids.add(rid)
        physical.add(pk)
        sources.add(source)
        x = _decimal(item["x_m"], "موقعیت افقی", signed=True)
        y = _decimal(item["y_m"], "موقعیت عمودی", signed=True)
        L = _decimal(item["length_m"], "طول ناحیه", positive=True)
        W = _decimal(item["width_m"], "عرض ناحیه", positive=True)
        datum = _decimal(item["base_elevation_m"], "تراز کف مبنا", signed=True)
        t00 = _decimal(item["thickness_00_m"], "ضخامت گوشه مبنا")
        t10 = _decimal(item["thickness_10_m"], "ضخامت گوشه راست")
        t01 = _decimal(item["thickness_01_m"], "ضخامت گوشه بالا")
        t11 = t10 + t01 - t00
        if t11 < 0 or max(t00, t10, t01, t11) <= 0:
            raise ValueError("صفحه شیب دارای ضخامت منفی یا سراسر صفر است")
        raw_openings = item["openings"]
        if not isinstance(raw_openings, list):
            raise ValueError("بازشوهای ناحیه باید فهرست باشند")
        number_of_openings += len(raw_openings)
        if number_of_openings > MAX_OPENINGS:
            raise ValueError("تعداد بازشوهای پروژه از سقف مجاز بیشتر است")
        zone = dict(region_id=rid, physical_key=pk, source_ref=source,
                    approved_by=item["approved_by"], datum_ref=item["datum_ref"],
                    x=x, y=y, L=L, W=W, datum=datum,
                    t00=t00, t10=t10, t01=t01, t11=t11,
                    box=_rectangle(x, y, L, W))
        # Physical regions must not overlap even when the input contains new ids.
        if any(_overlap(zone["box"], other["box"]) for other in zones):
            raise ValueError("دو ناحیه فیزیکی شیب‌بندی با یکدیگر تداخل دارند")
        zone["raw_openings"] = raw_openings
        zones.append(zone)

    connections = []
    adjacency = {z["region_id"]: set() for z in zones}
    for i, a in enumerate(zones):
        for b in zones[i+1:]:
            edge = _connection(a, b)
            if edge is None:
                continue
            # An affine function on an edge is identical if both endpoint
            # values match. No approximate tolerance or elevation rounding.
            if any(_surface_height(a, *point) != _surface_height(b, *point)
                   for point in edge):
                raise ValueError("تراز رویه دو ناحیه مجاور ناپیوسته است")
            adjacency[a["region_id"]].add(b["region_id"])
            adjacency[b["region_id"]].add(a["region_id"])
            connections.append({
                "first_region": a["region_id"],
                "second_region": b["region_id"],
                "segment_m": [[_wire(x), _wire(y)] for x, y in edge],
                "verified": True,
            })
    reached = set()
    frontier = [zones[0]["region_id"]]
    while frontier:
        current = frontier.pop()
        if current in reached:
            continue
        reached.add(current)
        frontier.extend(adjacency[current] - reached)
    if len(reached) != len(zones):
        raise ValueError("همه نواحی این قرارداد باید با ضلع مشترک به هم متصل باشند")

    outputs = []
    total_area = total_deducted_area = Decimal(0)
    total_gross = total_removed = Decimal(0)
    for z in zones:
        void_boxes = []
        void_rows = []
        removed_area = removed_volume = Decimal(0)
        for opening in z["raw_openings"]:
            if not isinstance(opening, dict) or set(opening) != OPENING_FIELDS:
                raise ValueError("کلیدهای بازشو مستند و نسخه‌دار نیستند")
            oid = _text(opening["id"], "شناسه بازشو")
            pk = _text(opening["physical_key"], "شناسه فیزیکی بازشو")
            s = _text(opening["source_ref"], "منبع بازشو")
            if oid in ids or pk in physical or s in sources:
                raise ValueError("شناسه فیزیکی یا مرجع بازشو در سطح تکراری است")
            ids.add(oid)
            physical.add(pk)
            sources.add(s)
            if opening["penetration"] != "full_depth":
                raise ValueError("فقط بازشوی نافذ تمام ضخامت پذیرفته است")
            x = _decimal(opening["x_m"], "مختصات بازشو", signed=True)
            y = _decimal(opening["y_m"], "مختصات بازشو", signed=True)
            L = _decimal(opening["length_m"], "طول بازشو", positive=True)
            W = _decimal(opening["width_m"], "عرض بازشو", positive=True)
            box = _rectangle(x, y, L, W)
            if not (z["x"] <= x and z["y"] <= y
                    and box[2] <= z["x"]+z["L"]
                    and box[3] <= z["y"]+z["W"]):
                raise ValueError("بازشو باید درون ناحیه بدون برش مرزی قرار داشته باشد")
            if any(_overlap(box, old) for old in void_boxes):
                raise ValueError("بازشوهای دارای هم‌پوشانی دوبار کسر نمی‌شوند")
            void_boxes.append(box)
            area = L * W
            thickness_center = _thickness(z, x + L/2, y + W/2)
            volume = area * thickness_center
            removed_area += area
            removed_volume += volume
            void_rows.append(dict(id=oid, physical_key=pk, source_ref=s,
                                  area_m2=_wire(area), deducted_volume_m3=_wire(volume),
                                  formula="opening_area * affine_thickness_at_opening_centroid"))
        gross_area = z["L"] * z["W"]
        gross = gross_area * (z["t00"] + z["t10"] + z["t01"] + z["t11"]) / 4
        net_area = gross_area - removed_area
        net_volume = gross - removed_volume
        if net_area <= 0 or net_volume <= 0:
            raise ValueError("سطح یا حجم خالص ناحیه مثبت نیست")
        total_area += gross_area
        total_deducted_area += removed_area
        total_gross += gross
        total_removed += removed_volume
        outputs.append({
            "region_id": z["region_id"], "physical_key": z["physical_key"],
            "source_ref": z["source_ref"], "approved_by": z["approved_by"],
            "datum_ref": z["datum_ref"], "base_elevation_m": _wire(z["datum"]),
            "corner_thickness_m": {key: _wire(z[key]) for key in ("t00", "t10", "t01", "t11")},
            "gross_area_m2": _wire(gross_area), "deducted_area_m2": _wire(removed_area),
            "net_area_m2": _wire(net_area), "gross_volume_m3": _wire(gross),
            "deducted_volume_m3": _wire(removed_volume), "net_volume_m3": _wire(net_volume),
            "openings": void_rows,
            "formula": "integral_rectangle(t00+dx*(x-x0)/L+dy*(y-y0)/W) minus full_depth_openings",
        })
    return {
        "policy": POLICY, "surface_id": data["surface_id"],
        "coordinate_frame_ref": data["coordinate_frame_ref"],
        "source_ref": data["source_ref"], "source_sha256_claim": digest.lower(),
        "source_sha256_verified": False, "approved_by": data["approved_by"],
        "material_ref": data["material_ref"], "zone_count": len(zones),
        "measurement_unit": "m3",
        "gross_area_m2": _wire(total_area),
        "deducted_area_m2": _wire(total_deducted_area),
        "net_area_m2": _wire(total_area - total_deducted_area),
        "gross_volume_m3": _wire(total_gross),
        "deducted_volume_m3": _wire(total_removed),
        "net_volume_m3": _wire(total_gross - total_removed),
        "zones": outputs, "verified_shared_edges": connections,
        "boq_ready": False, "purchase_quantity": None,
        "payment_role": "unreviewed_geometry_only",
        "acceptance": "synthetic_geometry_only",
    }
