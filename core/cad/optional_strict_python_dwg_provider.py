"""Fail-closed DWG reader via optional pinned prebuilt Python wheel.

Strict conversion checks entity coverage. Critically, the upstream DXF
writer can default $INSUNITS to metres even when original DWG is millimetres.
Never pass such a unit error into takeoff or silently infer a missing unit.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib import metadata, util
from pathlib import Path
import os
import tempfile
from math import isclose, isfinite

from core.drawings.dwg_converter import OfflineDWGConverter

PINNED_VERSION = "0.17.0"
MAX_DWG_BYTES = 50 * 1024 * 1024
ALLOWED_DWG_HEADERS = frozenset({"AC1015", "AC1018", "AC1021", "AC1024", "AC1027", "AC1032"})

_UNIT_CODES = {
    "inches": (1, "in"), "inch": (1, "in"), "in": (1, "in"),
    "feet": (2, "ft"), "foot": (2, "ft"), "ft": (2, "ft"),
    "millimeters": (4, "mm"), "millimetres": (4, "mm"), "mm": (4, "mm"),
    "centimeters": (5, "cm"), "centimetres": (5, "cm"), "cm": (5, "cm"),
    "meters": (6, "m"), "metres": (6, "m"), "m": (6, "m"),
    "kilometers": (7, "km"), "kilometres": (7, "km"), "km": (7, "km"),
}


class StrictPythonDWGError(RuntimeError):
    pass


def _validate_native_entity_roster(native_document, converted_document) -> dict:
    """Check actual source ModelSpace identities and every LINE against written DXF.

    Writer-reported written==total is insufficient evidence: eight source
    LINEs disappeared in a separate LibreDWG converter on the private case.
    The ezdwg decoder is the source witness, not a second independent CAD oracle.
    """
    native = {}
    layers = {int(layer.handle): str(layer.name) for layer in native_document.layers}
    for entity in native_document.modelspace().iter_entities():
        handle = int(entity.handle)
        kind = str(entity.dxftype)
        if handle in native:
            raise StrictPythonDWGError("DWG native source contains duplicate ModelSpace handles")
        if len(native) >= 1_000_000:
            raise StrictPythonDWGError("DWG native roster exceeds the one-million-entity safety limit")
        native[handle] = (kind, entity)
    converted = {}
    for entity in converted_document.modelspace():
        handle = int(entity.dxf.handle, 16)
        if handle in converted:
            raise StrictPythonDWGError("Converted DXF contains duplicate ModelSpace handles")
        converted[handle] = (entity.dxftype(), entity)
    source_types = {(handle, value[0]) for handle, value in native.items()}
    dest_types = {(handle, value[0]) for handle, value in converted.items()}
    if source_types != dest_types:
        missing = source_types - dest_types
        extra = dest_types - source_types
        raise StrictPythonDWGError(
            f"Strict DWG conversion lost/retyped source identities; "
            f"missing={len(missing)} extra={len(extra)}")
    def xyz(value):
        if value is None:
            raise StrictPythonDWGError("DWG LINE endpoint is missing")
        values = tuple(float(v) for v in value)
        if len(values) not in (2, 3) or not all(isfinite(v) for v in values):
            raise StrictPythonDWGError("DWG LINE endpoint is invalid")
        return values if len(values) == 3 else (*values, 0.0)
    verified_lines = 0
    verified_layers = 0
    for handle, (kind, raw) in native.items():
        if kind != "LINE":
            continue
        entity = converted[handle][1]
        for field in ("start", "end"):
            first = xyz(raw.dxf.get(field))
            second = xyz(entity.dxf.get(field))
            if any(not isclose(a, b, rel_tol=1e-12, abs_tol=1e-7)
                   for a, b in zip(first, second)):
                raise StrictPythonDWGError(
                    f"Strict DWG LINE geometry changed (handle={handle:X}, field={field})")
        source_layer_handle = raw.dxf.get("layer_handle")
        if source_layer_handle is None or int(source_layer_handle) not in layers:
            raise StrictPythonDWGError(
                f"Cannot verify source DWG LINE layer (handle={handle:X})")
        if layers[int(source_layer_handle)] != str(entity.dxf.layer):
            raise StrictPythonDWGError(
                f"Strict DWG LINE layer changed (handle={handle:X})")
        verified_layers += 1
        verified_lines += 1
    if not native:
        raise StrictPythonDWGError("Original DWG ModelSpace is empty")
    return {"source_entity_count": len(native), "dxf_entity_count": len(converted),
            "source_line_count": verified_lines, "line_geometry_verified": verified_lines,
            "line_layers_verified": verified_layers, "handle_type_roster_matched": True}




def declared_dwg_unit(source_unit: str | None) -> tuple[int, str]:
    """Reject unitless/unknown DWG; do not guess from title or model size."""
    if not isinstance(source_unit, str):
        raise StrictPythonDWGError("Original DWG has no explicit supported unit")
    unit = _UNIT_CODES.get(source_unit.strip().casefold())
    if unit is None:
        raise StrictPythonDWGError("Original DWG unit is unsupported or ambiguous")
    return unit


@dataclass(frozen=True)
class StrictPythonDWGReceipt:
    output: Path
    source_sha256: str
    output_sha256: str
    decoder_version: str
    signature: str
    total_entities: int
    written_entities: int
    skipped_entities: int
    source_unit: str
    source_unit_code: int
    original_dxf_unit_code: int
    source_unit_restored_in_dxf: bool
    source_modelspace_verified: bool = False
    line_geometry_verified_count: int = 0
    line_layer_verified_count: int = 0


class StrictPythonDWGProvider:
    @property
    def available(self) -> bool:
        if util.find_spec("ezdwg") is None:
            return False
        try:
            return metadata.version("ezdwg") == PINNED_VERSION
        except metadata.PackageNotFoundError:
            return False

    @staticmethod
    def _sha(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _handles(document) -> list[tuple[str, str]]:
        return sorted(
            (str(entity.dxftype()), str(entity.dxf.get("handle", "")))
            for entity in document.modelspace()
        )

    def convert(self, source: str | Path) -> StrictPythonDWGReceipt:
        import ezdxf
        path = Path(source)
        if not path.is_file() or path.suffix.lower() != ".dwg":
            raise StrictPythonDWGError("Expected a real local DWG source file")
        if not 6 < path.stat().st_size <= MAX_DWG_BYTES:
            raise StrictPythonDWGError("DWG is empty or outside the approved size limit")
        header = OfflineDWGConverter.inspect_header(path)["code"]
        if header not in ALLOWED_DWG_HEADERS:
            raise StrictPythonDWGError("DWG version not approved for strict Python decoding")
        if not self.available:
            raise StrictPythonDWGError("Pinned ezdwg[dxf]==0.17.0 prebuilt wheel is unavailable")
        original_sha = self._sha(path)
        import ezdwg
        decoded_source = ezdwg.read(str(path))
        if decoded_source.version != header:
            raise StrictPythonDWGError("Decoder version disagrees with raw DWG header")
        expected_units, unit_name = declared_dwg_unit(decoded_source.units)
        fd, name = tempfile.mkstemp(prefix="structuralpro-ezdwg-strict-", suffix=".dxf")
        os.close(fd)
        out = Path(name)
        try:
            out.unlink(missing_ok=True)
            result = ezdwg.to_dxf(str(path), str(out), strict=True)
            total = int(result.total_entities)
            written = int(result.written_entities)
            skipped = int(result.skipped_entities)
            if total <= 0 or skipped or written != total:
                raise StrictPythonDWGError("Strict DWG conversion lost entity coverage")
            if not out.is_file() or out.stat().st_size <= 100:
                raise StrictPythonDWGError("Strict decoder produced no DXF")
            dxf_doc = ezdxf.readfile(out)
            roster = _validate_native_entity_roster(decoded_source, dxf_doc)
            original_dxf_unit = int(dxf_doc.header.get("$INSUNITS", 0) or 0)
            restored = original_dxf_unit != expected_units
            if restored:
                before = self._handles(dxf_doc)
                if not before:
                    raise StrictPythonDWGError("Cannot repair units in an empty drawing")
                # Use the explicit native DWG $INSUNITS; this fixes DXF writer's
                # incorrect default, not a guessed metre/millimetre calibration.
                dxf_doc.header["$INSUNITS"] = expected_units
                dxf_doc.saveas(out)
                reloaded = ezdxf.readfile(out)
                if self._handles(reloaded) != before:
                    raise StrictPythonDWGError("DXF geometry identity changed while correcting unit header")
                if int(reloaded.header.get("$INSUNITS", 0) or 0) != expected_units:
                    raise StrictPythonDWGError("Failed to preserve original DWG unit in DXF")
            if self._sha(path) != original_sha:
                raise StrictPythonDWGError("Source DWG changed during strict conversion")
            return StrictPythonDWGReceipt(
                output=out, source_sha256=original_sha,
                output_sha256=self._sha(out), decoder_version=PINNED_VERSION,
                signature=header, total_entities=total,
                written_entities=written, skipped_entities=skipped,
                source_unit=unit_name, source_unit_code=expected_units,
                original_dxf_unit_code=original_dxf_unit,
                source_unit_restored_in_dxf=restored,
                source_modelspace_verified=bool(roster["handle_type_roster_matched"]),
                line_geometry_verified_count=int(roster["line_geometry_verified"]),
                line_layer_verified_count=int(roster["line_layers_verified"]),
            )
        except Exception:
            out.unlink(missing_ok=True)
            raise
