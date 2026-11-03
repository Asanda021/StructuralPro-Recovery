"""Read-only DXF provenance audit for source LINEs absent from parsed ModelSpace.

The raw DXF can contain a LINE nested in an anonymous BLOCK even when a
DXF reader does not return that LINE from modelspace(). This module distinguishes
raw presence from geometric inclusion and never approves or copies quantities.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path
from typing import Any

_MAX_DXF_BYTES = 250 * 1024 * 1024
_MAX_AUDITED_HANDLES = 1_000_000


@dataclass(frozen=True)
class RawDXFLineProvenance:
    handle: int
    section: str
    owner_handle: str
    block_name: str
    block_handle: str
    block_record_handle: str
    layer: str
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    paper_space: str
    layout: str


def _xyz(fields: dict[str, str], codes: tuple[str, str, str]) -> tuple[float, float, float]:
    try:
        coords = tuple(float(fields.get(code, "0")) for code in codes)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid raw DXF LINE coordinate") from exc
    if any(not isfinite(value) for value in coords):
        raise ValueError("Non-finite raw DXF LINE coordinate")
    return coords


def locate_raw_dxf_lines(path: str | Path, handles: set[int]) -> dict[int, RawDXFLineProvenance]:
    """Locate selected LINE handles by DXF section and containing BLOCK.

    Parses ASCII DXF group-code pairs without asking ezdxf to repair or omit
    malformed anonymous blocks. Only the requested handles are retained.
    Raises on binary DXF, duplicate handle, malformed group codes and bad XY/Z.
    """
    source = Path(path)
    if not handles:
        return {}
    if len(handles) > _MAX_AUDITED_HANDLES:
        raise ValueError("Too many requested source handles for DXF audit")
    if not source.is_file() or not 0 < source.stat().st_size <= _MAX_DXF_BYTES:
        raise ValueError("DXF provenance source absent or outside safe size limit")
    found: dict[int, RawDXFLineProvenance] = {}
    section = ""
    block_name = block_handle = block_record_handle = ""
    pending_type: str | None = None
    fields: dict[str, str] = {}

    def finish() -> None:
        nonlocal section, block_name, block_handle, block_record_handle
        if pending_type == "SECTION":
            section = fields.get("2", "").upper()
        elif pending_type == "ENDSEC":
            section = ""
            block_name = block_handle = block_record_handle = ""
        elif pending_type == "BLOCK" and section == "BLOCKS":
            block_name = fields.get("2", "")
            block_handle = fields.get("5", "").upper()
            block_record_handle = fields.get("330", "").upper()
        elif pending_type == "ENDBLK" and section == "BLOCKS":
            block_name = block_handle = block_record_handle = ""
        elif pending_type == "LINE":
            raw_handle = fields.get("5", "")
            if not raw_handle:
                raise ValueError("DXF LINE has no original handle")
            try:
                handle = int(raw_handle, 16)
            except ValueError as exc:
                raise ValueError("DXF LINE has invalid original handle") from exc
            if handle in handles:
                if handle in found:
                    raise ValueError("Duplicate raw DXF LINE handle")
                found[handle] = RawDXFLineProvenance(
                    handle=handle, section=section,
                    owner_handle=fields.get("330", "").upper(),
                    block_name=block_name if section == "BLOCKS" else "",
                    block_handle=block_handle if section == "BLOCKS" else "",
                    block_record_handle=block_record_handle if section == "BLOCKS" else "",
                    layer=fields.get("8", ""),
                    start=_xyz(fields, ("10", "20", "30")),
                    end=_xyz(fields, ("11", "21", "31")),
                    paper_space=fields.get("67", ""),
                    layout=fields.get("410", ""),
                )

    with source.open("rb") as stream:
        if stream.read(22).startswith(b"AutoCAD Binary DXF"):
            raise ValueError("Binary DXF cannot be audited as text")
        stream.seek(0)
        pair_count = 0
        while True:
            code = stream.readline()
            if not code:
                break
            value = stream.readline()
            if not value:
                raise ValueError("Truncated DXF group-code pair")
            pair_count += 1
            if pair_count > 12_000_000:
                raise ValueError("DXF raw audit exceeded pair safety limit")
            key = code.strip().decode("ascii", errors="strict")
            if not key.isdecimal():
                raise ValueError("Invalid raw DXF group code")
            val = value.rstrip(b"\r\n").decode("utf-8", errors="replace")
            if key == "0":
                if pending_type is not None:
                    finish()
                pending_type = val.strip().upper()
                fields = {}
            elif pending_type is not None:
                fields[key] = val.strip()
        if pending_type is not None:
            finish()
    return found


def _point3(source: Any) -> tuple[float, float, float]:
    points = tuple(float(v) for v in source)
    if len(points) not in (2, 3) or any(not isfinite(v) for v in points):
        raise ValueError("Invalid native LINE coordinates")
    return points if len(points) == 3 else (*points, 0.0)


def compare_raw_and_native_line(
    raw: RawDXFLineProvenance, native: Any, source_layers: dict[int, str],
) -> bool:
    """Independent raw bytes vs native decoder: exact 3D endpoints and layer."""
    try:
        declared_layer = source_layers[int(native.dxf.get("layer_handle"))]
        start = _point3(native.dxf.get("start"))
        end = _point3(native.dxf.get("end"))
    except (TypeError, ValueError, KeyError, AttributeError):
        return False
    if raw.layer != declared_layer:
        return False
    return all(isclose(a, b, abs_tol=1e-7, rel_tol=1e-12)
               for expected, observed in ((start, raw.start), (end, raw.end))
               for a, b in zip(expected, observed))


def audit_native_lines_absent_from_dxf_modelspace(
    dxf_path: str | Path,
    native_document: Any,
    missing_handles: set[int],
) -> dict[str, Any]:
    """Distinguish raw DXF presence from an actual source entity deletion.

    Presence under BLOCKS does not prove insertion into modelspace or permit
    takeoff. Geometry and layer must be independently checked to be VERIFIED.
    """
    found = locate_raw_dxf_lines(dxf_path, missing_handles)
    if not found:
        return {"status": "ABSENT_FROM_RAW_DXF", "raw_found": 0,
                "raw_geometry_and_layer_verified": 0, "locations": ()}
    native_entities = {}
    for entity in native_document.modelspace().iter_entities():
        handle = int(entity.handle)
        if handle in found:
            native_entities[handle] = entity
    try:
        layers = {int(layer.handle): str(layer.name) for layer in native_document.layers}
    except (AttributeError, ValueError, TypeError):
        layers = {}
    matched = sum(
        1 for handle, evidence in found.items()
        if handle in native_entities
        and compare_raw_and_native_line(evidence, native_entities[handle], layers)
    )
    locations = tuple(sorted({
        (entry.section, entry.block_name, entry.block_handle,
         entry.block_record_handle, entry.owner_handle)
        for entry in found.values()
    }))
    return {
        "status": "RAW_DXF_PRESENT_MODELSPACE_OWNERSHIP_UNRESOLVED",
        "raw_found": len(found),
        "raw_geometry_and_layer_verified": matched,
        "missing_from_raw": len(missing_handles) - len(found),
        "locations": locations,
    }
