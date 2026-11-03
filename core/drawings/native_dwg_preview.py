"""Source-native read-only DWG graphical preview, never a BOQ measurement source.

The normal strict DWG import is still the ONLY payable entrypoint. This
fallback makes a real DWG with unitless metadata or unsupported SHX/text
conversion visible in the Windows drawing workspace without fabricating
units, silently losing entities, or declaring quantity acceptance.
"""
from __future__ import annotations

from collections import Counter
from hashlib import file_digest
from importlib import metadata, util
from math import dist, isfinite, pi
from pathlib import Path
from typing import Any

from core.cad.persian_text_v1 import normalize_cad_text, is_rtl_cad_text
from core.drawings.dwg_takeoff import DWGDocument, DWGEntity
from core.drawings.dwg_converter import OfflineDWGConverter

_EXPECTED_VERSION = "0.17.0"
# Bounded larger-drawing read-only policy; not a guarantee of UI/performance
# acceptance for all vendor proxy objects.  Worker isolation and incremental
# rendering allow controlled growth without silent source-entity truncation.
_LIMIT_BYTES = 100 * 1024 * 1024
_LIMIT_ENTITIES = 1_000_000
_ALLOWED = frozenset({"AC1015", "AC1018", "AC1021", "AC1024", "AC1027", "AC1032"})
_BLOCK = "بازنمایی مستقیم و فقط‌خواندنی DWG؛ بدون واحد و تبدیل کامل قابل‌تأیید، متره و BOQ مجاز نیست"


def _xy(value) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError("Invalid native drawing coordinates")
    xy = tuple(map(float, value[:2]))
    if not all(isfinite(v) for v in xy):
        raise ValueError("Non-finite coordinate in native DWG")
    return xy


def _positive(value: Any) -> float:
    val = float(value)
    if not isfinite(val) or val < 0:
        raise ValueError("Invalid numeric native CAD attribute")
    return val


