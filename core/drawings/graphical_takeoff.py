"Production-grade, deterministic graphical takeoff primitives with fail-closed input validation."
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import hypot, isfinite, sqrt
import re
from typing import Iterable


def _number(value, name, minimum=None):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _points(points, minimum):
    points = list(points)
    if len(points) < minimum:
        raise ValueError(f"at least {minimum} points are required")
    for i, point in enumerate(points):
        _number(point.x, f"point[{i}].x")
        _number(point.y, f"point[{i}].y")
    return points


@dataclass(frozen=True)
class ScaleCalibration:
    ratio: float
    drawing_unit: str = "cm"
    model_unit: str = "m"
    label: str = ""
    source: str = "manual"

    @classmethod
    def parse(cls, value: str | float, drawing_unit="cm", model_unit="m"):
        if isinstance(value, bool):
            raise ValueError("مقیاس باید عددی و متناهی باشد")
        if isinstance(value, (int, float)):
            ratio = _number(value, "scale ratio", 0.0)
        else:
            match = re.search(r"1\s*[:/]\s*(\d+(?:\.\d+)?)", str(value))
            if not match:
                raise ValueError("مقیاس باید مانند 1:100 باشد")
            ratio = _number(match.group(1), "scale ratio", 0.0)
        if ratio <= 0:
            raise ValueError("مقیاس باید بزرگ‌تر از صفر باشد")
        if drawing_unit not in {"mm", "cm", "m"}:
            raise ValueError(f"واحد نقشه پشتیبانی نمی‌شود: {drawing_unit}")
        if model_unit not in {"mm", "cm", "m"}:
            raise ValueError(f"واحد مدل پشتیبانی نمی‌شود: {model_unit}")
        return cls(ratio, drawing_unit, model_unit, str(value), "manual")

    def length(self, drawing_distance: float) -> float:
        distance = _number(drawing_distance, "drawing distance", 0.0)
        drawing_to_m = {"mm": 0.001, "cm": 0.01, "m": 1.0}[self.drawing_unit]
        metres = distance * self.ratio * drawing_to_m
        model_from_m = {"mm": 1000.0, "cm": 100.0, "m": 1.0}[self.model_unit]
        result = metres * model_from_m
        if not isfinite(result):
            raise ValueError("نتیجه طول باید متناهی باشد")
        return result

    def area(self, drawing_area: float) -> float:
        area = _number(drawing_area, "drawing area", 0.0)
        result = self.length(sqrt(area)) ** 2
        if not isfinite(result):
            raise ValueError("نتیجه مساحت باید متناهی باشد")
        return result


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class GraphicMeasurement:
    id: str
    kind: str
    value: float
    unit: str
    page: int | None = None
    layer: str | None = None
    label: str = ""
    source: str = "manual"
    confidence: float = 1.0
    geometry: tuple = ()
    formula: str = ""
    def to_dict(self): return asdict(self)


def polyline_length(points: Iterable[Point], closed=False) -> float:
    pts = _points(points, 2)
    total = sum(hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y)
                for i in range(len(pts) - 1))
    if closed and len(pts) > 2:
        total += hypot(pts[0].x - pts[-1].x, pts[0].y - pts[-1].y)
    if not isfinite(total):
        raise ValueError("طول هندسی باید متناهی باشد")
    return total


def polygon_area(points: Iterable[Point]) -> float:
    pts = list(points)
    if len(pts) < 3:
        return 0.0
    pts = _points(pts, 3)
    area = abs(sum(pts[i].x * pts[(i + 1) % len(pts)].y
                   - pts[(i + 1) % len(pts)].x * pts[i].y
                   for i in range(len(pts))) / 2)
    if not isfinite(area):
        raise ValueError("مساحت هندسی باید متناهی باشد")
    return area


def subtract_areas(gross: float, holes: Iterable[float]) -> float:
    gross = _number(gross, "gross area", 0.0)
    holes = [_number(value, "opening area", 0.0) for value in holes]
    value = gross - sum(holes)
    if not isfinite(value):
        raise ValueError("مساحت خالص باید متناهی باشد")
    if value < -1e-9:
        raise ValueError("مجموع بازشوها از مساحت اصلی بیشتر است")
    return max(0.0, value)


def snap_point(point: Point, candidates: Iterable[Point], tolerance: float) -> Point:
    _number(point.x, "point.x")
    _number(point.y, "point.y")
    tolerance = _number(tolerance, "snap tolerance", 0.0)
    candidate_points = list(candidates)
    if not candidate_points:
        return point
    pts = _points(candidate_points, 1)
    best = min(pts, key=lambda p: hypot(p.x - point.x, p.y - point.y))
    distance = hypot(best.x - point.x, best.y - point.y)
    if not isfinite(distance):
        raise ValueError("فاصله snap باید متناهی باشد")
    return best if distance <= tolerance else point


class MeasurementStore:
    def __init__(self): self._items = []; self._counter = 0

    def add_length(self, points, scale: ScaleCalibration, **meta):
        pts = tuple(points)
        distance = polyline_length(pts)
        value = scale.length(distance)
        item_id = f"M{self._counter + 1:05d}"
        item = GraphicMeasurement(item_id, "length", value, scale.model_unit,
            geometry=tuple((p.x, p.y) for p in pts),
            formula=f"{distance:g} × {scale.ratio:g}", **meta)
        self._add(item)
        self._counter += 1
        return item

    def add_area(self, points, scale: ScaleCalibration, holes=(), **meta):
        pts = tuple(points)
        if len(pts) < 3:
            raise ValueError("برای متره مساحت حداقل سه نقطه لازم است")
        gross = scale.area(polygon_area(pts))
        openings = [scale.area(_number(value, "opening area", 0.0)) for value in holes]
        value = subtract_areas(gross, openings)
        item_id = f"M{self._counter + 1:05d}"
        area_unit = {"mm": "mm2", "cm": "cm2", "m": "m2"}[scale.model_unit]
        item = GraphicMeasurement(item_id, "area", value, area_unit,
            geometry=tuple((p.x, p.y) for p in pts),
            formula=f"مساحت ناخالص {gross:g} - بازشوها {sum(openings):g}", **meta)
        self._add(item)
        self._counter += 1
        return item

    def add_count(self, count: int, **meta):
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("تعداد باید عدد صحیح باشد")
        if count < 0:
            raise ValueError("تعداد نمی‌تواند منفی باشد")
        item = GraphicMeasurement(f"M{self._counter + 1:05d}", "count",
                                  float(count), "عدد", **meta)
        self._add(item)
        self._counter += 1
        return item

    def _add(self, item):
        _number(item.value, "measurement value", 0.0)
        if not item.unit.strip():
            raise ValueError("measurement unit is required")
        self._items.append(item)

    def all(self): return list(self._items)
    def clear(self): self._items.clear()
    def summary(self):
        out = {}
        for item in self._items:
            out[item.unit] = out.get(item.unit, 0) + item.value
        return {"count": len(self._items), "by_unit": out}


def extract_scale_candidates(text: str):
    return [float(value) for value in re.findall(r"1\s*[:/]\s*(\d+(?:\.\d+)?)", text or "")]
