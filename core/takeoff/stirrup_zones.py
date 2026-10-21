"""Reviewed, non-overlapping physical stirrup zones for one concrete beam.

Do not derive stirrup counts from spacing. Engineers must enter both the
first/last physical bar stations and the exact reviewed count and cut length.
"""
from __future__ import annotations

import math
from typing import Any

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _n(value: Any, label: str, *, allow_zero: bool = False, integer: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} باید عدد معتبر باشد")
    try:
        x = float(value.translate(_DIGITS) if isinstance(value, str) else value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{label} باید عدد معتبر باشد") from exc
    if not math.isfinite(x) or x < 0 or (x == 0 and not allow_zero):
        raise ValueError(f"{label} باید {'نامنفی' if allow_zero else 'مثبت'} و متناهی باشد")
    if integer and not x.is_integer():
        raise ValueError(f"{label} باید عدد صحیح باشد")
    return x


def validate_stirrup_zones(zones: list[dict[str, Any]], beam_length_m: Any) -> list[dict[str, Any]]:
    """Check exact coverage and placement without computing counts or cutting lengths.

    Intervals cover the beam [0,L] exactly; neighboring zones may share an
    interval boundary but cannot share the same physical bar station.
    Stations are absolute distances from the beam reference start, in metres.
    """
    length = _n(beam_length_m, "طول تیر")
    if not isinstance(zones, list) or not zones:
        raise ValueError("حداقل یک ناحیه خاموت دارای دیتایل معتبر لازم است")
    results: list[dict[str, Any]] = []
    for index, z in enumerate(zones, 1):
        if not isinstance(z, dict):
            raise ValueError(f"ناحیه {index}: ساختار اطلاعات نامعتبر است")
        title = f"ناحیه {index}"
        name = str(z.get("name", "")).strip() or title
        start = _n(z.get("start_m"), f"شروع {name}", allow_zero=True)
        end = _n(z.get("end_m"), f"پایان {name}")
        spacing = _n(z.get("spacing_m"), f"فاصله خاموت {name}")
        count = int(_n(z.get("count"), f"تعداد خاموت {name}", integer=True))
        first = _n(z.get("first_bar_m"), f"محل اولین خاموت {name}", allow_zero=True)
        last = _n(z.get("last_bar_m"), f"محل آخرین خاموت {name}", allow_zero=True)
        cut = _n(z.get("cut_length_m"), f"طول برش خاموت {name}")
        unit_weight = _n(z.get("unit_weight_kg_m"), f"وزن واحد خاموت {name}")
        weight_source = z.get("unit_weight_source")
        if not isinstance(weight_source, str) or not weight_source.strip():
            raise ValueError(f"منبع وزن واحد خاموت {name} الزامی است")
        ref = z.get("source_ref")
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError(f"مرجع دیتایل {name} الزامی است")
        tolerance = max(1e-8, length * 1e-9)
        if end <= start + tolerance or end > length + tolerance:
            raise ValueError(f"مرز ناحیه {name} خارج از طول تیر یا نامعتبر است")
        if first < start - tolerance or last > end + tolerance or first > last + tolerance:
            raise ValueError(f"محل اولین/آخرین خاموت {name} خارج از ناحیه است")
        travel = (count - 1) * spacing
        if not math.isfinite(travel) or not math.isclose(last - first, travel, abs_tol=tolerance, rel_tol=1e-8):
            raise ValueError(f"تعداد، فاصله و محل خاموت‌های {name} با هم سازگار نیستند")
        if first - start > spacing + tolerance or end - last > spacing + tolerance:
            raise ValueError(f"در ابتدا یا انتهای {name} فاصله بدون پوشش بیش از گام خاموت است")
        results.append({"name": name, "start_m": start, "end_m": end,
                        "spacing_m": spacing, "first_bar_m": first, "last_bar_m": last,
                        "count": count, "cut_length_m": cut,
                        "unit_weight_kg_m": unit_weight,
                        "unit_weight_source": weight_source.strip(),
                        "source_ref": ref.strip()})
    results.sort(key=lambda x: x["start_m"])
    tol = max(1e-8, length * 1e-9)
    if not math.isclose(results[0]["start_m"], 0, abs_tol=tol):
        raise ValueError("شروع ناحیه‌های خاموت باید ابتدای تیر (صفر) باشد")
    if not math.isclose(results[-1]["end_m"], length, abs_tol=tol):
        raise ValueError("ناحیه‌های خاموت باید تا انتهای تیر پوشش داشته باشند")
    for previous, next_zone in zip(results, results[1:]):
        gap = next_zone["start_m"] - previous["end_m"]
        if abs(gap) > tol:
            raise ValueError("ناحیه‌های خاموت دارای هم‌پوشانی یا فاصله پوشش‌داده‌نشده هستند")
        if previous["last_bar_m"] >= next_zone["first_bar_m"] - tol:
            raise ValueError("محل خاموت مشترک دوبار شمرده شده یا ترتیب خاموت‌ها نامعتبر است")
        if (next_zone["first_bar_m"] - previous["last_bar_m"] >
                max(next_zone["spacing_m"], previous["spacing_m"]) + tol):
            raise ValueError("فاصله خاموت در مرز دو ناحیه از فواصل اعلام‌شده بیشتر است")
    return results