def _identity(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _native_display_geometry(typ: str, d: dict) -> dict:
    """Build bounded WCS display paths, never quantities, from decoded fields.

    Use ezdxf's geometry implementation for OCS, arc sweeps, bulges and knots.
    Connecting spline control vertices or polyline bulges as straight chords
    misrepresents the source. Separate hatch rings must stay separate paths.
    """
    from ezdxf.entities import factory
    from ezdxf.path import make_path

    if typ == "HATCH":
        paths = []
        from ezdxf.math import OCS, Vec3
        ocs = OCS(d.get("extrusion", (0, 0, 1)))
        budget = 0
        for ring in d.get("paths", []):
            # Only the decoder's explicit polyline representation is supported;
            # do not invent a boundary for unsupported edge-only rings.
            points = ring.get("points", [])
            if len(points) < 2 or ring.get("edges") or any(ring.get("bulges", [])):
                raise ValueError("Native hatch boundary is not an explicit decoded polyline")
            budget += len(points) + 1
            if budget > 20000:
                raise ValueError("Native display path exceeds safe vertex budget")
            values = [_xy(tuple(ocs.to_wcs(Vec3(p[0], p[1], d.get("elevation", 0))))) for p in points]
            if ring.get("closed") and values[-1] != values[0]:
                values.append(values[0])
            paths.append(values)
        if not paths:
            raise ValueError("Native hatch has no decoded boundary paths")
        return {"display_paths": paths, "display_fidelity": "BOUNDARIES_ONLY_NO_PATTERN"}
    attrs = {key: d[key] for key in ("extrusion", "elevation", "thickness") if key in d}
    if typ == "ARC":
        attrs.update(center=d["center"], radius=_positive(d["radius"]),
                     start_angle=float(d["start_angle"]), end_angle=float(d["end_angle"]))
        if attrs["radius"] <= 0 or not all(isfinite(attrs[k]) for k in ("start_angle", "end_angle")):
            raise ValueError("Invalid native arc")
        entity = factory.new(typ, dxfattribs=attrs)
    elif typ == "LWPOLYLINE":
        entity = factory.new(typ, dxfattribs=attrs)
        points, bulges = d.get("points", []), d.get("bulges", [])
        if len(points) < 2 or (bulges and len(bulges) != len(points)):
            raise ValueError("Incomplete native polyline")
        entity.set_points([(*_xy(p), float(bulges[i]) if bulges else 0.0)
                           for i, p in enumerate(points)], format="xyb")
        entity.closed = bool(d.get("closed"))
    elif typ == "SPLINE":
        entity = factory.new(typ, dxfattribs={"degree": int(d["degree"])})
        if not d.get("control_points") or not d.get("knots"):
            raise ValueError("Native spline lacks explicit control points or knots")
        entity.control_points = d["control_points"]
        entity.knots = d["knots"]
        if d.get("weights"):
            entity.weights = d["weights"]
    elif typ == "SOLID":
        points = d.get("points", [])
        if len(points) not in (3, 4):
            raise ValueError("Incomplete native solid")
        attrs.update({f"vtx{i}": points[min(i, len(points)-1)] for i in range(4)})
        entity = factory.new(typ, dxfattribs=attrs)
    else:
        return {}
    path = make_path(entity)
    control = list(path.control_vertices())
    if not control:
        raise ValueError("Native display path is empty")
    span = max(max(v.x for v in control)-min(v.x for v in control),
               max(v.y for v in control)-min(v.y for v in control), 1e-6)
    points = []
    for vertex in path.flattening(distance=span*1e-4):
        points.append(_xy(tuple(vertex)))
        if len(points) > 20000:
            raise ValueError("Native display path exceeds safe vertex budget")
    if len(points) < 2:
        raise ValueError("Native display path is incomplete")
    return {"display_points": points, "closed": bool(path.is_closed),
            "display_fidelity": ("BOUNDARIES_ONLY_NO_SOLID_FILL" if typ == "SOLID" else
                                 "TESSELLATED_SOURCE_GEOMETRY_NOT_MEASUREMENT")}


def native_readonly_dwg_preview(path: str | Path) -> DWGDocument:
    src = Path(path)
    if src.suffix.lower() != ".dwg" or not src.is_file():
        raise ValueError("Original DWG file required")
    if not 6 < src.stat().st_size <= _LIMIT_BYTES:
        raise ValueError("DWG size outside bounded preview policy")
    source_identity = _identity(src)
    version = OfflineDWGConverter.inspect_header(src)["code"]
    if version not in _ALLOWED:
        raise ValueError("DWG version not supported for native preview")
    if util.find_spec("ezdwg") is None or metadata.version("ezdwg") != _EXPECTED_VERSION:
        raise RuntimeError("Pinned ezdwg==0.17.0 must be installed for native DWG preview")

    # Streaming hashing: avoid allocating a second full 100MB source buffer
    # merely to verify the immutable drawing evidence.
    with src.open("rb") as source_stream:
        digest = file_digest(source_stream, "sha256").hexdigest()
    import ezdwg
    raw = ezdwg.read(str(src))
    if raw.version != version:
        raise ValueError("Native parser disagrees with real DWG signature")
    unit = "unitless" if raw.units is None else str(raw.units)
    known_units = {"millimeters": "mm", "centimeters": "cm", "meters": "m",
                   "feet": "ft", "inches": "in", "kilometers": "km"}
    # Critical: unitless must NEVER be silently changed to metres.
    display_units = known_units.get(unit, "unitless" if unit == "unitless" else "unknown")
    layer_map = {int(layer.handle):layer for layer in raw.layers}
    out = DWGDocument(
        source=str(src.resolve()), format="DWG_NATIVE_READONLY_PREVIEW",
        source_sha256=digest, dxf_version=version, units=display_units,
    )
    out.layers = sorted({layer.name for layer in layer_map.values()})
    out.warnings = [_BLOCK]
    if display_units in {"unitless", "unknown"}:
        out.warnings.append("DWG does not declare a usable unit; reference dimension calibration is required")
    out.conversion = {"provider": "ezdwg native read-only preview",
                      "decoder_version": _EXPECTED_VERSION,
                      "preview_only": True, "geometry_approved": False,
                      "cad_derived_legacy_metre_rows_approved": 0,
                      "requires_strict_financial_reimport": True}
    unsupported = Counter()
    unresolved_fonts = 0
    text_style_counts: Counter[str] = Counter()
    native_text_decoded_count = 0
    seen_handles: set[str] = set()
    for index, obj in enumerate(raw.modelspace().iter_entities()):
        if index >= _LIMIT_ENTITIES:
            raise ValueError("DWG entity count exceeds bounded preview policy")
        typ = str(obj.dxftype)
        d = obj.dxf
        handle = str(obj.handle)
        if not handle or handle in seen_handles:
            raise ValueError("DWG native entities need unique nonblank handles")
        seen_handles.add(handle)
        layer_info = layer_map.get(d.get("layer_handle"))
        name = str(layer_info.name) if layer_info else "UNKNOWN_LAYER"
        visible = bool(layer_info.on and not layer_info.frozen and not d.get("invisible")) if layer_info else False
        data: dict[str, Any] = {
            "unsupported_measurement": _BLOCK,
            "layer_visible": visible, "layer_defined": bool(layer_info),
            "preview_only": True,
        }
        if typ == "LINE":
            p,q = _xy(d.get("start")),_xy(d.get("end"))
            data.update(start=p,end=q,length=dist(p,q))
        elif typ in {"ARC", "LWPOLYLINE", "SPLINE", "SOLID", "HATCH"}:
            try:
                data.update(_native_display_geometry(typ, d))
            except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError) as exc:
                # Retain the source identity and a visible audit failure, without
                # rendering incorrect fallback geometry or approving quantities.
                data["preview_decode_error"] = type(exc).__name__ + ": " + str(exc)
                unsupported[typ] += 1
        elif typ == "CIRCLE":
            if d.get("center") is not None and d.get("radius") is not None:
                data.update(center=_xy(d["center"]),radius=_positive(d["radius"]))
        elif typ in {"TEXT", "MTEXT", "DIMENSION"}:
            raw_text = str(d.get("text", "") or "")
            value = normalize_cad_text(raw_text)
            data["source_text"] = raw_text
            data["text"] = value  # Never invent characters for legacy SHX maps.
            position = d.get("text_midpoint") if typ == "DIMENSION" else d.get("insert")
            if position is None:
                position = d.get("insert")
            if position is not None:
                data["insert"] = _xy(position)
            if d.get("height") is not None:
                data["height"] = _positive(d["height"])
            if d.get("char_height") is not None:
                data["char_height"] = _positive(d["char_height"])
            rotation = d.get("text_rotation", 0) if typ == "DIMENSION" else d.get("rotation", 0)
            data["rotation"] = float(rotation)
            if d.get("attachment_point") is not None:
                data["attachment_point"] = int(d["attachment_point"])
            if d.get("width") is not None:
                data["text_width"] = _positive(d["width"])
            data["style_handle"] = str(d.get("style_handle") or "")
            text_style_counts[data["style_handle"]] += 1
            native_text_decoded_count += 1
            # Source-decoder text is retained verbatim in source_text; Unicode
            # normalization is only for display. Neither a legacy SHX font name
            # nor an apparently readable string proves its original glyph map.
            data["source_text_coverage"] = "DECODER_TEXT_PRESERVED_READONLY"
            data["source_text_mapping_approved"] = False
            data["text_generation_flag"] = int(d.get("text_generation_flag") or 0)
            data["font_name"] = "source-style-handle:" + data["style_handle"]
            # Do not pretend a Windows/Qt font can decode the text of a custom
            # legacy SHX byte-to-glyph mapping. Keep raw characters inspectable.
            legacy_like = (
                data["text_generation_flag"] & 2
                and not is_rtl_cad_text(value)
                and sum(1 for c in value if 0xA0 <= ord(c) <= 0x2FFF) >= 2
            )
            if legacy_like:
                unresolved_fonts += 1
                data["text_status"] = "LEGACY_SHX_ENCODING_REQUIRES_SOURCE_FONT"
                data["font_notice"] = "متن اصلی محفوظ؛ نگاشت کاراکتر فونت SHX نامشخص است و حدس نمی‌زنیم"
            else:
                data["text_status"] = "SOURCE_UNICODE_VISIBLE_FONT_FIDELITY_UNVERIFIED"
                data["font_notice"] = "فونت جایگزین برای نمایش؛ تطبیق دقیق قلم منبع تأیید نشده"
            if typ == "DIMENSION":
                data["native_measurement"] = d.get("actual_measurement")
            out.text_labels.append(value)
        elif typ == "INSERT":
            name_of_block = str(d.get("name",""))
            out.block_counts[name_of_block] = out.block_counts.get(name_of_block,0)+1
            if d.get("insert") is not None:
                data["insert"] = _xy(d["insert"])
            data["block"] = name_of_block
        else:
            unsupported[typ] += 1
        out.entities.append(DWGEntity(typ,name,handle,data))
    with src.open("rb") as source_stream:
        final_digest = file_digest(source_stream, "sha256").hexdigest()
    if final_digest != digest or _identity(src) != source_identity:
        raise ValueError("DWG source changed during preview")
    if not out.entities:
        raise ValueError("No native DWG entities available for preview")
    out.conversion["source_entity_count"] = len(out.entities)
    out.conversion["source_count_basis"] = "DECODED_MODELSPACE_NOT_INDEPENDENT_DWG_ORACLE"
    out.conversion["original_source_count_verified"] = False
    from core.drawings.cad_large_scene import cad_coverage_report
    out.conversion["primitive_types_not_drawn"] = cad_coverage_report(out)["not_drawn_by_type"]
    out.conversion["text_fidelity"] = "NOT_VERIFIED_LEGACY_SHX_CODEPAGE"
    out.conversion["native_text_entity_count"] = native_text_decoded_count
    out.conversion["native_text_decoded_preserved_count"] = native_text_decoded_count
    out.conversion["native_text_style_handles"] = dict(sorted(text_style_counts.items()))
    out.conversion["native_text_mapping_approved"] = False
    out.conversion["native_text_financial_approval"] = False
    out.conversion["legacy_shx_text_candidates"] = unresolved_fonts
    if unresolved_fonts:
        out.warnings.append(
            f"{unresolved_fonts} متن CAD با نویسه‌گذاری قدیمی مشکوک است؛ نصب فونت فارسی به‌تنهایی نگاشت SHX را بازیابی نمی‌کند"
        )
    return out
