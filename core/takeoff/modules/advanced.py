"""Extended construction quantity operations used by the unified takeoff engine."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math

def _n(v: Any, name: str, minimum: float = 0.0) -> float:
    if isinstance(v, bool): raise ValueError(f"{name} must be numeric")
    try: x=float(v)
    except (TypeError, ValueError, OverflowError): raise ValueError(f"{name} must be numeric")
    if not math.isfinite(x): raise ValueError(f"{name} must be finite")
    if x < minimum: raise ValueError(f"{name} must be >= {minimum}")
    if name in {"count", "joist_count"} and not x.is_integer():
        raise ValueError(f"{name} must be an integer")
    return x

@dataclass(frozen=True)
class AdvancedQuantity:
    category: str
    item: str
    quantity: float
    unit: str
    formula: str

def calculate_advanced_item(item: str, **p: Any) -> AdvancedQuantity:
    k=item.strip().casefold().replace(" ","_")
    if k in {"excavation","خاکبرداری"}:
        q=_n(p["length"],"length")*_n(p["width"],"width")*_n(p["depth"],"depth")*_n(p.get("count",1),"count")
        return AdvancedQuantity("خاکی","خاکبرداری",q,"m3","L×W×D×تعداد")
    if k in {"demolition","demolition_volume","تخریب"}:
        q=_n(p["length"],"length")*_n(p["width"],"width")*_n(p["height"],"height")*_n(p.get("count",1),"count")
        return AdvancedQuantity("تخریب","تخریب حجمی",q,"m3","L×W×H×تعداد")
    if k in {"footing_concrete","foundation_concrete","بتن_فونداسیون"}:
        q=_n(p["length"],"length")*_n(p["width"],"width")*_n(p["thickness"],"thickness")*_n(p.get("count",1),"count")
        return AdvancedQuantity("فونداسیون","بتن فونداسیون",q,"m3","L×W×t×تعداد")
    if k in {"footing_formwork","قالب_فونداسیون"}:
        q=_n(p["perimeter"],"perimeter")*_n(p["height"],"height")*_n(p.get("count",1),"count")
        return AdvancedQuantity("فونداسیون","قالب فونداسیون",q,"m2","محیط×ارتفاع×تعداد")
    if k in {"steel_roof_deck_area"}:
        q=_n(p["length"],"length", minimum=1e-12)*_n(p["width"],"width", minimum=1e-12)*_n(p.get("count",1),"count")
        return AdvancedQuantity("سقف فولادی","مساحت عرشه فولادی",q,"m2","L×W×تعداد")
    if k in {"steel_roof_deck_weight","steel_roof_composite_deck"}:
        q=_n(p["length"],"length", minimum=1e-12)*_n(p["width"],"width", minimum=1e-12)*_n(p["sheet_weight"],"sheet_weight", minimum=1e-12)*_n(p.get("count",1),"count")
        return AdvancedQuantity("سقف فولادی","وزن ورق عرشه",q,"kg","L×W×kg/m²×تعداد")
    if k in {"kromit_roof"}:
        q=_n(p["joist_length"],"joist_length", minimum=1e-12)*_n(p["joist_unit_weight"],"joist_unit_weight", minimum=1e-12)*_n(p["joist_count"],"joist_count", minimum=1e-12)*_n(p.get("count",1),"count")
        return AdvancedQuantity("سقف فولادی","وزن تیرچه کرومیت",q,"kg","طول تیرچه×وزن واحد×تعداد تیرچه×تعداد سقف")
    if k in {"steel_truss_roof"}:
        q=_n(p["steel_length"],"steel_length", minimum=1e-12)*_n(p["unit_weight"],"unit_weight", minimum=1e-12)*_n(p.get("count",1),"count")
        return AdvancedQuantity("سقف فولادی","وزن فولاد خرپا",q,"kg","طول کل فولاد×وزن واحد×تعداد")
    if k in {"steel_sandwich_roof"}:
        q=_n(p["length"],"length")*_n(p["width"],"width")*_n(p.get("count",1),"count")
        return AdvancedQuantity("سقف فولادی","مساحت ساندویچ‌پنل",q,"m2","L×W×تعداد")
    if k in {"steel","steel_roof","steel_weight","اسکلت_فلزی"}:
        q=_n(p["length"],"length")*_n(p["unit_weight"],"unit_weight")*_n(p.get("count",1),"count")
        return AdvancedQuantity("اسکلت فلزی","وزن فولاد",q,"kg","L×وزن واحد×تعداد")
    if k in {"screed","کف_سازی"}:
        q=_n(p["length"],"length")*_n(p["width"],"width")*_n(p["thickness"],"thickness")*_n(p.get("count",1),"count")
        return AdvancedQuantity("کف‌سازی","حجم کف‌سازی",q,"m3","L×W×t×تعداد")
    if k in {"facade","نما"}:
        gross=_n(p["length"],"length")*_n(p["height"],"height")
        openings=_n(p.get("openings",0),"openings")
        if openings > gross:
            raise ValueError("openings cannot exceed gross facade area")
        q=gross-openings
        return AdvancedQuantity("نما","سطح نما",q,"m2","L×H−بازشو")
    if k in {"ceiling","false_ceiling","سقف_کاذب"}:
        q=_n(p["length"],"length")*_n(p["width"],"width")*_n(p.get("count",1),"count")
        return AdvancedQuantity("سقف کاذب","سطح سقف کاذب",q,"m2","L×W×تعداد")
    raise KeyError(f"unsupported advanced item: {item}")
