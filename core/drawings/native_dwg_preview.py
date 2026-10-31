"""Source-native read-only DWG graphical preview, never a BOQ measurement source.

The normal strict DWG import is still the ONLY payable entrypoint. This
fallback makes a real DWG with unitless metadata or unsupported SHX/text
conversion visible in the Windows drawing workspace without fabricating
units, silently losing entities, or declaring quantity acceptance.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from importlib import metadata, util
from math import dist, isfinite, pi
from pathlib import Path
from typing import Any

from core.cad.persian_text_v1 import normalize_cad_text, is_rtl_cad_text
from core.drawings.dwg_takeoff import DWGDocument, DWGEntity
from core.drawings.dwg_converter import OfflineDWGConverter

_EXPECTED_VERSION = "0.17.0"
_LIMIT_BYTES = 50 * 1024 * 1024
_LIMIT_ENTITIES = 250_000
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


def native_readonly_dwg_preview(path: str | Path) -> DWGDocument:
    src = Path(path)
    if src.suffix.lower() != ".dwg" or not src.is_file():
        raise ValueError("Original DWG file required")
    if not 6 < src.stat().st_size <= _LIMIT_BYTES:
        raise ValueError("DWG size outside bounded preview policy")
    version = OfflineDWGConverter.inspect_header(src)["code"]
    if version not in _ALLOWED:
        raise ValueError("DWG version not supported for native preview")
    if util.find_spec("ezdwg") is None or metadata.version("ezdwg") != _EXPECTED_VERSION:
        raise RuntimeError("Pinned ezdwg==0.17.0 must be installed for native DWG preview")

    digest = sha256(src.read_bytes()).hexdigest()
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
        visible = bool(layer_info.on and not layer_info.frozen) if layer_info else False
        data: dict[str, Any] = {
            "unsupported_measurement": _BLOCK,
            "layer_visible": visible, "layer_defined": bool(layer_info),
            "preview_only": True,
        }
        if typ == "LINE":
            p,q = _xy(d.get("start")),_xy(d.get("end"))
            data.update(start=p,end=q,length=dist(p,q))
        elif typ == "LWPOLYLINE":
            points = [_xy(p) for p in d.get("points",[])]
            if points:
                data.update(points=points,closed=bool(d.get("closed")),
                            bulges=[float(b) for b in d.get("bulges",[])])
        elif typ in {"ARC", "CIRCLE"}:
            if d.get("center") is not None and d.get("radius") is not None:
                data.update(center=_xy(d["center"]),radius=_positive(d["radius"]))
        elif typ in {"TEXT", "MTEXT", "DIMENSION"}:
            raw_text = str(d.get("text", "") or "")
            value = normalize_cad_text(raw_text)
            data["text"] = value  # Never invent characters for legacy SHX maps.
            if d.get("insert") is not None:
                data["insert"] = _xy(d["insert"])
            if d.get("height") is not None:
                data["height"] = _positive(d["height"])
            if d.get("char_height") is not None:
                data["char_height"] = _positive(d["char_height"])
            if d.get("rotation") is not None:
                data["rotation"] = float(d["rotation"])
            if d.get("width") is not None:
                data["text_width"] = _positive(d["width"])
            data["style_handle"] = str(d.get("style_handle") or "")
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
    if sha256(src.read_bytes()).hexdigest() != digest:
        raise ValueError("DWG source changed during preview")
    if not out.entities:
        raise ValueError("No native DWG entities available for preview")
    out.conversion["source_entity_count"] = len(out.entities)
    out.conversion["primitive_types_not_drawn"] = dict(unsupported)
    out.conversion["text_fidelity"] = "NOT_VERIFIED_LEGACY_SHX_CODEPAGE"
    out.conversion["legacy_shx_text_candidates"] = unresolved_fonts
    if unresolved_fonts:
        out.warnings.append(
            f"{unresolved_fonts} متن CAD با نویسه‌گذاری قدیمی مشکوک است؛ نصب فونت فارسی به‌تنهایی نگاشت SHX را بازیابی نمی‌کند"
        )
    return out
