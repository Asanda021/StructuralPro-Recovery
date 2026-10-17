"""Standalone, reviewed *takeoff* contract for rectangular RC shear-wall parts.

No design inference, project writes, pricing, BoQ commits or automatic approvals.
This file is additive: integrating it with StructuralPro requires a separate review.
"""
from __future__ import annotations

from decimal import Decimal, DecimalException, Inexact, InvalidOperation, Rounded, localcontext
from hashlib import sha256
import json
import unicodedata
from typing import Any

SCHEMA = "shear_wall_specialist_chat_v1"
BAR_GROUPS = (
    "vertical", "horizontal", "boundary_longitudinal", "boundary_ties",
    "crossties", "opening_reinforcement", "starters_connections",
)
PART_KINDS = {"straight", "bend", "hook", "lap", "anchorage", "other"}
FACE_SIDES = {"front", "back"}
EDGE_KINDS = {"left_end", "right_end", "top", "bottom", "opening_jamb"}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
ZERO = Decimal("0")


class ShearWallValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise ShearWallValidationError(code, message)


def record(value: Any, required: set[str], optional: set[str] | None = None, *, label: str) -> dict:
    if not isinstance(value, dict):
        fail("SCHEMA", f"{label}: ساختار دیکشنری لازم است")
    missing = required - value.keys()
    extra = value.keys() - required - (optional or set())
    if missing or extra:
        fail("SCHEMA", f"{label}: کلیدهای نامعتبر/ناقص: missing={sorted(missing)}, extra={sorted(extra)}")
    return value


def sequence(value: Any, *, label: str, nonempty: bool = False) -> list:
    if not isinstance(value, list) or (nonempty and not value):
        fail("SCHEMA", f"{label}: فهرست معتبر لازم است")
    return value


