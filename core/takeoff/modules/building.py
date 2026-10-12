"""Deterministic building/architectural quantity operations.

All operations are unit-aware and intentionally independent from pricing.
They accept normalized dictionaries so the same engine can be driven by
forms, CAD rules, BIM quantities, or imported schedules.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math

@dataclass(frozen=True)
class QuantityResult:
    category: str
    item: str
    quantity: float
    unit: str
    formula: str
    warnings: tuple[str, ...] = ()

def _n(v: Any, name: str, *, minimum: float = 0.0) -> float:
    if isinstance(v, bool): raise ValueError(f"{name} must be numeric")
    try: x=float(v)
    except (TypeError, ValueError, OverflowError): raise ValueError(f"{name} must be numeric")
    if not math.isfinite(x): raise ValueError(f"{name} must be finite")
    if x < minimum: raise ValueError(f"{name} must be >= {minimum}")
    if name in {"count", "void_count", "joist_count", "layers"} and not x.is_integer():
        raise ValueError(f"{name} must be an integer")
    return x

def _rect_area(length,width): return _n(length,"length")*_n(width,"width")
def _wall_area(length,height,openings=0):
    gross = _n(length,"length")*_n(height,"height")
    deduction = _n(openings,"openings")
    if deduction > gross:
        raise ValueError("openings cannot exceed gross wall area")
    return gross-deduction

def calculate_building_item(item: str, **p: Any) -> QuantityResult:
    k=item.strip().casefold().replace(" ","_")
    if k in {"wall","wall_area","دیوار"}:
        q=_wall_area(p["length"],p["height"],p.get("openings",0))*_n(p.get("count",1),"count"); return QuantityResult("ابنیه","دیوار",q,"m2","(L×H−بازشو)×تعداد")
    if k in {"slab","slab_area","floor","کف"}:
        q=_rect_area(p["length"],p["width"]); return QuantityResult("ابنیه","سطح سقف/کف",q,"m2","L×W")
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
        import math
        joist_count=_n(p.get("joist_count", math.ceil(W/spacing)+1),"joist_count", minimum=1e-12)
        ribs=joist_count*L*joist_width*joist_depth*count
        q=topping+ribs
        return QuantityResult("سقف سبک بتنی",item,q,"m3","A×t رویه + تعداد تیرچه×L×b×h",("تعداد تیرچه از عرض/فاصله به‌صورت شفاف مشتق شده؛ کلاف‌ها، تیرهای مرزی و بازشوها جداگانه متره شوند.",))
    if k in {"hollow_core_roof","دال_مجوف"}:
        area=_rect_area(p["length"],p["width"])*_n(p.get("count",1),"count")
        gross=area*_n(p["thickness"],"thickness", minimum=1e-12)
        void=3.141592653589793*(_n(p["void_diameter"],"void_diameter")/2)**2*_n(p["length"],"length")*_n(p["void_count"],"void_count")*_n(p.get("count",1),"count")
        if void > gross:
            raise ValueError("hollow-core void volume cannot exceed gross slab volume")
        q=gross-void
        return QuantityResult("سقف دال مجوف",item,q,"m3","L×W×t − π(d/2)²×L×تعداد فضای خالی",())
    if k in {"waffle_roof","وافل"}:
        area=_rect_area(p["length"],p["width"])*_n(p.get("count",1),"count")
        top=area*_n(p["top_thickness"],"top_thickness")
        dx=(area/_n(p["spacing_x"],"spacing_x", minimum=1e-12))*_n(p["rib_width"],"rib_width", minimum=1e-12)*_n(p["rib_depth"],"rib_depth", minimum=1e-12)
        dy=(area/_n(p["spacing_y"],"spacing_y", minimum=1e-12))*_n(p["rib_width"],"rib_width")*_n(p["rib_depth"],"rib_depth")
        overlap=(area/(_n(p["spacing_x"],"spacing_x")*_n(p["spacing_y"],"spacing_y")))*_n(p["rib_width"],"rib_width")**2*_n(p["rib_depth"],"rib_depth")
        q=top+dx+dy-overlap
        return QuantityResult("سقف وافل",item,q,"m3","A×t رویه + A/sx×b×h + A/sy×b×h − تقاطع تیرچه‌ها",())
    if k in {"uboot_roof","cobiax_roof"}:
        area=_rect_area(p["length"],p["width"])*_n(p.get("count",1),"count")
        gross=area*_n(p["thickness"],"thickness")
        void=_n(p["void_length"],"void_length")*_n(p["void_width"],"void_width")*_n(p["void_height"],"void_height")*_n(p["void_count"],"void_count")*_n(p.get("count",1),"count")
        if void > gross:
            raise ValueError("void volume cannot exceed gross slab volume")
        q=gross-void
        return QuantityResult("سقف مجوف",item,q,"m3","L×W×t − حجم واقعی فضاهای خالی",())
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
        q=_wall_area(p["length"],p["height"],p.get("openings",0))*_n(p.get("waste",1.0),"waste",minimum=0); return QuantityResult("نازک‌کاری",item,q,"m2","سطح خالص×ضریب پرت")
    if k in {"roof_insulation","waterproofing","عایق"}:
        q=_rect_area(p["length"],p["width"])*_n(p.get("layers",1),"layers"); return QuantityResult("عایق‌کاری",item,q,"m2","L×W×لایه")
    if k in {"door","window","opening","درب","پنجره"}:
        q=_n(p.get("count",1),"count"); return QuantityResult("در و پنجره",item,q,"عدد","تعداد")
    if k in {"rebar","reinforcement","آرماتور"}:
        q=_n(p["length"],"length")*_n(p["unit_weight"],"unit_weight")*_n(p.get("count",1),"count"); return QuantityResult("آرماتور",item,q,"kg","L×وزن واحد×تعداد")
    raise KeyError(f"unsupported building item: {item}")
