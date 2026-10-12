"""Phase 21: deterministic DWG/DXF extraction boundary.

DXF is parsed with ezdxf when available. DWG is accepted only through an
explicit backend adapter because ezdxf does not decode native DWG bytes.
No geometry, unit, scale, or engineering quantity is guessed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import pi, hypot
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
import hashlib


INSUNITS = {
    0: "unitless", 1: "in", 2: "ft", 3: "mi", 4: "mm", 5: "cm", 6: "m",
    7: "km", 8: "microinch", 9: "mil", 10: "yd", 11: "angstrom",
    12: "nm", 13: "um", 14: "dm", 15: "dam", 16: "hm", 17: "gm",
    18: "au", 19: "ly", 20: "pc", 21: "us_survey_ft", 22: "us_survey_in",
    23: "us_survey_yd", 24: "us_survey_mi", 25: "us_survey_ft",
    26: "us_survey_mi",
}


@dataclass(frozen=True)
class CadEntityRecord:
    handle: str
    entity_type: str
    layer: str
    block: str | None
    geometry: tuple[tuple[str, float], ...]
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CadExtractionResult:
    format: str
    version: str
    units: str
    layers: tuple[str, ...]
    blocks: tuple[str, ...]
    entities: tuple[CadEntityRecord, ...]
    source_fingerprint: str
    backend: str

    @property
    def object_count(self) -> int:
        return len(self.entities)

    def by_layer(self, layer: str) -> tuple[CadEntityRecord, ...]:
        return tuple(e for e in self.entities if e.layer == layer)

    def by_type(self, entity_type: str) -> tuple[CadEntityRecord, ...]:
        return tuple(e for e in self.entities if e.entity_type == entity_type)

    def export_payload(self) -> dict[str, Any]:
        return {
            "schema": "structuralpro.cad.dwg_dxf.v1",
            "format": self.format,
            "version": self.version,
            "units": self.units,
            "layers": list(self.layers),
            "blocks": list(self.blocks),
            "object_count": self.object_count,
            "entities": [asdict(e) for e in self.entities],
            "source_fingerprint": self.source_fingerprint,
            "backend": self.backend,
        }


class CadExtractionError(ValueError):
    """Raised when CAD evidence cannot be decoded deterministically."""


def artifact_fingerprint(payload: bytes) -> str:
    if not isinstance(payload, bytes) or not payload:
        raise CadExtractionError("CAD artifact must be non-empty bytes")
    return hashlib.sha256(payload).hexdigest()


def _version(doc: Any) -> str:
    return str(getattr(doc, "acadver", "") or "")


def _units(doc: Any) -> str:
    value = int(getattr(doc.header, "get", lambda *_: 0)("$INSUNITS", 0) or 0)
    return INSUNITS.get(value, "unitless")


def _point(value: Any) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2] if len(value) > 2 else 0.0))


def _geometry(entity: Any) -> tuple[tuple[str, float], ...]:
    typ = entity.dxftype()
    if typ == "LINE":
        start, end = _point(entity.dxf.start), _point(entity.dxf.end)
        return (("length", hypot(end[0] - start[0], end[1] - start[1])),)
    if typ in {"CIRCLE", "ARC"}:
        radius = float(entity.dxf.radius)
        values = [("radius", radius), ("circumference", 2 * pi * radius)]
        if typ == "ARC":
            sweep = (float(entity.dxf.end_angle) - float(entity.dxf.start_angle)) % 360.0
            values.append(("arc_length", 2 * pi * radius * sweep / 360.0))
        return tuple(values)
    if typ in {"LWPOLYLINE", "POLYLINE"}:
        try:
            length = float(entity.length())
        except (AttributeError, TypeError, ValueError):
            length = 0.0
        return (("length", length),)
    if typ == "DIMENSION":
        value = getattr(entity.dxf, "actual_measurement", None)
        return (("measurement", float(value)),) if value is not None else ()
    if typ in {"TEXT", "MTEXT"}:
        return ()
    if typ == "INSERT":
        return (("scale_x", float(entity.dxf.xscale)), ("scale_y", float(entity.dxf.yscale)),
                ("rotation", float(entity.dxf.rotation)))
    return ()


def _entity_record(entity: Any) -> CadEntityRecord:
    typ = entity.dxftype()
    attrs: list[tuple[str, str]] = []
    for name in ("text", "name", "style"):
        if hasattr(entity.dxf, name):
            attrs.append((name, str(getattr(entity.dxf, name))))
    block = str(entity.dxf.name) if typ == "INSERT" and hasattr(entity.dxf, "name") else None
    return CadEntityRecord(
        handle=str(getattr(entity.dxf, "handle", "")),
        entity_type=typ,
        layer=str(getattr(entity.dxf, "layer", "0")),
        block=block,
        geometry=_geometry(entity),
        attributes=tuple(sorted(attrs)),
    )


def extract_dxf(payload: bytes) -> CadExtractionResult:
    if not isinstance(payload, bytes) or not payload:
        raise CadExtractionError("DXF artifact must be non-empty bytes")
    try:
        import ezdxf
        from io import StringIO
        doc = ezdxf.read(StringIO(payload.decode("utf-8")))
    except Exception as exc:
        raise CadExtractionError("DXF decoding failed") from exc

    entities: list[CadEntityRecord] = []
    for entity in doc.modelspace():
        entities.append(_entity_record(entity))

    layers = tuple(sorted(str(layer.dxf.name) for layer in doc.layers))
    blocks = tuple(sorted(str(block.name) for block in doc.blocks if not str(block.name).startswith("*")))
    return CadExtractionResult(
        format="DXF",
        version=_version(doc),
        units=_units(doc),
        layers=layers,
        blocks=blocks,
        entities=tuple(entities),
        source_fingerprint=artifact_fingerprint(payload),
        backend="ezdxf",
    )


DwgBackend = Callable[[bytes], CadExtractionResult]


def extract_cad(payload: bytes, fmt: str, dwg_backend: DwgBackend | None = None) -> CadExtractionResult:
    """Decode DXF directly; decode DWG only via an explicit backend."""
    normalized = fmt.upper().strip()
    if normalized == "DXF":
        return extract_dxf(payload)
    if normalized == "DWG":
        if dwg_backend is None:
            raise CadExtractionError(
                "Native DWG decoding requires an explicit DWG backend; "
                "no conversion or geometry guessing is performed"
            )
        result = dwg_backend(payload)
        if not isinstance(result, CadExtractionResult) or result.format != "DWG":
            raise CadExtractionError("DWG backend returned an invalid extraction result")
        return result
    raise CadExtractionError("Unsupported CAD format")


def validate_extraction(result: CadExtractionResult) -> None:
    if result.format not in {"DXF", "DWG"}:
        raise CadExtractionError("Unsupported CAD format")
    if not result.units or result.units == "unitless":
        raise CadExtractionError("CAD units are unresolved")
    handles = [e.handle for e in result.entities]
    if len(handles) != len(set(handles)):
        raise CadExtractionError("Duplicate CAD entity handles detected")


def layer_index(result: CadExtractionResult) -> Mapping[str, tuple[str, ...]]:
    validate_extraction(result)
    return {
        layer: tuple(e.handle for e in result.entities if e.layer == layer)
        for layer in result.layers
    }
