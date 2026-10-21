"""Deterministic building/architectural quantity operations.

All operations are unit-aware and intentionally independent from pricing.
They accept normalized dictionaries so the same engine can be driven by
forms, CAD rules, BIM quantities, or imported schedules.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math
from decimal import Decimal

@dataclass(frozen=True)
class QuantityResult:
    category: str
    item: str
    quantity: float
    unit: str
    formula: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        finite = self.quantity.is_finite() if isinstance(self.quantity, Decimal) else math.isfinite(self.quantity)
        if not finite or self.quantity < 0:
            raise ValueError("نتیجه متره باید متناهی و نامنفی باشد (finite and nonnegative)")

def _n(v: Any, name: str, *, minimum: float = 0.0) -> float:
    if isinstance(v, bool): raise ValueError(f"{name} must be numeric")
    try: x=float(v)
    except (TypeError, ValueError, OverflowError): raise ValueError(f"{name} must be numeric")
    if not math.isfinite(x): raise ValueError(f"{name} must be finite")
    if x == 0.0 and Decimal(str(v)) != 0:
        raise ValueError(f"{name} underflow: nonzero input rounded to zero")
    if name in {"count", "void_count", "joist_count", "layers", "rib_count_x", "rib_count_y", "intersection_count"}:
        if not x.is_integer() or Decimal(str(v)) != Decimal(int(x)):
            raise ValueError(f"{name} must be an exactly representable integer")
    if name in {"length", "width", "depth", "height", "thickness", "perimeter", "sloped_length", "waist_thickness", "unit_weight", "count", "layers"}:
        minimum = max(minimum, 1e-12)
    if x < minimum: raise ValueError(f"{name} must be >= {minimum}")
    if name in {"count", "void_count", "joist_count", "layers"} and not x.is_integer():
        raise ValueError(f"{name} must be an integer")
    if not isinstance(v, float) and Decimal(str(v)) != Decimal(str(x)):
        raise ValueError(f"{name}: دقت ورودی مستند در تبدیل به float قابل حفظ نیست")
    return x

def _rect_area(length,width): return _n(length,"length")*_n(width,"width")
def _wall_area(length,height,openings=0):
    gross = _n(length,"length")*_n(height,"height")
    deduction = _n(openings,"openings")
    if deduction > gross:
        raise ValueError("openings cannot exceed gross wall area")
    return gross-deduction


def _mul(*factors):
    result = 1.0
    for factor in factors:
        result *= factor
    if not math.isfinite(result):
        raise ValueError("نتیجه متره باید متناهی باشد (finite)")
    if result == 0.0 and all(factor > 0.0 for factor in factors):
        raise ValueError("derived quantity underflow: nonzero product rounded to zero")
    return result

def calculate_building_item(item: str, **p: Any) -> QuantityResult:
    k=item.strip().casefold().replace(" ","_")
    if k in {"wall","wall_area","دیوار"}:
        q=_wall_area(p["length"],p["height"],p.get("openings",0))*_n(p.get("count",1),"count"); return QuantityResult("ابنیه","دیوار",q,"m2","(L×H−بازشو)×تعداد")
    if k in {"slab","slab_area","floor","کف"}:
        q=_wall_area(p["length"],p["width"],p.get("openings",0))*_n(p.get("count",1),"count")
        return QuantityResult("ابنیه","سطح سقف/کف",q,"m2","(L×W−بازشوی هر تکرار)×تعداد")
    if k == "steel_roof_composite_concrete":
        # A flat bounding rectangle is NOT complete corrugated-deck concrete.
        # Only individually reviewed flat topping zones can use this legacy
        # item; complete roofs must use separately reviewed AEC detail parts.
        required = {"composite_scope", "deck_profile_ref", "reviewed_concrete_regions"}
        # Application bookkeeping metadata must never masquerade as geometry.
        metadata = {"manual_location_id", "member_code", "price_code", "unit_price"}
        if not required.issubset(p) or set(p) - required - metadata:
            raise ValueError("سقف مرکب به دیتایل واقعی، مرجع پروفیل و نواحی بتن تأییدشده نیاز دارد")
        if p["composite_scope"] != "topping_only":
            raise ValueError("بتن کامل سقف مرکب فقط از مسیر دیتایل ناحیه‌ای تأییدشده مجاز است")
        from core.takeoff.reviewed_components import require_text
        from core.takeoff.reviewed_detail_calculators import calculate_reviewed_detail
        require_text(p["deck_profile_ref"], "مرجع پروفیل عرشه فولادی")
        checked = calculate_reviewed_detail("concrete_regions", p["reviewed_concrete_regions"])
        if any(region["input"]["voids"] for region in checked["details"]):
            raise ValueError("کسورات بتن جان عرشه نباید داخل دیتایل رویه با scope=topping_only محاسبه شود")
        return QuantityResult("سقف مرکب — فقط رویه", item, checked["quantity"], "m3",
                              "جمع حجم واقعی رویه از دیتایل ناحیه‌ای تأییدشده",
                              ("این مقدار فقط بتن رویه است؛ حجم بتن جان عرشه و سایر نواحی نیازمند ریزمتره مستقل‌اند.",))
    if k in {"solid_slab_roof","solid_slab","flat_slab"}:
        q=_rect_area(p["length"],p["width"])*_n(p["thickness"],"thickness", minimum=1e-12)*_n(p.get("count",1),"count")
        return QuantityResult("سقف بتن‌آرمه",item,q,"m3","L×W×t×تعداد")
    if k in {"joist_block_roof","joist_foam_roof"}:
        L=_n(p["length"],"length")
        W=_n(p["width"],"width")
        count=_n(p.get("count",1),"count")
        area=L*W*count
        topping=area*_n(p["topping_thickness"],"topping_thickness", minimum=1e-12)
        spacing=_n(p["joist_spacing"],"joist_spacing", minimum=1e-12)
        joist_width=_n(p["joist_width"],"joist_width", minimum=1e-12)
        joist_depth=_n(p["joist_depth"],"joist_depth", minimum=1e-12)
        if joist_width > spacing:
            raise ValueError("joist_width cannot exceed joist_spacing")
        joist_count=_n(p["joist_count"],"joist_count", minimum=1e-12)
        ribs=joist_count*L*joist_width*joist_depth*count
        q=topping+ribs
        return QuantityResult("سقف سبک بتنی",item,q,"m3","A×t رویه + تعداد تیرچه×L×b×h",("تعداد تیرچه باید صریح از نقشه چیدمان مستند وارد شود؛ تیرچه‌های پیش‌ساخته بتن درجا نیستند و حجم کلاف‌ها و بازشوها باید جداگانه کنترل شود.",))
    if k in {"hollow_core_roof","دال_مجوف"}:
        # Precast voids are not implicitly as long as the outer slab.
        # A real section schedule must confirm both shape and effective length.
        from core.takeoff.reviewed_components import require_text
        require_text(p.get("void_spec_ref"), "مرجع واقعی پروفیل فضای خالی هالوکور")
        require_text(p.get("void_reviewed_by"), "بازبین پروفیل هالوکور")
        if p.get("void_cross_section") != "circular":
            raise ValueError("فقط فضای خالی دایره‌ای با مقطع تأییدشده قابل محاسبه است")
        effective = _n(p.get("void_effective_length_m"), "void_effective_length_m", minimum=1e-12)
        length = _n(p["length"], "length")
        width = _n(p["width"], "width")
        thick = _n(p["thickness"], "thickness")
        count = _n(p.get("count", 1), "count")
        diameter = _n(p["void_diameter"], "void_diameter", minimum=1e-12)
        void_count = _n(p["void_count"], "void_count", minimum=1)
        if effective > length:
            raise ValueError("طول واقعی حفره نمی‌تواند از طول قطعه بیشتر باشد")
        if diameter > thick or diameter * void_count > width:
            raise ValueError("هندسه فضای خالی هالوکور در ضخامت یا عرض واقعی نمی‌گنجد")
        gross = length * width * thick
        void = math.pi * (diameter / 2)**2 * effective * void_count
        if void >= gross:
            raise ValueError("hollow-core void volume cannot exceed gross slab volume")
        return QuantityResult("سقف دال مجوف", item, (gross-void)*count, "m3",
                              "(حجم قطعه − π×قطر²/۴×طول واقعی حفره×تعداد)×تعداد قطعه",
                              ("فقط مقطع دایره‌ای دارای مرجع؛ بتن رویه و درزها جداگانه متره شوند.",))
    if k in {"waffle_roof","وافل"}:
        # Grid spacing is not a schedule of physical ribs. Use signed real
        # rib counts and run lengths, and deduct intersections exactly once.
        from core.takeoff.reviewed_components import require_text
        require_text(p.get("layout_ref"), "مرجع جانمایی واقعی وافل")
        require_text(p.get("approved_by"), "تأییدکننده جانمایی وافل")
        L=_n(p["length"], "length")
        W=_n(p["width"], "width")
        count=_n(p.get("count",1), "count")
        topping=_n(p["top_thickness"], "top_thickness", minimum=1e-12)
        rib_width=_n(p["rib_width"], "rib_width", minimum=1e-12)
        rib_depth=_n(p["rib_depth"], "rib_depth", minimum=1e-12)
        nx=_n(p.get("rib_count_x"), "rib_count_x", minimum=1)
        ny=_n(p.get("rib_count_y"), "rib_count_y", minimum=1)
        ix=_n(p.get("intersection_count"), "intersection_count", minimum=0)
        lx=_n(p.get("rib_run_length_x_m"), "rib_run_length_x_m", minimum=1e-12)
        ly=_n(p.get("rib_run_length_y_m"), "rib_run_length_y_m", minimum=1e-12)
        for field, num in (("rib_count_x",nx),("rib_count_y",ny),("intersection_count",ix)):
            if not num.is_integer(): raise ValueError(f"{field} باید عدد صحیح واقعی باشد")
        if rib_width >= min(L,W) or lx > L or ly > W or ix > nx*ny:
            raise ValueError("جانمایی تیرچه‌های وافل با طول، عرض یا تعداد تقاطع‌ها سازگار نیست")
        gross_topping = L*W*topping
        ribs = (nx*lx+ny*ly)*rib_width*rib_depth
        overlaps = ix*rib_width*rib_width*rib_depth
        if overlaps >= ribs:
            raise ValueError("حجم تقاطع‌ها از حجم جان تیرچه‌ها بیشتر است")
        q = (gross_topping+ribs-overlaps)*count
        return QuantityResult("سقف وافل — جانمایی بازبینی‌شده",item,q,"m3",
                              "(حجم رویه + حجم جان‌های شمارش‌شده − تقاطع‌های واقعی)×تعداد سقف",
                              ("کلاف‌ها، نواحی توپر، لبه‌ها و بازشوها در این مقدار نیستند.",))
    if k == "cobiax_roof":
        if not str(p.get("void_spec_ref", "")).strip() or "void_volume" not in p:
            raise ValueError("cobiax requires verified void_volume and void_spec_ref; bounding-box dimensions are not void volume")
        gross = _rect_area(p["length"],p["width"]) * _n(p["thickness"], "thickness")
        void = _n(p["void_volume"], "void_volume", minimum=1e-12) * _n(p["void_count"], "void_count", minimum=1)
        if void > gross:
            raise ValueError("void volume cannot exceed gross slab volume")
        q = (gross - void) * _n(p.get("count",1), "count")
        return QuantityResult("سقف مجوف",item,q,"m3","(L×W×t − حجم تأییدشده هر حفره×تعداد حفره)×تعداد سقف",("حجم حفره از مشخصات صریح کاربر؛ هندسه تولیدکننده و نواحی توپر باید بازبینی شوند.",))
    if k == "uboot_roof":
        if not str(p.get("void_spec_ref", "")).strip() or "void_volume" not in p:
            raise ValueError("uboot requires verified void_volume and void_spec_ref; bounding-box dimensions cannot establish actual void volume")
        # The void is a manufactured hollow shape, not necessarily the
        # rectangular outer bounding box. Use independently reviewed volume.
        count=_n(p.get("count",1),"count")
        gross=_rect_area(p["length"],p["width"])*_n(p["thickness"],"thickness")
        void=_n(p["void_volume"],"void_volume",minimum=1e-12)*_n(p["void_count"],"void_count",minimum=1)
        if void > gross:
            raise ValueError("void volume cannot exceed gross slab volume")
        q=(gross-void)*count
        return QuantityResult("سقف مجوف",item,q,"m3","(حجم ناخالص − حجم واقعی مستند حفره‌ها)×تعداد سقف",
                              ("نواحی توپر، کلاف‌ها و دیتایل واقعی سازنده باید جداگانه بررسی شوند.",))
    if k in {"slab_volume","concrete_slab","بتن_سقف"}:
        q=_rect_area(p["length"],p["width"])*_n(p["thickness"],"thickness")*_n(p.get("count",1),"count"); return QuantityResult("ابنیه","بتن سقف",q,"m3","L×W×t×تعداد")
    if k in {"tie_beam","tie_beam_concrete","شناژ"}:
        q=_rect_area(p["width"],p["depth"])*_n(p["length"],"length")*_n(p.get("count",1),"count"); return QuantityResult("سازه","شناژ / کلاف بتنی",q,"m3","b×h×L×تعداد")
    if k in {"shear_wall","shear_wall_concrete","دیوار_برشی"}:
        q=_n(p["length"],"length")*_n(p["thickness"],"thickness")*_n(p["height"],"height")*_n(p.get("count",1),"count"); return QuantityResult("سازه","دیوار برشی بتنی",q,"m3","L×t×H×تعداد")
    if k in {"stair_concrete","stair","پله_بتنی"}:
        if "sloped_length" not in p or "waist_thickness" not in p:
            raise ValueError("stair_concrete requires sloped_length and waist_thickness; horizontal box volume is not a valid stair takeoff")
        q=_n(p["sloped_length"],"sloped_length")*_n(p["width"],"width")*_n(p["waist_thickness"],"waist_thickness", minimum=1e-12)*_n(p.get("count",1),"count")
        return QuantityResult("سازه","حجم دال شیب‌دار پله بتنی",q,"m3","Lشیب×عرض×ضخامت‌دال×تعداد",("حجم پله‌های مثلثی/رایزرها، پاگردها و کسر بازشوها باید با اجزای هندسی مستقل متره شوند.",))
    if k in {"roof_area","roof","سقف"}:
        q=_rect_area(p["length"],p["width"])*_n(p.get("count",1),"count"); return QuantityResult("سقف","مساحت سیستم سقف",q,"m2","L×W×تعداد")
    if k in {"column","column_concrete","بتن_ستون"}:
        q=_rect_area(p["width"],p["depth"])*_n(p["height"],"height")*_n(p.get("count",1),"count"); return QuantityResult("سازه","بتن ستون",q,"m3","b×h×H×تعداد")
    if k in {"beam","beam_concrete","بتن_تیر"}:
        q=_rect_area(p["width"],p["depth"])*_n(p["length"],"length")*_n(p.get("count",1),"count"); return QuantityResult("سازه","بتن تیر",q,"m3","b×h×L×تعداد")
    if k in {"formwork","formwork_area","قالب"}:
        q=_n(p["perimeter"],"perimeter")*_n(p["height"],"height")*_n(p.get("count",1),"count"); return QuantityResult("بتن","قالب‌بندی",q,"m2","محیط×ارتفاع×تعداد")
    if k in {"plaster","plaster_area","گچ","گچ_کاری","paint","paint_area","رنگ"}:
        q=_wall_area(p["length"],p["height"],p.get("openings",0))*_n(p.get("count",1),"count"); return QuantityResult("نازک‌کاری",item,q,"m2","سطح خالص×تعداد")
    if k in {"tile","ceramic","tile_area","کاشی","سرامیک"}:
        q=_mul(_wall_area(p["length"],p["height"],p.get("openings",0)), _n(p.get("waste",1.0),"waste",minimum=0)); return QuantityResult("نازک‌کاری",item,q,"m2","سطح خالص×ضریب پرت")
    if k in {"roof_insulation","waterproofing","عایق"}:
        q=_rect_area(p["length"],p["width"])*_n(p.get("layers",1),"layers"); return QuantityResult("عایق‌کاری",item,q,"m2","L×W×لایه")
    if k in {"door","window","opening","درب","پنجره"}:
        q=_n(p.get("count",1),"count"); return QuantityResult("در و پنجره",item,q,"عدد","تعداد")
    if k in {"rebar","reinforcement","آرماتور"}:
        detail_fields = ("bend_length", "hook_length", "lap_length")
        if any(name in p for name in (*detail_fields, "diameter_mm", "detail_ref")):
            if any(name not in p for name in (*detail_fields, "diameter_mm")) or not str(p.get("detail_ref", "")).strip():
                raise ValueError("rebar detail requires diameter_mm, bend_length, hook_length, lap_length and detail_ref")
            _n(p["diameter_mm"], "diameter_mm", minimum=1e-12)
            cut_length = _n(p["length"], "length") + sum(_n(p[name], name) for name in detail_fields)
            formula = "(طول مستقیم+خم+قلاب+وصله)×وزن واحد صریح×تعداد"
            warnings = ()
        else:
            cut_length = _n(p["length"], "length")
            formula = "طول برش صریح×وزن واحد×تعداد"
            warnings = ("طول ورودی باید طول برش کامل باشد؛ دیتایل قطر/خم/قلاب/وصله در این ردیف ثبت نشده و پذیرش دقیق میلگرد نیازمند بازبینی است.",)
        q=cut_length*_n(p["unit_weight"],"unit_weight")*_n(p.get("count",1),"count")
        return QuantityResult("آرماتور",item,q,"kg",formula,warnings)
    raise KeyError(f"unsupported building item: {item}")
