"""Transactional drawing viewer model for PDF/DXF/DWG sources."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math


@dataclass(frozen=True)
class DrawingViewport:
    left: float
    top: float
    width: float
    height: float

    def normalized(self) -> "DrawingViewport":
        if any(not math.isfinite(value) for value in (self.left, self.top, self.width, self.height)):
            raise ValueError("مختصات پنجره بزرگ‌نمایی باید متناهی باشند")
        if self.width == 0 or self.height == 0:
            raise ValueError("پنجره بزرگ‌نمایی باید عرض و ارتفاع مثبت داشته باشد")
        return DrawingViewport(min(self.left, self.left + self.width),
                               min(self.top, self.top + self.height),
                               abs(self.width), abs(self.height))


class DrawingViewerModel:
    """Load a real drawing; failed imports never replace the currently open drawing."""

    def __init__(self, path: str | Path | None = None):
        self.path: Path | None = None
        self.kind: str = ""
        self.page_count = 0
        self.cad_document: Any = None
        self.ifc_document: Any = None
        self.current_page = 1
        if path:
            self.open(path)

    def open(self, path: str | Path) -> "DrawingViewerModel":
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"فایل نقشه پیدا نشد یا فایل معمولی نیست: {p}")
        ext = p.suffix.lower()
        new_kind = ""
        new_page_count = 0
        new_cad_document = None
        new_ifc_document = None
        if ext == ".pdf":
            from core.drawings.pdf_engine import PDFDrawingEngine
            # Close the underlying PDF handle after validating the file and page count.
            with PDFDrawingEngine(p) as engine:
                new_kind = "pdf"
                new_page_count = engine.page_count
                if new_page_count < 1:
                    raise ValueError("PDF هیچ صفحه قابل‌نمایشی ندارد.")
        elif ext in {".dwg", ".dxf"}:
            from core.drawings.dwg_takeoff import DWGTakeoffEngine
            new_cad_document = DWGTakeoffEngine.with_array_support().import_file(p)
            new_kind = "cad"
            new_page_count = 1
        elif ext == ".ifc":
            from core.bim.ifc import DeepIFCAdapter
            try:
                new_ifc_document = DeepIFCAdapter().read_display_meshes(p)
            except ValueError as exc:
                if "ظرفیت نمایش مثلث‌ها" not in str(exc):
                    raise
                # A full-scene failure must not prevent controlled access to
                # a large verified IFC. Preview one REAL member, never imply
                # all source members have been loaded in the 2D projection.
                try:
                    import ifcopenshell
                except ImportError:
                    raise
                source = ifcopenshell.open(str(p))
                candidates = [m for m in source.by_type("IfcElement")
                              if getattr(m, "Representation", None)]
                candidates.sort(key=lambda m: (
                    0 if m.is_a() == "IfcWall" else 1, m.GlobalId
                ))
                if not candidates:
                    raise ValueError("مدل IFC فاقد عضو قابل نمایش است.") from exc
                new_ifc_document = DeepIFCAdapter().read_display_meshes(
                    p, max_triangles=40_000,
                    selected_global_ids=[candidates[0].GlobalId])
                if len(new_ifc_document.source_roster) <= len(new_ifc_document.meshes):
                    raise ValueError("پیش‌نمایش محدود باید شامل هشدار پوشش ناقص باشد.")
            new_kind = "ifc"
            new_page_count = 1
        else:
            raise ValueError("فرمت نقشه باید PDF، DWG، DXF یا IFC باشد.")

        # Commit viewer state only after the complete import/validation succeeds.
        self.path = p
        self.kind = new_kind
        self.page_count = new_page_count
        self.cad_document = new_cad_document
        self.ifc_document = new_ifc_document
        self.current_page = 1
        return self

    @property
    def source_name(self) -> str:
        return self.path.name if self.path else ""

    @property
    def summary(self) -> dict[str, Any]:
        if self.kind == "cad" and self.cad_document is not None:
            from core.drawings.dwg_takeoff import DWGTakeoffEngine
            return DWGTakeoffEngine().summarize(self.cad_document)
        return {"pages": self.page_count, "source": str(self.path or ""), "kind": self.kind}

    def clamp_page(self, page: int) -> int:
        try:
            value = int(page)
        except (TypeError, ValueError) as exc:
            raise ValueError("شماره صفحه باید عدد صحیح باشد.") from exc
        return max(1, min(value, max(1, self.page_count)))
