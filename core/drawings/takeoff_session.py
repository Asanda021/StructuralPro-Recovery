"""Stateful drawing takeoff session for the Windows graphical workflow.

The session is UI-independent and keeps every measurement traceable to a drawing
source/page.  It provides calibration, measurement editing, undo/redo, source
links, validation and BOQ-ready rows without introducing a GUI dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from copy import deepcopy
import json
import math
from typing import Any, Iterable

from core.drawings.graphical_takeoff import Point, polygon_area, polyline_length, snap_point
from core.drawings.markup import Markup, MarkupStore


@dataclass(frozen=True)
class TakeoffItem:
    id: str
    kind: str
    quantity: float
    unit: str
    page: int
    label: str = ""
    takeoff_code: str = ""
    source: str = ""
    source_ref: str = ""
    geometry: tuple[tuple[float, float], ...] = ()
    formula: str = ""
    confidence: float = 1.0
    holes: tuple[tuple[tuple[float, float], ...], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Calibration:
    meters_per_pixel: float
    page: int
    reference_pixels: float
    reference_meters: float
    source: str = "manual-reference"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DrawingTakeoffSession:
    """Auditable editing session for a drawing and its takeoff items."""

    def __init__(self, drawing_source: str = ""):
        self.drawing_source = str(drawing_source or "")
        self.calibration: Calibration | None = None
        self.calibrations: dict[int, Calibration] = {}
        self.items: list[TakeoffItem] = []
        self.markups = MarkupStore()
        self.current_page = 1
        self._counter = 0
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def set_page(self, page: int) -> int:
        page = self._page_number(page)
        if page < 1:
            raise ValueError("page must be positive")
        self.current_page = page
        self.calibration = self.calibrations.get(page)
        return page

    def calibrate(self, page: int, reference_pixels: float, reference_meters: float) -> Calibration:
        page = self._page_number(page)
        if isinstance(reference_pixels, bool) or isinstance(reference_meters, bool):
            raise ValueError("مرجع کالیبراسیون باید عددی باشد")
        px = float(reference_pixels)
        meters = float(reference_meters)
        if page < 1 or not math.isfinite(px) or not math.isfinite(meters) or px <= 0 or meters <= 0:
            raise ValueError("calibration values must be positive and finite")
        previous = self.calibrations.get(page)
        if previous and not math.isclose(previous.meters_per_pixel, meters / px, rel_tol=1e-12) and any(
            item.page == page and item.kind in {"length", "area"} for item in self.items
        ):
            raise ValueError("این صفحه متره ثبت‌شده دارد؛ پیش از تغییر مقیاس، متره‌های وابسته را حذف و با مقیاس جدید اندازه‌گیری کنید")
        self._record()
        calibration = Calibration(meters / px, page, px, meters)
        self.calibrations[page] = calibration
        self.calibration = self.calibrations.get(self.current_page)
        self._redo.clear()
        return calibration

    def set_meters_per_pixel(self, meters_per_pixel: float, page: int | None = None) -> Calibration:
        factor = float(meters_per_pixel)
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("meters_per_pixel must be positive and finite")
        page = self.current_page if page is None else int(page)
        return self.calibrate(page, 1.0, factor)

    def _factor_for(self, page: int) -> float:
        calibration = self.calibrations.get(int(page))
        if calibration is None:
            raise ValueError(f"مقیاس صفحه {page} کالیبره نشده است؛ قبل از متره همین صفحه را کالیبره کن")
        return float(calibration.meters_per_pixel)

    def _record(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > 50:
            self._undo.pop(0)

    def _snapshot(self) -> dict[str, Any]:
        return {
            "calibration": self.calibration.to_dict() if self.calibration else None,
            "calibrations": {str(page): value.to_dict() for page, value in self.calibrations.items()},
            "items": [x.to_dict() for x in self.items],
            "markups": [x.to_dict() for x in self.markups.items],
            "current_page": self.current_page,
            "counter": self._counter,
        }

    def _restore(self, state: dict[str, Any]) -> None:
        raw = state.get("calibration")
        self.calibration = Calibration(**raw) if raw else None
        saved_calibrations = state.get("calibrations")
        if isinstance(saved_calibrations, dict):
            self.calibrations = {int(page): Calibration(**value) for page, value in saved_calibrations.items()}
        else:
            self.calibrations = {self.calibration.page: self.calibration} if self.calibration else {}
        self.calibration = self.calibrations.get(int(state.get("current_page", 1)))
        self.items = [
            TakeoffItem(
                id=str(x["id"]), kind=str(x["kind"]), quantity=float(x["quantity"]),
                unit=str(x["unit"]), page=int(x["page"]), label=str(x.get("label", "")),
                takeoff_code=str(x.get("takeoff_code", "")), source=str(x.get("source", "")),
                source_ref=str(x.get("source_ref", "")),
                geometry=tuple(tuple(p) for p in x.get("geometry", ())),
                formula=str(x.get("formula", "")), confidence=float(x.get("confidence", 1.0)),
                holes=tuple(tuple(tuple(p) for p in hole) for hole in x.get("holes", ())),
            )
            for x in state.get("items", [])
        ]
        self.markups.items = [Markup(**x) for x in state.get("markups", [])]
        self.current_page = int(state.get("current_page", 1))
        self._counter = int(state.get("counter", len(self.items)))

    def _commit(self) -> None:
        self._redo.clear()

    def _next_id(self) -> str:
        self._counter += 1
        return f"TO-{self._counter:05d}"

    def _source_ref(self, page: int, item_id: str) -> str:
        source = self.drawing_source or "drawing"
        return f"{source}#page={page}&takeoff={item_id}"

    @staticmethod
    def _page_number(value) -> int:
        if isinstance(value, bool):
            raise ValueError("شماره صفحه باید عدد صحیح مثبت باشد")
        number = float(value)
        if not math.isfinite(number) or not number.is_integer() or number < 1:
            raise ValueError("شماره صفحه باید عدد صحیح مثبت باشد")
        return int(number)

    @staticmethod
    def _ensure_finite(value: float) -> float:
        if isinstance(value, bool):
            raise ValueError("مقدار متره نمی‌تواند مقدار منطقی باشد")
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise ValueError("quantity must be finite and non-negative")
        return value

    @staticmethod
    def _ensure_confidence(value: float) -> float:
        value = float(value)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        return value

    def _ensure_source_unique(self, source: str, ignore_id: str | None = None) -> None:
        source = str(source or "").strip()
        if not source:
            return
        if any(x.source == source and x.id != ignore_id for x in self.items):
            raise ValueError(f"منبع متره تکراری و مستعد دوباره‌شماری: {source}")

    def add_length(
        self, points: Iterable[Point], *, page: int | None = None, label: str = "",
        takeoff_code: str = "", source: str = "", confidence: float = 1.0,
    ) -> TakeoffItem:
        pts = tuple(points)
        if len(pts) < 2:
            raise ValueError("طول حداقل به دو نقطه نیاز دارد")
        page = self.current_page if page is None else self._page_number(page)
        factor = self._factor_for(page)
        px = polyline_length(pts)
        quantity = self._ensure_finite(px * factor)
        self._ensure_source_unique(source)
        confidence = self._ensure_confidence(confidence)
        self._record()
        item_id = self._next_id()
        item = TakeoffItem(
            item_id, "length", quantity, "m", page, label, takeoff_code, source,
            self._source_ref(page, item_id), tuple((p.x, p.y) for p in pts),
            f"{px:g} px × {factor:g} m/px", self._ensure_confidence(confidence),
        )
        self.items.append(item)
        self._commit()
        return item

    def add_area(
        self, points: Iterable[Point], *, holes: Iterable[Iterable[Point]] = (),
        page: int | None = None, label: str = "", takeoff_code: str = "",
        source: str = "", confidence: float = 1.0,
    ) -> TakeoffItem:
        pts = tuple(points)
        if len(pts) < 3:
            raise ValueError("مساحت حداقل به سه نقطه نیاز دارد")
        page = self.current_page if page is None else self._page_number(page)
        factor = self._factor_for(page)
        gross_px = polygon_area(pts)
        hole_points = tuple(tuple(h) for h in holes)
        if any(len(hole) < 3 for hole in hole_points):
            raise ValueError("هندسه هر بازشو حداقل به سه نقطه نیاز دارد")
        holes_px = sum(polygon_area(h) for h in hole_points)
        net_px = gross_px - holes_px
        if net_px < -1e-9:
            raise ValueError("مجموع بازشوها از مساحت اصلی بیشتر است")
        quantity = self._ensure_finite(max(0.0, net_px) * factor * factor)
        self._ensure_source_unique(source)
        confidence = self._ensure_confidence(confidence)
        self._record()
        item_id = self._next_id()
        item = TakeoffItem(
            item_id, "area", quantity, "m2", page, label, takeoff_code, source,
            self._source_ref(page, item_id), tuple((p.x, p.y) for p in pts),
            f"{max(0.0, net_px):g} px² × {factor:g}²", self._ensure_confidence(confidence),
            tuple(tuple((p.x, p.y) for p in hole) for hole in hole_points),
        )
        self.items.append(item)
        self._commit()
        return item

    def add_count(
        self, count: int = 1, *, page: int | None = None, label: str = "",
        takeoff_code: str = "", source: str = "", confidence: float = 1.0,
    ) -> TakeoffItem:
        page = self.current_page if page is None else self._page_number(page)
        quantity = self._ensure_finite(count)
        if quantity <= 0:
            raise ValueError("count must be positive")
        if not quantity.is_integer():
            raise ValueError("count must be an integer")
        self._ensure_source_unique(source)
        confidence = self._ensure_confidence(confidence)
        self._record()
        item_id = self._next_id()
        item = TakeoffItem(
            item_id, "count", quantity, "عدد", page, label, takeoff_code, source,
            self._source_ref(page, item_id), (), f"{int(quantity)} عدد", self._ensure_confidence(confidence),
        )
        self.items.append(item)
        self._commit()
        return item

    def edit(self, item_id: str, **changes: Any) -> TakeoffItem:
        index = next((i for i, x in enumerate(self.items) if x.id == item_id), None)
        if index is None:
            raise KeyError(item_id)
        old = self.items[index]
        data = old.to_dict()
        data.update(changes)
        if "quantity" in data:
            data["quantity"] = self._ensure_finite(data["quantity"])
        if "confidence" in data:
            data["confidence"] = self._ensure_confidence(data["confidence"])
        if "page" in data:
            data["page"] = int(data["page"])
            if data["page"] < 1:
                raise ValueError("page must be positive")
        if "source" in data:
            self._ensure_source_unique(str(data["source"]), ignore_id=item_id)
        if "geometry" in data:
            data["geometry"] = tuple(tuple(p) for p in data["geometry"])
        self._record()
        self.items[index] = TakeoffItem(**data)
        self._commit()
        return self.items[index]

    def remove(self, item_id: str) -> bool:
        index = next((i for i, x in enumerate(self.items) if x.id == item_id), None)
        if index is None:
            return False
        self._record()
        self.items.pop(index)
        self._commit()
        return True

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        return True

    def add_note(self, text: str, x: float, y: float, *, page: int | None = None) -> Markup:
        text = str(text).strip()
        if not text:
            raise ValueError("یادداشت نمی‌تواند خالی باشد")
        page = self.current_page if page is None else int(page)
        self._record()
        markup = Markup(f"MK-{len(self.markups.items)+1:04d}", "note", text, float(x), float(y), page=page)
        self.markups.add(markup)
        self._commit()
        return markup

    def for_page(self, page: int | None = None) -> list[TakeoffItem]:
        page = self.current_page if page is None else int(page)
        return [x for x in self.items if x.page == page]

    def find(self, item_id: str) -> TakeoffItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def snap(self, point: Point, candidates: Iterable[Point], tolerance: float = 8.0) -> Point:
        return snap_point(point, candidates, float(tolerance))

    def validate(self) -> dict[str, Any]:
        issues: list[str] = []
        ids = [x.id for x in self.items]
        if any(not str(value).strip() for value in ids):
            issues.append("شناسه متره خالی است")
        if len(ids) != len(set(ids)):
            issues.append("شناسه متره تکراری است")
        sources = [x.source for x in self.items if x.source]
        if len(sources) != len(set(sources)):
            issues.append("منبع متره تکراری است")
        for page, calibration in self.calibrations.items():
            if (page < 1 or calibration.page != page
                    or not math.isfinite(calibration.meters_per_pixel) or calibration.meters_per_pixel <= 0
                    or not math.isfinite(calibration.reference_pixels) or calibration.reference_pixels <= 0
                    or not math.isfinite(calibration.reference_meters) or calibration.reference_meters <= 0):
                issues.append(f"کالیبراسیون صفحه {page} نامعتبر است")
            elif not math.isclose(calibration.meters_per_pixel,
                                  calibration.reference_meters / calibration.reference_pixels, rel_tol=1e-12):
                issues.append(f"مقیاس صفحه {page} با مرجع کالیبراسیون مطابقت ندارد")
        for item in self.items:
            if item.page < 1 or not math.isfinite(item.quantity) or item.quantity < 0:
                issues.append(f"متره {item.id} مقدار نامعتبر دارد")
            if not math.isfinite(item.confidence) or not 0.0 <= item.confidence <= 1.0:
                issues.append(f"متره {item.id} سطح اطمینان نامعتبر دارد")
            if item.kind in {"length", "area"} and item.page not in self.calibrations:
                issues.append(f"متره {item.id} بدون مقیاس همان صفحه ثبت شده است")
        return {"valid": not issues, "issues": issues, "item_count": len(self.items)}

    def boq_rows(self, selected_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
        from core.drawings.takeoff_bridge import validate_session_payload
        validation = validate_session_payload(self.to_dict())
        if not validation["valid"]:
            raise ValueError("نشست نقشه معتبر نیست: " + "؛ ".join(validation["issues"]))
        selected = None if selected_ids is None else set(selected_ids)
        if selected is not None and (not selected or selected - {item.id for item in self.items}):
            raise ValueError("انتخاب متره خالی است یا شناسه متره در نشست وجود ندارد")
        rows = []
        for item in self.items:
            if selected is not None and item.id not in selected:
                continue
            rows.append({
                "source": item.source_ref,
                "source_id": item.source_ref,
                "description": item.label or item.takeoff_code or item.kind,
                "quantity": item.quantity,
                "unit": item.unit,
                "price_code": item.takeoff_code or None,
                "takeoff_id": item.id,
                "page": item.page,
                "formula": item.formula,
                "confidence": item.confidence,
                "needs_confirmation": False,
            })
        return rows

    def revision_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "id": x.id, "page": x.page, "kind": x.kind, "quantity": x.quantity,
                "unit": x.unit, "label": x.label, "takeoff_code": x.takeoff_code,
                "source": x.source_ref, "geometry": x.geometry,
            }
            for x in self.items
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "drawing_source": self.drawing_source,
            "calibration": self.calibration.to_dict() if self.calibration else None,
            "calibrations": {str(page): value.to_dict() for page, value in self.calibrations.items()},
            "current_page": self.current_page,
            "items": [x.to_dict() for x in self.items],
            "markups": [x.to_dict() for x in self.markups.items],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DrawingTakeoffSession":
        session = cls(data.get("drawing_source", ""))
        raw_calibrations = data.get("calibrations")
        if isinstance(raw_calibrations, dict):
            for page_key, value in raw_calibrations.items():
                page_number = cls._page_number(page_key)
                calibration = Calibration(**value)
                if calibration.page != page_number:
                    raise ValueError("شماره صفحه کالیبراسیون با کلید ذخیره‌شده مطابقت ندارد")
                session.calibrations[page_number] = calibration
        else:
            raw = data.get("calibration")
            if raw:
                calibration = Calibration(**raw)
                session.calibrations[calibration.page] = calibration
        for page_number, calibration in session.calibrations.items():
            values = (calibration.meters_per_pixel, calibration.reference_pixels, calibration.reference_meters)
            if page_number < 1 or any(not math.isfinite(float(v)) or float(v) <= 0 for v in values):
                raise ValueError("فایل متره دارای کالیبراسیون نامعتبر است")
        session.current_page = cls._page_number(data.get("current_page", 1))
        if session.current_page < 1:
            raise ValueError("شماره صفحه جاری باید مثبت باشد")
        session.calibration = session.calibrations.get(session.current_page)
        session.items = [
            TakeoffItem(
                id=str(x["id"]), kind=str(x["kind"]), quantity=float(x["quantity"]),
                unit=str(x["unit"]), page=cls._page_number(x["page"]), label=str(x.get("label", "")),
                takeoff_code=str(x.get("takeoff_code", "")), source=str(x.get("source", "")),
                source_ref=str(x.get("source_ref", "")),
                geometry=tuple(tuple(p) for p in x.get("geometry", ())),
                formula=str(x.get("formula", "")), confidence=float(x.get("confidence", 1.0)),
                holes=tuple(tuple(tuple(p) for p in hole) for hole in x.get("holes", ())),
            )
            for x in data.get("items", [])
        ]
        session.markups.items = [Markup(**x) for x in data.get("markups", [])]
        session._counter = max([int(str(x.id).split("-")[-1]) for x in session.items] or [0])
        return session
