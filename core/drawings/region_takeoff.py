"""Geometry adapters for converting a selected viewport rectangle to takeoff polygon points."""
from __future__ import annotations

import math


def rectangle_to_points(left: float, top: float, right: float, bottom: float) -> tuple[tuple[float, float], ...]:
    """Return a normalized, non-zero rectangle as polygon vertices in scene coordinates."""
    values = tuple(float(v) for v in (left, top, right, bottom))
    if not all(math.isfinite(v) for v in values):
        raise ValueError("مختصات ناحیه باید عددی و متناهی باشند")
    x1, y1, x2, y2 = values
    x_min, x_max = sorted((x1, x2))
    y_min, y_max = sorted((y1, y2))
    if x_max <= x_min or y_max <= y_min:
        raise ValueError("ناحیه انتخاب‌شده باید عرض و ارتفاع مثبت داشته باشد")
    return (
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
    )


def calibrated_rectangle_area(
    left: float, top: float, right: float, bottom: float, meters_per_pixel: float
) -> float:
    """Preview a rectangle's area only with an explicit, finite calibration factor."""
    rectangle_to_points(left, top, right, bottom)
    factor = float(meters_per_pixel)
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError("برای محاسبه مساحت، کالیبراسیون معتبر و مثبت لازم است")
    width = abs(float(right) - float(left))
    height = abs(float(bottom) - float(top))
    area = width * height * factor * factor
    if not math.isfinite(area) or area <= 0:
        raise ValueError("مساحت پیش‌نمایش معتبر نیست")
    return area
