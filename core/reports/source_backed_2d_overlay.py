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
        # A visible label for the exported image; source geometry owns no new QTO.
        with localcontext() as label_ctx:
            label_ctx.prec = 80
            outer_x = [_coordinate(x) for x, _ in outer]
            outer_y = [_coordinate(y) for _, y in outer]
            label_x = (min(outer_x) + max(outer_x)) / 2
            label_y = (min(outer_y) + max(outer_y)) / 2
            label_size = max(max(outer_x)-min(outer_x), max(outer_y)-min(outer_y), Decimal("1")) / 22
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
            "_label_x": format(label_x, "f"),
            "_label_y": format(label_y, "f"),
            "_label_size": format(label_size, "f"),
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
        + '<text text-anchor="middle" font-weight="bold" fill="#17263b" x="'
        + shape["_label_x"] + '" y="' + shape["_label_y"]
        + '" font-size="' + shape["_label_size"] + '">'
        + escape(shape["member_id"]) + '</text>'
        for shape in shapes
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="720" '
        'viewBox="' + view_box + '" role="img" aria-label="محدوده برداشت مستند">'
        '<title>محدوده‌های برداشت مستند، نه پلان کامل ساختمان</title>'
        + paths + '</svg>'
    )
    for shape in shapes:
        for private_key in ("_svg_path", "_label_x", "_label_y", "_label_size"):
            del shape[private_key]
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


