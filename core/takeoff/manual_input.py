"Fast, deterministic manual takeoff input normalization with fail-closed numeric parsing."
from __future__ import annotations
from dataclasses import dataclass
import math
import re

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ALIASES = {
    "ستون": ("column", ("count","width","depth","height")),
    "تیر": ("beam", ("count","length","width","depth")),
    "شناژ": ("tie_beam", ("count","length","width","depth")),
    "کلاف": ("tie_beam", ("count","length","width","depth")),
    "پی": ("footing_concrete", ("count","length","width","thickness")),
    "فونداسیون": ("footing_concrete", ("count","length","width","thickness")),
    "دیوار برشی": ("shear_wall", ("count","length","thickness","height")),
    "دال": ("solid_slab_roof", ("count","length","width","thickness")),
    "سقف دال": ("solid_slab_roof", ("count","length","width","thickness")),
    "تیرچه بلوک": ("joist_block_roof", ("count","length","width","topping_thickness","joist_spacing","joist_width","joist_depth")),
    "تیرچه یونولیت": ("joist_foam_roof", ("count","length","width","topping_thickness","joist_spacing","joist_width","joist_depth")),
    "پله": ("stair_concrete", ("count","sloped_length","width","waist_thickness")),
    "دیوار": ("wall", ("count","length","height","openings")),
    "خاکبرداری": ("excavation", ("length","width","depth")),
    "آرماتور": ("rebar", ("count","length","unit_weight")),
    "فولاد": ("steel", ("count","length","unit_weight")),
}
LATIN_ALIASES = {"column": ALIASES["ستون"], "beam": ALIASES["تیر"], "wall": ALIASES["دیوار"], "stair": ALIASES["پله"]}
_NUMBER = r"[+-]?\d+(?:[.,]\d+)?"

@dataclass(frozen=True)
class ManualEntry:
    code: str
    params: dict[str, float]
    missing: tuple[str, ...]
    source_text: str
    @property
    def complete(self) -> bool:
        return not self.missing

def _number(value: str) -> float:
    try:
        number = float(value.translate(PERSIAN_DIGITS).replace(",", "").strip())
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("مقدار متره باید عددی باشد") from exc
    if not math.isfinite(number):
        raise ValueError("مقدار متره باید متناهی باشد")
    return number

def _normalise(text: str) -> str:
    return (text.translate(PERSIAN_DIGITS).replace("×","x").replace("✕","x")
            .replace("٬",",").replace("٫",".").strip())

def _extract_named(text: str) -> dict[str, float]:
    aliases = {
        "تعداد":"count","عدد":"count","طول":"length","عرض":"width","عمق":"depth",
        "ارتفاع":"height","ضخامت":"thickness","ضخامت رویه":"topping_thickness","ضخامت جان پله":"waist_thickness",
        "طول شیبدار":"sloped_length","بازشو":"openings","فاصله تیرچه":"joist_spacing",
        "فاصله":"joist_spacing","عرض تیرچه":"joist_width","عمق تیرچه":"joist_depth",
        "وزن واحد":"unit_weight","وزن":"unit_weight",
    }
    out = {}
    labels = "|".join(re.escape(label) for label in sorted(aliases, key=len, reverse=True))
    pattern = rf"(?<!\w)({labels})\s*[:=]?\s*({_NUMBER})(?![\d.eE])\s*(mm|cm|m|میلی‌متر|سانتی‌متر|متر)?(?!\w)"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        label, token, unit = match.groups()
        key = aliases[label]
        if "," in token:
            raise ValueError("جداکننده عدد مبهم است؛ برای اعشار از نقطه یا ممیز فارسی استفاده کنید")
        value = _number(token)
        if value < 0:
            raise ValueError(f"مقدار «{label}» نمی‌تواند منفی باشد")
        if unit:
            if key in {"count", "unit_weight", "openings"}:
                raise ValueError(f"واحد طول برای «{label}» معتبر نیست")
            value *= {"mm": .001, "cm": .01, "m": 1,
                      "میلی‌متر": .001, "سانتی‌متر": .01, "متر": 1}[unit.lower()]
        if key in out and out[key] != value:
            raise ValueError(f"مقادیر متعارض برای «{label}» ثبت شده است")
        out[key] = value
    return out

def _extract_code(text: str):
    compact = re.sub(r"\s+"," ",text.lower())
    for label,value in sorted({**ALIASES,**LATIN_ALIASES}.items(), key=lambda x:-len(x[0])):
        if label.lower() in compact: return value
    raise ValueError("نوع عملیات مشخص نیست؛ مثال: «ستون: تعداد=12، عرض=0.5، عمق=0.5، ارتفاع=3»")

def parse_manual_entry(text: str) -> ManualEntry:
    raw = text.strip()
    if not raw: raise ValueError("ورودی متره خالی است.")
    normalized = _normalise(raw)
    code,fields = _extract_code(normalized)
    params = _extract_named(normalized)
    # Compact column syntax: «12 ستون 50x50 ارتفاع 3» (cm is detected from the text).
    if code == "column":
        dims = re.search(rf"({_NUMBER})\s*(mm|cm|m)?\s*x\s*({_NUMBER})\s*(mm|cm|m)?(?!\w)", normalized, re.IGNORECASE)
        if dims:
            count_match = re.search(rf"({_NUMBER})\s+(?:ستون|column)\b", normalized, re.IGNORECASE)
            if count_match:
                params.setdefault("count", _number(count_match.group(1)))
            first, first_unit, second, second_unit = dims.groups()
            shared_unit = first_unit or second_unit or "m"
            for key, token, unit in (("width", first, first_unit), ("depth", second, second_unit)):
                if "," in token:
                    raise ValueError("جداکننده ابعاد مبهم است؛ از ممیز فارسی یا نقطه استفاده کنید")
                value = _number(token) * {"mm": .001, "cm": .01, "m": 1}[(unit or shared_unit).lower()]
                if key in params and params[key] != value:
                    raise ValueError("ابعاد کوتاه و ورودی نام‌گذاری‌شده متعارض هستند")
                params[key] = value
    for key, value in params.items():
        if not math.isfinite(value):
            raise ValueError(f"{key} باید متناهی باشد")
        if value < 0:
            raise ValueError(f"{key} نمی‌تواند منفی باشد")
        if key == "count" and not value.is_integer():
            raise ValueError("تعداد باید عدد صحیح باشد")
    missing = tuple(name for name in fields if name not in params or (params[name] < 0 if name == "openings" else params[name] <= 0))
    return ManualEntry(code, params, missing, raw)

def parse_manual_batch(text: str) -> tuple[ManualEntry,...]:
    lines = tuple(x.strip() for x in re.split(r"[\n;]+",text) if x.strip())
    if not lines: raise ValueError("هیچ ردیف متره‌ای وارد نشده است.")
    return tuple(parse_manual_entry(line) for line in lines)
