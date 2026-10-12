"""Offline CAD takeoff engine with layer/block/xref aware extraction."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import math


@dataclass(frozen=True)
class DWGEntity:
    entity_type: str
    layer: str
    handle: str | None
    data: dict[str, Any]


@dataclass
class DWGDocument:
    entities: list[DWGEntity] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    block_counts: dict[str, int] = field(default_factory=dict)
    text_labels: list[str] = field(default_factory=list)
    xrefs: list[str] = field(default_factory=list)
    units: str = "unknown"
    source: str = ""
    format: str = "DXF"


def _xy(v):
    return (float(v[0]), float(v[1]))


_UNIT_FACTORS = {"in": 0.0254, "ft": 0.3048, "mi": 1609.344, "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0}


def cad_unit_factor(unit: str) -> float | None:
    """Return multiplier from a known CAD unit to canonical metres."""
    return _UNIT_FACTORS.get(str(unit or "unknown").lower())


def _poly_metrics(points, closed=False, bulges=None):
    pts = [_xy(p) for p in points]
    if any(not math.isfinite(v) for p in pts for v in p):
        raise ValueError("CAD geometry contains non-finite coordinates")
    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    if closed and len(pts) > 2:
        length += math.dist(pts[-1], pts[0])
    area = 0.0
    if len(pts) > 2 and closed:
        area = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2)
    if bulges is not None:
        signed_area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
                          - pts[(i + 1) % len(pts)][0] * pts[i][1]
                          for i in range(len(pts))) / 2 if closed and len(pts) > 2 else 0.0
        # DXF bulge is tan(signed sweep / 4); use the actual circular arc,
        # never its chord, for engineering length and enclosed area.
        for i in range(len(pts) if closed else max(0, len(pts) - 1)):
            bulge = float(bulges[i])
            if not math.isfinite(bulge):
                raise ValueError("CAD bulge must be finite")
            if bulge == 0:
                continue
            chord = math.dist(pts[i], pts[(i + 1) % len(pts)])
            if chord == 0:
                raise ValueError("CAD arc has coincident endpoints")
            sweep = 4 * math.atan(bulge)
            radius = chord / (2 * abs(math.sin(sweep / 2)))
            length += radius * abs(sweep) - chord
            signed_area += radius * radius * (sweep - math.sin(sweep)) / 2
        area = abs(signed_area) if closed else 0.0
    if not math.isfinite(length) or not math.isfinite(area):
        raise ValueError("CAD geometry result must be finite")
    return length, area


class DWGTakeoffEngine:
    def _read_dxf(self, p: Path) -> DWGDocument:
        try:
            import ezdxf
        except ImportError as exc:
            raise RuntimeError(
                "کتابخانه ezdxf برای تحلیل DXF نصب نیست؛ نصب وابستگی‌های StructuralPro را بررسی کنید."
            ) from exc

        try:
            doc = ezdxf.readfile(str(p))
        except Exception as exc:
            raise RuntimeError(
                f"خواندن فایل CAD شکست خورد؛ فایل ممکن است خراب یا با نسخه/ساختار غیرقابل‌خواندن باشد: {exc}"
            ) from exc

        out = DWGDocument(source=str(p), format="DXF")
        layers = set()
        units_map = {0: "unitless", 1: "in", 2: "ft", 3: "mi", 4: "mm", 5: "cm", 6: "m", 7: "km"}
        raw_units = int(doc.header.get("$INSUNITS", 0) or 0)
        out.units = units_map.get(raw_units, "unknown")
        out.__dict__["unit_name"] = out.units
        try:
            out.xrefs = [str(x) for x in doc.xrefdocpaths]
        except Exception:
            pass

        try:
            entities = doc.modelspace()
            for e in entities:
                typ = e.dxftype()
                layer = str(getattr(e.dxf, "layer", "0"))
                layers.add(layer)
                data = {}

                if typ == "LINE":
                    data["start"] = _xy(e.dxf.start)
                    data["end"] = _xy(e.dxf.end)
                    data["length"] = math.dist(data["start"], data["end"])
                elif typ == "POLYLINE" and (e.is_polygon_mesh or e.is_poly_face_mesh):
                    # Mesh topology is not a 2D polyline. Keep its provenance and
                    # vertices, but never fabricate chord lengths or planar area.
                    data["mesh_vertices"] = [tuple(float(c) for c in v.dxf.location) for v in e.vertices]
                    data["unsupported_measurement"] = "شبکه سه‌بعدی به متره سطحی دوبعدی تبدیل نمی‌شود"
                elif typ in {"LWPOLYLINE", "POLYLINE"}:
                    pts = [_xy(p) for p in e.get_points("xy")] if typ == "LWPOLYLINE" else [_xy(v.dxf.location) for v in e.vertices]
                    bulges = [p[2] for p in e.get_points("xyb")] if typ == "LWPOLYLINE" else [float(getattr(v.dxf, "bulge", 0)) for v in e.vertices]
                    data["length"], data["area"] = _poly_metrics(pts, bool(getattr(e, "is_closed", getattr(e, "closed", False))), bulges)
                    data["points"] = pts
                    data["bulges"] = bulges
                elif typ == "CIRCLE":
                    r = float(e.dxf.radius)
                    data.update(radius=r, length=2 * math.pi * r, area=math.pi * r * r)
                elif typ == "ARC":
                    r = float(e.dxf.radius)
                    sweep = (float(e.dxf.end_angle) - float(e.dxf.start_angle)) % 360
                    data.update(radius=r, length=2 * math.pi * r * sweep / 360)
                elif typ in {"TEXT", "MTEXT"}:
                    data["text"] = str(e.dxf.text if hasattr(e.dxf, "text") else e.text)
                    data["insert"] = _xy(e.dxf.insert)
                    data["height"] = float(getattr(e.dxf, "height", getattr(e.dxf, "char_height", 1)))
                    out.text_labels.append(data["text"])
                elif typ == "INSERT":
                    name = str(e.dxf.name)
                    out.block_counts[name] = out.block_counts.get(name, 0) + 1
                    data.update(block=name, insert=_xy(e.dxf.insert))
                elif typ == "HATCH":
                    data["pattern"] = str(getattr(e.dxf, "pattern_name", ""))
                else:
                    for attr in ("start", "end", "center", "insert"):
                        if hasattr(e.dxf, attr):
                            try:
                                data[attr] = _xy(getattr(e.dxf, attr))
                            except Exception:
                                pass

                if typ in {"CIRCLE", "ARC"}:
                    data["center"] = _xy(e.dxf.center)
                if typ in {"LWPOLYLINE", "POLYLINE", "ARC"} and not data.get("unsupported_measurement"):
                    from ezdxf.path import make_path
                    path = make_path(e)
                    control = list(path.control_vertices())
                    span = max((max(p.x for p in control) - min(p.x for p in control)),
                               (max(p.y for p in control) - min(p.y for p in control)), 1e-6)
                    # Display approximation only; takeoff uses analytic metrics above.
                    display = []
                    for point in path.flattening(distance=span * 1e-4):
                        display.append(_xy(point))
                        if len(display) > 20000:
                            raise ValueError("هندسه CAD برای نمایش بسیار پیچیده است")
                    data["display_points"] = display
                    data["closed"] = bool(path.is_closed)
                out.entities.append(DWGEntity(typ, layer, getattr(e.dxf, "handle", None), data))
        except Exception as exc:
            raise RuntimeError(f"تحلیل عناصر CAD شکست خورد: {exc}") from exc

        factor = cad_unit_factor(out.units)
        if factor is not None and factor != 1.0:
            normalized = []
            for entity in out.entities:
                data = dict(entity.data)
                for key in ("length", "radius", "height"):
                    if key in data:
                        data[key] = float(data[key]) * factor
                if "area" in data:
                    data["area"] = float(data["area"]) * (factor ** 2)
                for key in ("start", "end", "insert", "center"):
                    if key in data and data[key] is not None:
                        data[key] = (float(data[key][0]) * factor, float(data[key][1]) * factor)
                if "points" in data:
                    data["points"] = [(float(p[0]) * factor, float(p[1]) * factor) for p in data["points"]]
                if "display_points" in data:
                    data["display_points"] = [(float(p[0]) * factor, float(p[1]) * factor) for p in data["display_points"]]
                normalized.append(DWGEntity(entity.entity_type, entity.layer, entity.handle, data))
            out.entities = normalized

        out.layers = sorted(layers)
        return out

    def import_file(self, path: str | Path) -> DWGDocument:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"فایل CAD پیدا نشد: {p}")
        if not p.is_file():
            raise ValueError(f"مسیر CAD یک فایل نیست: {p}")
        if p.suffix.lower() == ".dxf":
            return self._read_dxf(p)
        if p.suffix.lower() != ".dwg":
            raise ValueError("فرمت فایل باید DWG یا DXF باشد.")

        # Prefer the bundled/authorized ACadSharp bridge used by the Windows
        # product. Use a separately installed offline converter only when that
        # bridge is genuinely unavailable; conversion failures from an available
        # bridge must remain visible rather than silently switching backends.
        from core.cad.external_dwg_provider_v1 import ACadSharpDWGProvider
        provider = ACadSharpDWGProvider()
        if provider.available:
            converted = provider.convert(p)
            try:
                doc = self._read_dxf(converted)
            finally:
                converted.unlink(missing_ok=True)
            doc.source = str(p)
            doc.format = "DWG→DXF (ACadSharp)"
            return doc

        from core.drawings.dwg_converter import OfflineDWGConverter
        result = OfflineDWGConverter().convert(p)
        try:
            doc = self._read_dxf(result.output)
        finally:
            result.output.unlink(missing_ok=True)
            if result.output.parent.name.startswith("structuralpro_dwg_"):
                try:
                    result.output.parent.rmdir()
                except OSError:
                    pass
        doc.source = str(p)
        doc.format = "DWG→DXF (offline converter)"
        return doc

    def summarize(self, doc: DWGDocument) -> dict[str, Any]:
        by_type = {}
        for e in doc.entities:
            by_type[e.entity_type] = by_type.get(e.entity_type, 0) + 1
        return {
            "entities": len(doc.entities),
            "by_type": by_type,
            "layers": doc.layers,
            "blocks": doc.block_counts,
            "text_count": len(doc.text_labels),
            "xrefs": doc.xrefs,
            "units": doc.units,
            "source": doc.source,
            "format": doc.format,
            "unsupported_geometry_count": sum(bool(e.data.get("unsupported_measurement")) for e in doc.entities),
        }

    def layer_takeoff(self, doc: DWGDocument, rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Create review-required layer summaries; never treat raw/unknown units as metres."""
        out = []
        for layer, rule in rules.items():
            ents = [e for e in doc.entities if e.layer == layer]
            if not ents:
                continue
            metric = str(rule.get("metric", "count")).strip().lower()
            if metric not in {"count", "length", "area"}:
                raise ValueError(f"متریک CAD پشتیبانی نمی‌شود: {metric}")
            if metric in {"length", "area"} and cad_unit_factor(doc.units) is None:
                raise ValueError(
                    f"واحد نقشه CAD برای لایه {layer} نامشخص است؛ پیش از برداشت طول/مساحت، واحد یا کالیبراسیون معتبر تعیین شود."
                )
            values = []
            for entity in ents:
                if metric != "count" and entity.data.get("unsupported_measurement"):
                    raise ValueError(entity.data["unsupported_measurement"])
                raw = entity.data.get(metric, 1 if metric == "count" else None)
                if raw is None:
                    raise ValueError(f"هندسه لازم برای متریک {metric} در لایه {layer} وجود ندارد.")
                value = float(raw)
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"مقدار CAD نامعتبر در لایه: {layer}")
                values.append(value)
            qty = sum(values)
            default_unit = {"count": "عدد", "length": "m", "area": "m²"}[metric]
            out.append({
                "layer": layer,
                "count": len(ents),
                "quantity": qty,
                "description": str(rule.get("description", layer)),
                "unit": str(rule.get("unit", default_unit)),
                "price_code": rule.get("price_code"),
                "source": f"dwg-layer:{layer}",
                "needs_confirmation": True,
                "unit_basis": doc.units,
                "metric": metric,
            })
        return out

def infer_takeoff_from_layers(doc: DWGDocument, rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return DWGTakeoffEngine().layer_takeoff(doc, rules)