def link_source_backed_2d_overlay_to_boq(
    project_snapshot: dict, *, session_id: str,
    expected_project_version: int, expected_session_revision: int,
    revision: str, page: int, selected_takeoff_ids: tuple[str, ...],
) -> dict:
    """Bind source-verified 2D shapes to real, unambiguous persisted BOQ rows.

    Read-only acceptance adapter: the caller must supply one current project
    snapshot from the existing ProjectStore, with exact project/session versions.
    Aggregated/multi-source BOQ entries are deliberately NOT auto-distributed:
    attribution of a whole aggregate to one shape would be false. The output
    never grants independent quantity, pricing or engineering-approval rights.
    """
    if not isinstance(project_snapshot, dict):
        raise ValueError("snapshot معتبر پروژه الزامی است")
    pid = _id(project_snapshot.get("id"), "شناسه پروژه")
    sid = _id(session_id, "شناسه نشست")
    meta = project_snapshot.get("_meta")
    if not isinstance(meta, dict):
        raise ValueError("متاداده نسخه واقعی پروژه موجود نیست")
    observed_version = meta.get("version")
    if (type(expected_project_version) is not int or
        type(observed_version) is not int or
        expected_project_version != observed_version):
        raise ValueError("نسخه پروژه با snapshot جاری تطبیق ندارد")
    sessions = project_snapshot.get("drawing_sessions")
    if not isinstance(sessions, dict) or not isinstance(sessions.get(sid), dict):
        raise ValueError("نشست متره در snapshot واقعی پروژه وجود ندارد")
    record = sessions[sid]
    if (type(expected_session_revision) is not int or
        type(record.get("revision")) is not int or
        expected_session_revision != record["revision"]):
        raise ValueError("نسخه نشست متره تغییر کرده است")
    session = record.get("session")
    if not isinstance(session, dict):
        raise ValueError("داده نشست ثبت‌شده نامعتبر است")
    if (record.get("id") != sid or
        record.get("drawing_source") != session.get("drawing_source") or
        record.get("source_sha256") != session.get("source_sha256")):
        raise ValueError("رسید نشست و منشأ نقشه همخوان نیست")
    committed = record.get("committed_item_ids")
    if not isinstance(committed, list) or not all(
        isinstance(x, str) for x in committed
    ) or not set(selected_takeoff_ids).issubset(set(committed)):
        raise ValueError("برداشت هنوز در BOQ ثبت و تأیید انتقال نشده است")

    overlay = build_source_backed_2d_overlay(
        session, project_id=pid, revision=revision, page=page,
        selected_takeoff_ids=selected_takeoff_ids,
    )
    rows = session_to_boq_rows(
        session, session_id=sid, selected_item_ids=selected_takeoff_ids,
    )
    verified_measurement_identities(record, rows)
    source_to_row = {}
    for row in rows:
        source_id = row["source_id"]
        if source_id in source_to_row:
            raise ValueError("رسید منبع برداشت تکراری است")
        source_to_row[source_id] = row

    takeoffs = project_snapshot.get("takeoffs")
    boq_rows = project_snapshot.get("boq")
    if not isinstance(takeoffs, list) or not isinstance(boq_rows, list):
        raise ValueError("ریز متره یا BOQ واقعی پروژه موجود نیست")
    result = []
    used_boq_numbers = set()
    seen_sources = set()
    for shape in overlay["manifest"]["links"]:
        item_id = shape["takeoff_id"]
        source_id = f"drawing:{sid}:{item_id}"
        row = source_to_row.get(source_id)
        if row is None or source_id in seen_sources:
            raise ValueError("پیوند برداشت و رسید منبع یکتا نیست")
        seen_sources.add(source_id)

        matched_takeoffs = [t for t in takeoffs if isinstance(t, dict) and t.get("source_id") == source_id]
        if len(matched_takeoffs) != 1:
            raise ValueError("ریز متره ثبت‌شده با منبع یکتا یافت نشد")
        takeoff = matched_takeoffs[0]
        params = takeoff.get("params")
        provenance = takeoff.get("provenance")
        quantities = takeoff.get("quantities")
        if (takeoff.get("domain") != "drawing" or
            takeoff.get("drawing_session_id") != sid or
            takeoff.get("drawing_takeoff_id") != item_id or
            not isinstance(params, dict) or
            not isinstance(provenance, dict) or
            not isinstance(quantities, list) or len(quantities) != 1):
            raise ValueError("ثبت واقعی ریزمتره با نشست اصلی مطابق نیست")
        for receipt in (params, provenance):
            if (receipt.get("drawing_session_id") != sid or
                receipt.get("source_sha256") != overlay["manifest"]["source_sha256"] or
                receipt.get("measurement_identity") != row.get("measurement_identity") or
                receipt.get("geometry_evidence") != row["geometry_evidence"] or
                receipt.get("page") != page):
                raise ValueError("هویت هندسه و رسید ثبت‌شده متره ناسازگار است")
        if (params.get("geometry") != row["geometry"] or
            params.get("holes") != row["holes"]):
            raise ValueError("مختصات یا کسورات ثبت‌شده با نقشه مطابق نیست")
        q = quantities[0]
        if (q.get("code") != row["item_code"] or
            q.get("unit") != row["unit"] or
            q.get("source_ref") != row["source"] or
            decimal_value(q.get("amount"), field="takeoff quantity") !=
            decimal_value(row["quantity"], field="source quantity")):
            raise ValueError("کمیت/واحد ریزمتره با مدرک برداشت متفاوت است")

        source_boq = [b for b in boq_rows if isinstance(b, dict) and
            source_id in (b.get("source_ids") or [b.get("source_id")])]
        if len(source_boq) != 1:
            raise ValueError("ردیف BOQ متناظر با منبع یکتا یافت نشد")
        boq = source_boq[0]
        source_ids = boq.get("source_ids") or [boq.get("source_id")]
        if (source_ids != [source_id] or
            boq.get("status", "active") != "active" or
            boq.get("item_code") != row["item_code"] or
            boq.get("unit") != row["unit"] or
            decimal_value(boq.get("quantity"), field="BOQ quantity") !=
            decimal_value(row["quantity"], field="source quantity")):
            raise ValueError("BOQ تجمیعی، غیرفعال یا ناسازگار است؛ انتساب خودکار مجاز نیست")
        item_no = boq.get("item_no")
        if (type(item_no) is not int or item_no <= 0 or
            item_no in used_boq_numbers):
            raise ValueError("شماره BOQ غیرقابل ردیابی یا تکراری است")
        used_boq_numbers.add(item_no)

        floor_id, member_id = shape["floor_id"], shape["member_id"]
        floors = project_snapshot.get("floors")
        members = project_snapshot.get("members")
        if (not isinstance(floors, list) or not isinstance(members, list) or
            not any(isinstance(f, dict) and f.get("id") == floor_id for f in floors) or
            not any(isinstance(m, dict) and m.get("id") == member_id and
                m.get("floor_id") == floor_id for m in members)):
            raise ValueError("عضو یا طبقه در پروژه ثبت‌شده وجود ندارد")
        result.append({
            **shape,
            "source_id": source_id,
            "boq_row_id": f"boq-item-no:{item_no}",
            "takeoff_record_id": _id(takeoff.get("id"), "شناسه ریزمتره"),
            "measurement_identity": row["measurement_identity"],
            "review_status": "persisted_boq_source_verified_not_engineering_approval",
        })

    manifest = dict(overlay["manifest"])
    manifest["links"] = result
    manifest["project_version"] = observed_version
    manifest["session_id"] = sid
    manifest["session_revision"] = record["revision"]
    manifest["boq_reference_scope"] = "one_source_per_row_only"
    manifest["quantity_authority"] = False
    manifest["financial_mutation"] = False
    return {"svg": overlay["svg"], "manifest": manifest}