def ident(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail("SOURCE", f"{label}: شناسه یا مرجع خالی است")
    return unicodedata.normalize("NFKC", " ".join(value.translate(_DIGITS).casefold().split()))


def nonblank(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail("SOURCE", f"{label}: مرجع/تأییدکننده لازم است")
    return value.strip()


def decimal(value: Any, label: str, *, positive: bool = False, nonnegative: bool = False, integer: bool = False) -> Decimal:
    # Floats are deliberately rejected: Decimal(float) loses original evidence.
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        fail("DECIMAL", f"{label}: تنها مقدار متنی دهدهی، Decimal یا عدد صحیح مجاز است")
    if isinstance(value, str) and (not value.strip() or value != value.strip()):
        fail("DECIMAL", f"{label}: مقدار عددی باید صریح باشد")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        fail("DECIMAL", f"{label}: عدد دهدهی نامعتبر است")
    if not d.is_finite():
        fail("DECIMAL", f"{label}: NaN و بی‌نهایت مردود است")
    # Bound number scale and precision; never round an engineering quantity silently.
    if len(d.as_tuple().digits) > 30 or d.adjusted() > 14 or d.as_tuple().exponent < -18:
        fail("PRECISION", f"{label}: خارج از قرارداد دقت (۳۰ رقم، ۱۸ رقم اعشار، ۱۵ رقم صحیح)")
    if positive and d <= ZERO or nonnegative and d < ZERO:
        fail("GEOMETRY", f"{label}: مقدار مثبت/نامنفی لازم است")
    if integer and (d != d.to_integral_value() or d <= ZERO):
        fail("DECIMAL", f"{label}: مقدار صحیح مثبت لازم است")
    return d


def ds(d: Decimal) -> str:
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def audited(value: dict, name: str) -> None:
    nonblank(value.get("source_ref"), label=f"مرجع {name}")
    nonblank(value.get("approved_by"), label=f"تأییدکننده {name}")


def unique(value: Any, seen: set, label: str) -> str:
    key = ident(value, label=label)
    if key in seen:
        fail("DUPLICATE", f"{label}: شناسه تکراری {value}")
    seen.add(key)
    return key


def rect(x: Decimal, z: Decimal, width: Decimal, height: Decimal):
    return x, z, x + width, z + height


def overlap(a, b) -> Decimal:
    return max(ZERO, min(a[2], b[2]) - max(a[0], b[0])) * max(ZERO, min(a[3], b[3]) - max(a[1], b[1]))


def contains(outer, inner) -> bool:
    return outer[0] <= inner[0] < inner[2] <= outer[2] and outer[1] <= inner[1] < inner[3] <= outer[3]


def reviewed_box(p: dict, *, label: str, prefix: str = ""):
    x = decimal(p[prefix + "x_m"], f"{label} x", nonnegative=True)
    z = decimal(p[prefix + "z_m"], f"{label} z", nonnegative=True)
    w = decimal(p[prefix + "width_m"], f"{label} width", positive=True)
    h = decimal(p[prefix + "height_m"], f"{label} height", positive=True)
    return rect(x, z, w, h)


def _format_row(kind: str, physical: str, qty: Decimal, unit: str, expression: str, refs: list[str], **extras) -> dict:
    return {"kind": kind, "physical_id": physical, "quantity": ds(qty), "unit": unit,
            "formula": expression, "source_refs": refs, **extras}


def _bar_length(bar: dict) -> tuple[Decimal, str]:
    direct = "cut_length_m" in bar
    parts = "cut_parts" in bar
    if direct == parts:
        fail("REBAR_DETAIL", "طول برش باید دقیقاً یکی از روش‌های مستقیم یا جزءبه‌جزء باشد")
    if direct:
        return decimal(bar["cut_length_m"], "طول برش", positive=True), "طول برش مصوب"
    items = sequence(bar["cut_parts"], label="اجزای برش", nonempty=True)
    total = ZERO
    straight = False
    for item in items:
        record(item, {"kind", "length_m", "source_ref", "approved_by"}, label="جزء طول برش")
        if item["kind"] not in PART_KINDS:
            fail("REBAR_DETAIL", "نوع خم، قلاب، مهاری، وصله یا قطعه نامعتبر است")
        audited(item, "جزء برش")
        if item["kind"] == "straight":
            straight = True
        total += decimal(item["length_m"], "طول جزء برش", positive=True)
    if not straight:
        fail("REBAR_DETAIL", "طول مستقیم مستند برای سری میلگرد لازم است")
    return total, "Σ طول مستقیم، خم، قلاب، مهاری و وصله مستند"


def preview(data: dict, *, existing_claims: set[str] | None = None) -> dict:
    """Fail-closed pure preview; all quantities are exact decimal strings.

    ``existing_claims`` is supplied by a future existing-ledger adapter, not queried
    or guessed here. This cannot establish project-wide uniqueness on its own.
    """
    with localcontext() as ctx:
        ctx.prec = 160
        ctx.traps[Inexact] = True
        ctx.traps[Rounded] = True
        try:
            return _preview(data, existing_claims=existing_claims)
        except DecimalException as exc:
            fail("PRECISION", "دقت محاسبه دقیق از دامنه قرارداد خارج است: " + type(exc).__name__)


def _preview(data: dict, *, existing_claims: set[str] | None) -> dict:
    record(data, {"schema_version", "kind", "project_id", "floor_id", "wall_id", "physical_wall_id", "source", "datum", "segments", "openings", "interfaces", "formwork", "rebars"}, label="داده دیوار برشی")
    if data["schema_version"] != SCHEMA or data["kind"] != "shear_wall":
        fail("POLICY", "قرارداد یا نوع عضو نادرست است")
    project = ident(data["project_id"], label="پروژه")
    floor = ident(data["floor_id"], label="طبقه")
    wall = ident(data["wall_id"], label="دیوار")
    physical_wall = ident(data["physical_wall_id"], label="هویت فیزیکی دیوار")
    source = record(data["source"], {"mode", "source_id", "source_ref", "approved_by", "length_unit"}, label="منبع")
    if source["mode"] != "manual" or source["length_unit"] != "m":
        fail("UNSUPPORTED", "برداشت نقشه یا واحد غیر از متر نیازمند قرارداد مستقل و اعتبارسنجی فایل است")
    audited(source, "منبع")
    ident(source["source_id"], label="شناسه منبع")
    datum = record(data["datum"], {"coordinate_ref", "axis_ref", "level_ref", "orientation", "approved_by"}, label="محور و تراز")
    for f in ("coordinate_ref", "axis_ref", "level_ref", "approved_by"):
        nonblank(datum[f], label=f)
    if datum["orientation"] not in ("positive_x", "negative_x"):
        fail("DATUM", "جهت مستند محلی باید مشخص باشد")
    if existing_claims is not None and not isinstance(existing_claims, set):
        fail("SCHEMA", "دفتر ادعاهای فیزیکی باید مجموعه باشد")
    used_claims = set()
    def claim(typ: str, value: Any) -> str:
        key = ":".join((project, floor, typ, ident(value, label=typ)))
        if key in used_claims or (existing_claims is not None and key in existing_claims):
            fail("DUPLICATE", f"هویت فیزیکی قبلاً ادعا شده است: {key}")
        used_claims.add(key)
        return key
    claim("wall", physical_wall)
    claim("source", source["source_id"])

    segments = {}
    seen = set()
    results = []
    gross_total = ZERO
    for seg in sequence(data["segments"], label="قطعات", nonempty=True):
        record(seg, {"id", "physical_part_id", "x_m", "z_m", "y_m", "length_m", "height_m", "thickness_m", "source_ref", "approved_by"}, label="قطعه مستطیلی دیوار")
        sid = unique(seg["id"], seen, "شناسه قطعه")
        claim("part", seg["physical_part_id"])
        audited(seg, "هندسه قطعه")
        p = rect(decimal(seg["x_m"], "x قطعه", nonnegative=True), decimal(seg["z_m"], "z قطعه", nonnegative=True),
                 decimal(seg["length_m"], "طول قطعه", positive=True), decimal(seg["height_m"], "ارتفاع قطعه", positive=True))
        y = decimal(seg["y_m"], "موقعیت عرضی قطعه", nonnegative=True)
        thick = decimal(seg["thickness_m"], "ضخامت قطعه", positive=True)
        for other in segments.values():
            if overlap(p, other["rect"]) > 0:
                fail("OVERLAP", "قطعات دیوار در صفحه x-z هم‌پوشانی حجمی یا جانمایی مبهم دارند")
        gross = (p[2] - p[0]) * (p[3] - p[1]) * thick
        segments[sid] = {"rect": p, "y": y, "thickness": thick, "gross": gross, "segment": seg, "opening_m3": ZERO, "interface_m3": ZERO, "openings": [], "interfaces": []}
        gross_total += gross
        results.append(_format_row("concrete_gross", sid, gross, "m3", "L×H×t", [seg["source_ref"]], segment_id=sid))

    opening_total = ZERO
    opening_ids = set()
    for op in sequence(data["openings"], label="بازشوها"):
        record(op, {"id", "segment_id", "x_m", "z_m", "width_m", "height_m", "source_ref", "approved_by"}, label="بازشو")
        oid = unique(op["id"], opening_ids, "شناسه بازشو")
        sid = ident(op["segment_id"], label="شناسه قطعه بازشو")
        if sid not in segments:
            fail("GEOMETRY", "بازشو به قطعه ناموجود اشاره دارد")
        audited(op, "بازشو")
        op_rect = reviewed_box(op, label="بازشو")
        if not contains(segments[sid]["rect"], op_rect):
            fail("OPENING", "بازشو باید کامل در یک قطعه مستند قرار داشته باشد")
        if any(overlap(op_rect, prior["rect"]) > 0 for prior in segments[sid]["openings"]):
            fail("OPENING", "بازشوهای مشترک هم‌پوشانی دارند")
        seg = segments[sid]
        v = (op_rect[2] - op_rect[0]) * (op_rect[3] - op_rect[1]) * seg["thickness"]
        seg["openings"].append({"id": oid, "rect": op_rect})
        seg["opening_m3"] += v
        opening_total += v
        results.append(_format_row("concrete_opening_deduction", oid, -v, "m3", "-w×h×t قطعه", [op["source_ref"]], segment_id=sid))

    interfaces = set()
    iface_total = ZERO
    for inter in sequence(data["interfaces"], label="اشتراک سازه‌ای"):
        record(inter, {"id", "segment_id", "foreign_member_id", "x_m", "y_m", "z_m", "width_m", "depth_m", "height_m", "deduction_owner", "common_datum_ref", "source_ref", "approved_by"}, label="اشتراک با عضو خارجی")
        iid = unique(inter["id"], interfaces, "شناسه اشتراک")
        sid = ident(inter["segment_id"], label="شناسه قطعه مشترک")
        if sid not in segments:
            fail("GEOMETRY", "قطعه اشتراک موجود نیست")
        audited(inter, "هندسه اشتراک سازه‌ای")
        foreign = ident(inter["foreign_member_id"], label="عضو متقاطع")
        if foreign in {wall, physical_wall}:
            fail("OWNERSHIP", "عضو خارجی نمی‌تواند خود دیوار باشد")
        if nonblank(inter["common_datum_ref"], label="مرجع دستگاه مشترک") != datum["coordinate_ref"]:
            fail("DATUM", "اشتراک باید دارای دستگاه مختصات یکسان با دیوار باشد")
        if inter["deduction_owner"] != "shear_wall":
            fail("OWNERSHIP", "مسئول کسر حجم در این قرارداد باید صریحاً دیوار برشی باشد")
        r = reviewed_box(inter, label="اشتراک")
        yi = decimal(inter["y_m"], "y اشتراک", nonnegative=True)
        dep = decimal(inter["depth_m"], "عمق اشتراک", positive=True)
        seg = segments[sid]
        if not contains(seg["rect"], r) or yi < seg["y"] or yi + dep > seg["y"] + seg["thickness"]:
            fail("INTERFACE", "منشور اشتراک باید در هندسه قطعه مستند واقع شود")
        if any(overlap(r, op["rect"]) > 0 for op in seg["openings"]):
            fail("INTERFACE", "اشتراک و بازشو روی یک حجم تداخل دارند")
        if any(overlap(r, prior["rect"]) > 0 and min(yi+dep, prior["ymax"])>max(yi,prior["ymin"]) for prior in seg["interfaces"]):
            fail("INTERFACE", "دو اشتراک به یک حجم برخورد کرده‌اند")
        v = (r[2]-r[0]) * (r[3]-r[1]) * dep
        seg["interfaces"].append({"id":iid,"rect":r,"ymin":yi,"ymax":yi+dep})
        seg["interface_m3"] += v
        iface_total += v
        results.append(_format_row("concrete_interface_deduction", iid, -v, "m3", "-w×h×عمق منشور اشتراک", [inter["source_ref"], inter["common_datum_ref"]], foreign_member_id=inter["foreign_member_id"], segment_id=sid))

    net_total = ZERO
    for sid, seg in segments.items():
        net = seg["gross"] - seg["opening_m3"] - seg["interface_m3"]
        if net <= 0:
            fail("GEOMETRY", "حجم خالص قطعه بعد از کسورات باید مثبت باشد")
        net_total += net
        results.append(_format_row("concrete_net", sid, net, "m3", "L×H×t−Σبازشو−Σاشتراک", [seg["segment"]["source_ref"]], segment_id=sid))

    fw = record(data["formwork"], {"status", "source_ref", "approved_by", "payment_scope_ref", "payment_approved_by", "main_faces", "edge_faces", "edge_scope"}, label="قالب‌بندی")
    if fw["status"] != "confirmed":
        fail("UNREVIEWED", "قالب‌بندی باید کامل بازبینی شود")
    audited(fw, "قالب‌بندی")
    nonblank(fw["payment_scope_ref"], label="مرجع قرارداد پرداخت قالب")
    nonblank(fw["payment_approved_by"], label="بازبین قرارداد پرداخت قالب")
    side_scope = record(fw["edge_scope"], {"status", "source_ref", "approved_by"}, label="دامنه وجوه جانبی")
    if side_scope["status"] != "reviewed_complete":
        fail("UNREVIEWED", "دامنه وجوه کناری و بازشوها نامشخص است")
    audited(side_scope, "دامنه وجوه جانبی")
    faces = {}
    face_seen = set()
    gross_main_area = ZERO
    payable_main = ZERO
    for face in sequence(fw["main_faces"], label="دو وجه اصلی", nonempty=True):
        record(face, {"id", "segment_id", "side", "status", "source_ref", "approved_by", "payment_ref", "contact_rectangles"}, {"reason"}, label="وجه قالب")
        fid = unique(face["id"], face_seen, "شناسه سطح")
        sid = ident(face["segment_id"], label="شناسه قطعه سطح")
        if sid not in segments or face["side"] not in FACE_SIDES:
            fail("FORMWORK", "سطح اصلی یا سمت آن نامعتبر است")
        key = (sid, face["side"])
        if key in faces:
            fail("DUPLICATE", "برای هر قطعه فقط یک تعریف کامل از وجه جلو و پشت مجاز است")
        audited(face, "وجه قالب")
        nonblank(face["payment_ref"], label="مرجع مبلغ قابل پرداخت یا عدم نیاز")
        if face["status"] not in ("formed", "not_required"):
            fail("UNREVIEWED", "وضعیت اجرای قالب باید صریح باشد")
        if face["status"] == "not_required":
            nonblank(face.get("reason"), label="علت عدم نیاز قالب")
        seg = segments[sid]
        base = (seg["rect"][2] - seg["rect"][0]) * (seg["rect"][3] - seg["rect"][1])
        op_area = sum(((o["rect"][2]-o["rect"][0]) * (o["rect"][3]-o["rect"][1]) for o in seg["openings"]), ZERO)
        area = base - op_area
        gross_main_area += area
        prior_contacts = []
        contact_total = ZERO
        seen_contacts = set()
        for contact in sequence(face["contact_rectangles"], label="سطح تماس"):
            record(contact, {"id", "x_m", "z_m", "width_m", "height_m", "source_ref", "approved_by"}, label="سطح تماس")
            unique(contact["id"], seen_contacts, "شناسه تماس")
            audited(contact, "تماس")
            c = reviewed_box(contact, label="سطح تماس")
            if not contains(seg["rect"], c) or any(overlap(c, op["rect"]) > 0 for op in seg["openings"]):
                fail("FORMWORK", "سطح تماس خارج از وجه یا روی بازشو است")
            if any(overlap(c, old) > 0 for old in prior_contacts):
                fail("FORMWORK", "سطوح تماس روی هم افتاده‌اند")
            prior_contacts.append(c)
            contact_total += (c[2]-c[0]) * (c[3]-c[1])
        if contact_total > area:
            fail("FORMWORK", "کسورات قالب از سطح موجود بیشتر است")
        # A verified foreign interface touching a formed face needs an explicit
        # same-rectangle contact exclusion: never leave payable duplicated area.
        surface_y = seg["y"] if face["side"] == "front" else seg["y"] + seg["thickness"]
        for inter in seg["interfaces"]:
            touches = (inter["ymin"] == surface_y if face["side"] == "front" else inter["ymax"] == surface_y)
            if touches and inter["rect"] not in prior_contacts:
                fail("FORMWORK", "سطح تماس اشتراکِ متصل به وجه باید با هندسه همان اشتراک کسر شود")
        eligible = area - contact_total
        formed = eligible if face["status"] == "formed" else ZERO
        if face["status"] == "formed" and formed <= ZERO:
            fail("FORMWORK", "وجهی که به عنوان قالب لازم ثبت شده باید سطح مثبت قابل پرداخت داشته باشد")
        faces[key] = fid
        payable_main += formed
        results.append(_format_row("formwork_main", fid, formed, "m2", "(L×H−بازشو−تماس) در صورت نیاز مستند قالب", [face["source_ref"], face["payment_ref"], fw["payment_scope_ref"]], segment_id=sid, side=face["side"], net_geometric_area_m2=ds(area), documented_contact_m2=ds(contact_total), status=face["status"]))
    if set(faces) != {(sid, side) for sid in segments for side in FACE_SIDES}:
        fail("FORMWORK", "هر قطعه باید وجه جلو و پشت با وضعیت مصوب داشته باشد")

    edge_area = ZERO
    edge_intervals = {}
    for edge in sequence(fw["edge_faces"], label="وجوه کناری"):
        record(edge, {"id", "physical_face_id", "segment_id", "kind", "status", "start_m", "end_m", "source_ref", "approved_by", "payment_ref"}, {"reason", "opening_id", "jamb_side"}, label="وجه کناری")
        eid = unique(edge["id"], face_seen, "شناسه سطح")
        claim("face", edge["physical_face_id"])
        sid = ident(edge["segment_id"], label="قطعه وجه کناری")
        if sid not in segments or edge["kind"] not in EDGE_KINDS or edge["status"] not in ("formed", "not_required"):
            fail("FORMWORK", "وجه کناری یا نوع تماس نامعتبر است")
        audited(edge, "وجه کناری")
        nonblank(edge["payment_ref"], label="مرجع پرداخت وجه جانبی")
        if edge["status"] == "not_required":
            nonblank(edge.get("reason"), label="دلیل حذف وجه کناری")
        seg = segments[sid]
        r = seg["rect"]
        kind = edge["kind"]
        start = decimal(edge["start_m"], "شروع بازه قالب کناری", nonnegative=True)
        end = decimal(edge["end_m"], "پایان بازه قالب کناری", positive=True)
        if end <= start:
            fail("FORMWORK", "بازه لبه باید طول مثبت داشته باشد")
        if kind == "opening_jamb":
            oid = ident(edge.get("opening_id"), label="شناسه بازشوی لبه")
            jamb_side = edge.get("jamb_side")
            if jamb_side not in {"left", "right", "top", "bottom"}:
                fail("FORMWORK", "لبه بازشو باید نوع ضلع صریح داشته باشد")
            matching = [o for o in seg["openings"] if o["id"] == oid]
            if len(matching) != 1:
                fail("FORMWORK", "لبه بازشو به هندسه معتبر ارجاع نمی‌دهد")
            op = matching[0]["rect"]
            if (jamb_side == "left" and op[0] == r[0] or
                jamb_side == "right" and op[2] == r[2] or
                jamb_side == "bottom" and op[1] == r[1] or
                jamb_side == "top" and op[3] == r[3]):
                fail("FORMWORK", "لبه بازشو در مرز خارجی دیوار بتن ندارد")
            max_length = op[3]-op[1] if jamb_side in {"left", "right"} else op[2]-op[0]
            interval_key = (sid,kind,oid,jamb_side)
        else:
            if "opening_id" in edge or "jamb_side" in edge:
                fail("FORMWORK", "لبه خارجی نمی‌تواند دیتایل مخصوص لبه بازشو داشته باشد")
            max_length = r[3]-r[1] if kind in {"left_end", "right_end"} else r[2]-r[0]
            interval_key = (sid,kind)
            # A formed wall edge coincident with an opening has no formwork there.
            for op in seg["openings"]:
                orc = op["rect"]
                boundary_match = {
                    "left_end": orc[0] == r[0], "right_end": orc[2] == r[2],
                    "bottom": orc[1] == r[1], "top": orc[3] == r[3],
                }[kind]
                a,b = ((orc[1]-r[1],orc[3]-r[1]) if kind in {"left_end","right_end"}
                       else (orc[0]-r[0],orc[2]-r[0]))
                if boundary_match and max(ZERO,min(end,b)-max(start,a)) > 0 and edge["status"] == "formed":
                    fail("FORMWORK", "قالب کناری نباید در محدوده بازشوی قطع‌کننده محاسبه شود")
            # Shared boundaries of two parts are internal faces, not payable edge formwork.
            if edge["status"] == "formed":
                for osid, other in segments.items():
                    if osid == sid:
                        continue
                    o = other["rect"]
                    if kind == "left_end" and o[2] == r[0] and max(ZERO,min(end+r[1],o[3])-max(start+r[1],o[1]))>0:
                        fail("FORMWORK", "وجه مشترک قطعات نباید قالب کناری دریافت کند")
                    if kind == "right_end" and o[0] == r[2] and max(ZERO,min(end+r[1],o[3])-max(start+r[1],o[1]))>0:
                        fail("FORMWORK", "وجه مشترک قطعات نباید قالب کناری دریافت کند")
                    if kind == "bottom" and o[3] == r[1] and max(ZERO,min(end+r[0],o[2])-max(start+r[0],o[0]))>0:
                        fail("FORMWORK", "وجه مشترک قطعات نباید قالب کناری دریافت کند")
                    if kind == "top" and o[1] == r[3] and max(ZERO,min(end+r[0],o[2])-max(start+r[0],o[0]))>0:
                        fail("FORMWORK", "وجه مشترک قطعات نباید قالب کناری دریافت کند")
        if end > max_length:
            fail("FORMWORK", "طول قالب جانبی خارج از محدوده هندسی مستند است")
        existing = edge_intervals.setdefault(interval_key, [])
        if any(max(ZERO, min(end,b)-max(start,a))>0 for a,b in existing):
            fail("DUPLICATE", "بازه‌های وجوه جانبی یک قطعه یا بازشو با شناسه‌های مختلف روی‌هم افتاده‌اند")
        existing.append((start,end))
        length = end-start
        qty = length * seg["thickness"] if edge["status"] == "formed" else ZERO
        edge_area += qty
        results.append(_format_row("formwork_edge", eid, qty, "m2", "طول بازه مستند ضلع×ضخامت همان قطعه", [edge["source_ref"], edge["payment_ref"], fw["payment_scope_ref"]], segment_id=sid, edge_kind=kind, status=edge["status"], exposed_length_m=ds(length)))

    bars = record(data["rebars"], set(BAR_GROUPS), label="گروه‌های مستقل میلگرد")
    physical_bars = set()
    rebar_mass = ZERO
    group_totals = {}
    for group in BAR_GROUPS:
        part = record(bars[group], {"status", "source_ref", "approved_by"}, {"reason", "series"}, label=f"میلگرد {group}")
        audited(part, f"میلگرد {group}")
        if part["status"] == "not_applicable":
            if group in ("vertical", "horizontal"):
                fail("REBAR_DETAIL", "دیوار برشی بتن‌آرمه نیازمند دیتایل مصوب میلگرد قائم و افقی است")
            if "series" in part:
                fail("REBAR_DETAIL", "گروه غیرقابل‌کاربرد نمی‌تواند سری داشته باشد")
            nonblank(part.get("reason"), label="علت عدم کاربرد میلگرد")
            group_totals[group] = {"status": "not_applicable", "kg": None, "reason": part["reason"]}
            continue
        if part["status"] != "confirmed":
            fail("UNREVIEWED", f"گروه {group} باید مستند و تأیید شود")
        total_group = ZERO
        ids = set()
        for bar in sequence(part.get("series"), label=f"سری میلگرد {group}", nonempty=True):
            record(bar, {"id", "physical_bar_set_id", "diameter_mm", "count", "count_scope", "unit_weight_kg_m", "unit_weight_source", "source_ref", "approved_by"}, {"cut_length_m", "cut_parts"}, label="سری میلگرد")
            bid = unique(bar["id"], ids, "شناسه سری میلگرد")
            physical = ident(bar["physical_bar_set_id"], label="شناسه فیزیکی سری میلگرد")
            if physical in physical_bars:
                fail("DUPLICATE", "سری فیزیکی میلگرد بین گروه‌ها تکرار شده است")
            physical_bars.add(physical)
            claim("bar", physical)
            audited(bar, "سری میلگرد")
            if bar["count_scope"] != "total_wall":
                fail("REBAR_DETAIL", "تعداد باید برای کل این دیوار صریح باشد؛ فاصله‌گذاری و ضریب تکرار پذیرفته نیست")
            decimal(bar["diameter_mm"], "قطر اسمی میلگرد mm", positive=True)
            count = decimal(bar["count"], "تعداد میلگرد", positive=True, integer=True)
            unit_weight = decimal(bar["unit_weight_kg_m"], "وزن واحد طول", positive=True)
            nonblank(bar["unit_weight_source"], label="جدول وزن واحد معتبر")
            length, formula = _bar_length(bar)
            mass = count * unit_weight * length
            total_group += mass
            rebar_mass += mass
            results.append(_format_row("rebar_"+group, physical, mass, "kg", "تعداد تأییدشده×وزن واحد طول×("+formula+")", [bar["source_ref"], bar["unit_weight_source"]], diameter_mm=ds(decimal(bar["diameter_mm"], "قطر", positive=True)), cut_length_m=ds(length), count=ds(count)))
        group_totals[group] = {"status": "confirmed", "kg": ds(total_group)}

    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=lambda o: ds(o) if isinstance(o, Decimal) else fail("SCHEMA", "نوع داده غیرقابل سریال‌سازی"))
    evidence_fingerprint = sha256(payload.encode("utf-8")).hexdigest()
    return {"policy": SCHEMA, "status": "standalone_reviewed_preview_not_committed", "identity": {"project_id": data["project_id"], "floor_id": data["floor_id"], "wall_id": data["wall_id"], "physical_wall_id": data["physical_wall_id"]},
            "input_sha256": evidence_fingerprint, "source_id": source["source_id"], "provenance": {"source_ref": source["source_ref"], "axis_ref": datum["axis_ref"], "coordinate_ref": datum["coordinate_ref"], "level_ref": datum["level_ref"], "orientation": datum["orientation"]},
            "totals": {"gross_concrete_m3": ds(gross_total), "openings_m3": ds(opening_total), "documented_interface_m3": ds(iface_total), "net_concrete_m3": ds(net_total), "geometric_main_formwork_m2": ds(gross_main_area), "payable_main_formwork_m2": ds(payable_main), "payable_edge_formwork_m2": ds(edge_area), "payable_formwork_m2": ds(payable_main + edge_area), "rebar_kg": ds(rebar_mass)},
            "rebar_groups": group_totals, "physical_claims": sorted(used_claims), "rows": results,
            "warnings": ["برداشت از نقشه، تداخل‌های اعلام‌نشده، واحدهای دیگر، SQLite، بازبینی مستقل، BOQ و پذیرش Windows در این ماژول انجام نشده است."]}
