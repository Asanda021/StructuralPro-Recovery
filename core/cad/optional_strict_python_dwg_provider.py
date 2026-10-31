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
            )
        except Exception:
            out.unlink(missing_ok=True)
            raise
