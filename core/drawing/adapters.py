"""Real drawing-source adapters for the P79 Drawing Intelligence boundary.

Adapters are deliberately source-specific and dependency-aware. They convert
DXF/DWG/PDF/IFC sources into the canonical DrawingPrimitive model used by P78.
No adapter invents engineering dimensions that are not present in the source.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .models import DrawingPrimitive


@dataclass(frozen=True)
class DrawingSource:
    path: Path
    kind: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AdapterResult:
    source: DrawingSource
    primitives: tuple[DrawingPrimitive, ...]
    warnings: tuple[str, ...] = ()


class DrawingAdapter(Protocol):
    extensions: tuple[str, ...]

    def read(self, path: str | Path) -> AdapterResult:
        ...


def _path(path: str | Path) -> Path:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if not p.is_file():
        raise ValueError(f"drawing source must be a file: {p}")
    return p


class DXFAdapter:
    extensions = (".dxf",)

    def read(self, path: str | Path) -> AdapterResult:
        p = _path(path)
        try:
            import ezdxf
        except ImportError as exc:
            raise RuntimeError("Install ezdxf to read DXF sources offline") from exc

        doc = ezdxf.readfile(str(p))
        primitives: list[DrawingPrimitive] = []
        for index, entity in enumerate(doc.modelspace(), 1):
            kind = entity.dxftype().upper()
            layer = str(getattr(entity.dxf, "layer", "") or "")
            source_id = f"dxf:{p.name}:{getattr(entity.dxf, 'handle', None) or index}"
            d = entity.dxf

            if kind == "LINE":
                primitives.append(
                    DrawingPrimitive(
                        "line",
                        x=float(d.start.x), y=float(d.start.y),
                        x2=float(d.end.x), y2=float(d.end.y),
                        layer=layer, source_id=source_id,
                    )
                )
            elif kind in {"TEXT", "MTEXT"}:
                text = str(getattr(entity, "text", "") or getattr(d, "text", "") or "")
                insert = getattr(d, "insert", None)
                x = float(insert.x) if insert is not None else 0.0
                y = float(insert.y) if insert is not None else 0.0
                primitives.append(
                    DrawingPrimitive("text", x=x, y=y, text=text,
                                     layer=layer, source_id=source_id)
                )
            elif kind in {"LWPOLYLINE", "POLYLINE"}:
                points: list[tuple[float, float]] = []
                try:
                    if kind == "LWPOLYLINE":
                        points = [(float(x), float(y)) for x, y, *_ in entity.get_points()]
                    else:
                        points = [(float(v.dxf.location.x), float(v.dxf.location.y))
                                  for v in entity.vertices]
                except Exception:
                    points = []
                for segment, (a, b) in enumerate(zip(points, points[1:]), 1):
                    primitives.append(
                        DrawingPrimitive(
                            "polyline", x=a[0], y=a[1], x2=b[0], y2=b[1],
                            layer=layer, source_id=f"{source_id}:{segment}",
                        )
                    )
            elif kind == "CIRCLE":
                center = d.center
                primitives.append(
                    DrawingPrimitive(
                        "circle", x=float(center.x), y=float(center.y),
                        width=float(d.radius) * 2, height=float(d.radius) * 2,
                        layer=layer, source_id=source_id,
                    )
                )

        return AdapterResult(
            DrawingSource(p, "dxf", {"entity_count": len(primitives)}),
            tuple(primitives),
        )


class DWGAdapter:
    extensions = (".dwg",)

    def __init__(self, converter=None):
        self.converter = converter

    def read(self, path: str | Path) -> AdapterResult:
        p = _path(path)
        from core.drawings.dwg_converter import OfflineDWGConverter

        converter = self.converter or OfflineDWGConverter()
        result = converter.convert(p)
        dxf_result = DXFAdapter().read(result.output)
        warnings = tuple(dxf_result.warnings) + (
            f"DWG converted through offline converter: {result.converter}",
        )
        source = DrawingSource(
            p, "dwg",
            {"converter": result.converter, "converted_path": str(result.output)},
        )
        return AdapterResult(source, dxf_result.primitives, warnings)


class PDFAdapter:
    extensions = (".pdf",)

    def read(self, path: str | Path) -> AdapterResult:
        p = _path(path)
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Install pypdf to read PDF drawing sources offline") from exc

        reader = PdfReader(str(p))
        primitives: list[DrawingPrimitive] = []
        for page_no, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            for line_no, line in enumerate(text.splitlines(), 1):
                value = line.strip()
                if not value:
                    continue
                primitives.append(
                    DrawingPrimitive(
                        "text", text=value, layer="PDF_TEXT",
                        source_id=f"pdf:{p.name}:p{page_no}:t{line_no}",
                        properties={"page": page_no},
                    )
                )
        return AdapterResult(
            DrawingSource(p, "pdf", {"page_count": len(reader.pages)}),
            tuple(primitives),
            ("PDF text extraction does not infer missing graphical dimensions.",),
        )


class IFCAdapter:
    extensions = (".ifc",)

    _TYPE_MAP = {
        "IFCBEAM": "beam",
        "IFCCOLUMN": "column",
        "IFCSLAB": "slab",
        "IFCWALL": "wall",
        "IFCFOOTING": "isolated",
    }

    def read(self, path: str | Path) -> AdapterResult:
        p = _path(path)
        try:
            import ifcopenshell
        except ImportError as exc:
            raise RuntimeError("Install ifcopenshell to read IFC sources offline") from exc

        model = ifcopenshell.open(str(p))
        primitives: list[DrawingPrimitive] = []
        for obj in model.by_type("IfcProduct"):
            ifc_type = str(obj.is_a()).upper()
            kind = self._TYPE_MAP.get(ifc_type)
            if not kind:
                continue
            name = str(getattr(obj, "Name", None) or "")
            layer = kind
            source_id = f"ifc:{p.name}:{obj.GlobalId}"
            primitives.append(
                DrawingPrimitive(
                    "bim",
                    text=name,
                    layer=layer,
                    source_id=source_id,
                    properties={"ifc_type": ifc_type, "global_id": obj.GlobalId},
                )
            )

        return AdapterResult(
            DrawingSource(p, "ifc", {"product_count": len(primitives)}),
            tuple(primitives),
            ("IFC adapter maps typed structural products; absent dimensions remain unresolved.",),
        )


class DrawingAdapterRegistry:
    def __init__(self, adapters: tuple[DrawingAdapter, ...] | None = None):
        from .pdf_graphics import GraphicalPDFAdapter
        self.adapters = adapters or (DXFAdapter(), DWGAdapter(), GraphicalPDFAdapter(), PDFAdapter(), IFCAdapter())

    def for_path(self, path: str | Path) -> DrawingAdapter:
        suffix = Path(path).suffix.casefold()
        for adapter in self.adapters:
            if suffix in adapter.extensions:
                return adapter
        supported = ", ".join(sorted(ext for a in self.adapters for ext in a.extensions))
        raise ValueError(f"unsupported drawing source {suffix!r}; supported: {supported}")

    def read(self, path: str | Path) -> AdapterResult:
        return self.for_path(path).read(path)
