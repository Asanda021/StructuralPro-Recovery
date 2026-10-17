"""Independent documented bored-pile takeoff, no persistence or guessed parameters.

Contract covers an explicit single straight cylindrical bore per physical pile,
with explicit top/bottom elevations, bar cut schedules, and owner-documented
concrete intersection deductions. Excavation, overpour, grout, spoil,
uncertain casing and pile design are NOT inferred from this geometric takeoff.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, Context, localcontext
import hashlib
import json

POLICY = "bored_pile_specialist_chat_v1"
PI = Decimal("3.14159265358979323846264338327950288419716939937510")
GROUPS = ("longitudinal", "spiral_ties", "crossties", "starters")
PARTS = ("straight", "bend", "hook", "anchorage", "lap", "other")


class PileInputError(ValueError):
    """Fail-closed input error with no guessed engineering fallback."""


def ident(x, label="شناسه"):
    if not isinstance(x, str) or not x.strip() or x != x.strip():
        raise PileInputError(f"{label}: متن صریح بدون فاصله اضافی لازم است")
    return x


def number(x, label, *, positive=True):
    if isinstance(x, (float, bool)) or not isinstance(x, (Decimal, int, str)):
        raise PileInputError(f"{label}: Decimal/int/string لازم است؛ float مجاز نیست")
    try:
        d = Decimal(str(x))
    except (InvalidOperation, ValueError):
        raise PileInputError(f"{label}: عدد نامعتبر") from None
    if d.is_finite() and (len(d.as_tuple().digits) > 60 or d.adjusted() < -60 or d.adjusted() > 60):
        raise PileInputError(f"{label}: دامنه یا دقت عدد فراتر از قرارداد مستقل است")
    if not d.is_finite() or (positive and d <= 0):
        raise PileInputError(f"{label}: مقدار نامعتبر یا غیرمثبت")
    return d


def integer(x, label):
    d = number(x, label)
    if d != d.to_integral_value():
        raise PileInputError(f"{label}: عدد صحیح لازم است")
    return int(d)


def exact(d):
    # Avoid context-sensitive normalization; keep all source precision.
    if d == 0:
        return "0"
    return format(d, "f")


def strict(x, keys, label):
    if not isinstance(x, dict) or set(x) != set(keys):
        raise PileInputError(f"{label}: کلیدهای قراردادی ناقص یا نامعتبر")


def hash_input(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                      default=str, separators=(",", ":")).encode("utf-8")).hexdigest()


def source(x, label):
    strict(x, ("source_ref", "approved_by"), label)
    return ident(x["source_ref"], f"منبع {label}"), ident(x["approved_by"], f"تأییدکننده {label}")


def compile_piles(data):
    """Produce audit-only quantities; never assert cross-member ownership cleared."""
    with localcontext(Context(prec=256, Emin=-999999, Emax=999999)):
        strict(data, ("policy", "project_id", "floor_id", "group_id", "source", "datum", "piles"), "ورودی شمع")
        if data["policy"] != POLICY:
            raise PileInputError("قرارداد محاسبه شمع نامعتبر")
        for name in ("project_id", "floor_id", "group_id"):
            ident(data[name], name)
        strict(data["source"], ("source_id", "source_ref", "approved_by"), "منبع برداشت")
        for key in data["source"]:
            ident(data["source"][key], key)
        strict(data["datum"], ("coordinate_ref", "vertical_datum_ref", "axis_ref"), "مبنای مختصات")
        for key in data["datum"]:
            ident(data["datum"][key], key)
        piles = data["piles"]
        if not isinstance(piles, list) or not piles:
            raise PileInputError("شمع‌ها باید فهرست غیرخالی باشند")
        seen_piles, seen_physical, seen_parts, seen_cuts = set(), set(), set(), set()
        out, claims = [], []
        for pile in piles:
            strict(pile, ("id", "physical_id", "diameter_m", "top_elevation_m", "bottom_elevation_m",
                          "geometry", "concrete", "deductions", "formwork", "rebars", "interface"), "شمع")
            pid, physical = ident(pile["id"], "شناسه شمع"), ident(pile["physical_id"], "هویت فیزیکی شمع")
            if pid in seen_piles or physical in seen_physical:
                raise PileInputError("هویت فیزیکی یا شناسه شمع تکراری است")
            seen_piles.add(pid);seen_physical.add(physical)
            gr = source(pile["geometry"], "هندسه شمع")
            diameter = number(pile["diameter_m"], "قطر واقعی حفاری")
            top = number(pile["top_elevation_m"], "تراز بالایی", positive=False)
            bottom = number(pile["bottom_elevation_m"], "تراز پایینی", positive=False)
            if top <= bottom:
                raise PileInputError("تراز بالا باید بزرگ‌تر از تراز پایین باشد")
            length = top-bottom
            gross = PI*diameter*diameter*length/Decimal(4)
            strict(pile["concrete"], ("status", "mix_ref", "source_ref", "approved_by"), "بتن")
            if pile["concrete"]["status"] != "documented_nominal":
                raise PileInputError("وضعیت حجم نظری بتن باید مستند باشد")
            for key in ("mix_ref", "source_ref", "approved_by"):
                ident(pile["concrete"][key], key)
            if not isinstance(pile["deductions"], list):
                raise PileInputError("کسورات باید فهرست صریح باشند")
            dtotal = Decimal(0)
            for cut in pile["deductions"]:
                strict(cut, ("id", "other_physical_id", "owner", "volume_m3", "source_ref", "approved_by"), "کسر شمع")
                cutid = ident(cut["id"], "شناسه کسر")
                unique = (physical, cutid)
                if unique in seen_cuts:
                    raise PileInputError("شناسه کسر تکراری است")
                seen_cuts.add(unique)
                foreign = ident(cut["other_physical_id"], "عضو دیگر")
                if foreign == physical or cut["owner"] != "other_member":
                    raise PileInputError("مالکیت کسر باید صریحاً به عضو دیگر تخصیص یافته باشد")
                ident(cut["source_ref"], "منبع کسر");ident(cut["approved_by"], "تأییدکننده کسر")
                dtotal += number(cut["volume_m3"], "حجم کسر")
            net = gross - dtotal
            if net <= 0:
                raise PileInputError("کسورات بتن بیش از حجم یا برابر آن است")
            strict(pile["interface"], ("pile_cap_id", "column_id", "ownership_status", "source_ref", "approved_by"), "اتصال شمع")
            iface = pile["interface"]
            if iface["ownership_status"] not in ("review_required", "documented_no_overlap", "documented_deductions"):
                raise PileInputError("وضعیت تداخل باید صریح باشد")
            ident(iface["pile_cap_id"], "کلاهک مرتبط");ident(iface["source_ref"], "مرجع اتصال")
            ident(iface["approved_by"], "تأییدکننده اتصال")
            # Optional column: explicit 'none' is distinct from absence.
            ident(iface["column_id"], "ستون مرتبط یا none")
            if iface["ownership_status"] == "documented_deductions" and not pile["deductions"]:
                raise PileInputError("وضعیت کسر مستند بدون سطر کسر مجاز نیست")
            if iface["ownership_status"] == "documented_no_overlap" and pile["deductions"]:
                raise PileInputError("وضعیت عدم تداخل با وجود کسورات سازگار نیست")
            out.append({"kind": "concrete_net", "pile_id": pid, "physical_id": physical+":concrete",
                        "quantity": exact(net), "unit": "m3", "source_refs": [gr[0],pile["concrete"]["source_ref"]],
                        "formula": "π(50 رقم)×قطر²÷۴×(تراز بالا−پایین)−کسورات صریح",
                        "evidence": {"gross_m3": exact(gross), "deductions_m3": exact(dtotal),
                                     "length_m": exact(length), "pi_used": exact(PI),
                                     "pile_cap_id": iface["pile_cap_id"],
                                     "ownership_status": iface["ownership_status"],
                                     "deductions": deepcopy(pile["deductions"])}})
            fw = pile["formwork"]
            if not isinstance(fw, dict) or fw.get("status") not in ("not_applicable", "documented"):
                raise PileInputError("وضعیت قالب/غلاف باید ثبت شده باشد")
            if fw["status"] == "not_applicable":
                strict(fw, ("status", "reason", "source_ref", "approved_by"), "عدم کاربرد قالب")
                for key in ("reason", "source_ref", "approved_by"):
                    ident(fw[key], key)
            else:
                strict(fw, ("status", "faces", "approved_by"), "قالب مستند")
                ident(fw["approved_by"], "تأییدکننده قالب")
                if not isinstance(fw["faces"], list) or not fw["faces"]:
                    raise PileInputError("وجوه قالب باید مستند باشند")
                for face in fw["faces"]:
                    strict(face, ("id", "physical_id", "net_area_m2", "source_ref"), "وجه قالب")
                    fid = ident(face["physical_id"], "وجه فیزیکی قالب")
                    if fid in seen_parts:
                        raise PileInputError("وجه قالب تکراری است")
                    seen_parts.add(fid)
                    out.append({"kind":"formwork", "pile_id":pid,"physical_id":fid,"quantity":exact(number(face["net_area_m2"],"سطح واقعی قالب")),
                                "unit":"m2","source_refs":[ident(face["source_ref"],"منبع قالب")],
                                "formula":"مساحت خالص وجه قالب مستقل مستند", "evidence":{"face_id":ident(face["id"],"وجه")}})
            if not isinstance(pile["rebars"], dict) or set(pile["rebars"])!=set(GROUPS):
                raise PileInputError("تمام گروه‌های میلگرد باید وضعیت صریح داشته باشند")
            for kind in GROUPS:
                group = pile["rebars"][kind]
                if not isinstance(group, dict):
                    raise PileInputError("گروه میلگرد معتبر نیست")
                if group.get("status") == "not_applicable":
                    strict(group, ("status", "reason", "source_ref", "approved_by"), "عدم کاربرد گروه میلگرد")
                    for k in ("reason", "source_ref", "approved_by"):
                        ident(group[k],k)
                    continue
                strict(group, ("status", "source_ref", "approved_by", "series"), "گروه میلگرد")
                if group["status"] != "confirmed":
                    raise PileInputError("گروه میلگرد تأییدنشده است")
                ident(group["source_ref"],"مرجع میلگرد"); ident(group["approved_by"],"تأییدکننده میلگرد")
                if not isinstance(group["series"],list) or not group["series"]:
                    raise PileInputError("سری میلگرد لازم است")
                for series in group["series"]:
                    strict(series, ("id", "physical_id", "count", "unit_weight_kg_m", "unit_weight_ref", "cut_length_m", "cut_length_ref", "approved_by"), "سری میلگرد")
                    sid = ident(series["physical_id"], "هویت فیزیکی سری میلگرد")
                    if sid in seen_parts:
                        raise PileInputError("سری میلگرد یا قطعه فیزیکی تکراری است")
                    seen_parts.add(sid)
                    ident(series["id"], "شناسه سری")
                    for key in ("unit_weight_ref", "cut_length_ref", "approved_by"):
                        ident(series[key], key)
                    mass = number(series["unit_weight_kg_m"], "وزن واحد میلگرد") * number(series["cut_length_m"], "طول برش مستند") * integer(series["count"], "تعداد میلگرد")
                    out.append({"kind":"rebar_"+kind, "pile_id":pid,"physical_id":sid,"quantity":exact(mass),
                                "unit":"kg", "source_refs":[group["source_ref"],series["cut_length_ref"],series["unit_weight_ref"]],
                                "formula":"تعداد صریح×طول برش مصوب×وزن واحد طول با مرجع",
                                "evidence":{"series_id":series["id"],"count":integer(series["count"],"تعداد"),"cut_length_m":exact(number(series["cut_length_m"],"طول"))}})
            claims.append({"pile_id":pid,"physical_id":physical,"cap_id":iface["pile_cap_id"],"column_id":iface["column_id"],
                           "ownership_status":iface["ownership_status"],"source_ref":iface["source_ref"]})
        totals={unit:exact(sum((Decimal(r["quantity"]) for r in out if r["unit"]==unit),Decimal(0))) for unit in ("m3","m2","kg")}
        return {"policy":POLICY,"source_sha256":hash_input(data),"identity":{"project_id":data["project_id"],"floor_id":data["floor_id"],"group_id":data["group_id"]},
                "rows":out,"totals":totals,"physical_claims":claims,
                "limit":"نظری: شمع استوانه‌ای ثابت؛ حفاری واقعی/اضافه‌حفاری/پرت/ظرفیت/تعداد مارپیچ/قیمت محاسبه نمی‌شود؛ ثبت قطعی نیازمند تطبیق مالکیت است"}
