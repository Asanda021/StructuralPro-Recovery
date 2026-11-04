"""Read-only source-bound SHX text audit; never infers missing glyph mappings.

The supplied ledger remains private.  Even two readers agreeing on a text string
cannot prove a custom SHX byte-to-glyph mapping or a dimension value.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

MAX_LEDGER_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 100_000
MAX_DWG_BYTES = 100 * 1024 * 1024
MAX_DXF_BYTES = 300 * 1024 * 1024
REQUIRED_COLUMNS = frozenset({
    "handle", "source_sha256", "entity_type", "style_handle", "font_file",
    "raw_tv_hex", "raw_tv_byte_count", "decoded_unicode", "glyph_mapping",
})


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _handle(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("SHX ledger handle must be hex string")
    name = raw.strip().upper()
    if not name or any(c not in "0123456789ABCDEF" for c in name):
        raise ValueError("SHX ledger contains nonhex handle")
    number = int(name, 16)
    if number <= 0 or number >= 2**64:
        raise ValueError("SHX ledger handle out of bounds")
    return f"{number:X}"


def validate_private_shx_ledger(rows: list[dict[str, str]], *, source_sha256: str) -> list[dict[str, str]]:
    """Reject stale/mutated/ambiguous private ledger rows without glyph guessing."""
    if not rows or len(rows) > MAX_RECORDS:
        raise ValueError("Empty or excessive SHX evidence ledger")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise ValueError("Original DWG SHA-256 is mandatory")
    seen = set()
    checked = []
    for row in rows:
        if not isinstance(row, dict) or not REQUIRED_COLUMNS.issubset(row):
            raise ValueError("SHX evidence schema incomplete")
        if row["source_sha256"].lower() != source_sha256.lower():
            raise ValueError("SHX evidence is from another original DWG")
        handle = _handle(row["handle"])
        if handle in seen or row["entity_type"] != "TEXT":
            raise ValueError("Duplicate or wrong-type SHX evidence")
        seen.add(handle)
        hex_text = row["raw_tv_hex"]
        if not isinstance(hex_text, str) or len(hex_text) % 2 or any(
            ch not in "0123456789abcdefABCDEF" for ch in hex_text
        ):
            raise ValueError("Invalid original text byte ledger")
        if (len(hex_text) // 2 != int(row["raw_tv_byte_count"])
                or len(hex_text) // 2 < 1 or len(hex_text) // 2 > 100_000):
            raise ValueError("Original text byte length inconsistent")
        if not str(row["font_file"]).lower().endswith(".shx"):
            raise ValueError("Legacy SHX font reference missing")
        if row["glyph_mapping"] != "UNKNOWN_ORIGINAL_SHX_NOT_PRESENT":
            raise ValueError("Cannot inherit unverified glyph-approval claims")
        checked.append({**row, "handle": handle})
    return checked


def classify_shx_record(
    record: dict[str, str], native_entity: Any | None, dxf_entity: Any | None,
    *, modelspace_record_handle: str,
) -> dict[str, Any]:
    """Classify modelspace vs block-owned TEXT. Neither status proves glyphs."""
    result: dict[str, Any] = {
        "handle": record["handle"],
        "font_file": record["font_file"],
        "style_handle": record["style_handle"],
        "glyph_mapping_verified": False,
        "dimension_reference_approved": False,
        "financial_quantity_approved": False,
    }
    if dxf_entity is None or dxf_entity.dxftype() != "TEXT":
        result["source_location_status"] = "MISSING_OR_RETYPE_CONVERTED_DXF"
        result["native_text_equal_ledger"] = False
        return result
    owner = str(dxf_entity.dxf.get("owner", "")).upper()
    result["dxf_owner_is_modelspace"] = owner == modelspace_record_handle.upper()
    if native_entity is None:
        result["source_location_status"] = (
            "DXF_NON_MODELSPACE_DEFINITION_ONLY"
            if owner != modelspace_record_handle.upper()
            else "NATIVE_MODELSPACE_TEXT_ABSENT_DXF_DIRECT_MODELSPACE"
        )
        result["native_text_equal_ledger"] = False
        return result
    from core.cad.persian_text_v1 import normalize_cad_text
    raw_text = str(native_entity.dxf.get("text", "") or "")
    same = raw_text == record["decoded_unicode"]
    result["native_text_equal_ledger"] = same
    result["source_location_status"] = (
        "NATIVE_DIRECT_MODELSPACE_RAW_TEXT_MATCHED_GLYPHS_UNVERIFIED"
        if same and owner == modelspace_record_handle.upper()
        else "SOURCE_TEXT_OR_OWNER_MISMATCH_UNVERIFIED"
    )
    # The only exported interpretation is diagnostic, not a rewritten text.
    result["normalized_text_matches_ledger"] = (
        normalize_cad_text(raw_text) == normalize_cad_text(record["decoded_unicode"])
    )
    return result


def audit_original_shx_ledger(
    source_dwg: str | Path, dxf_path: str | Path, private_ledger_csv: str | Path,
    *, expected_record_count: int | None = None,
) -> dict[str, Any]:
    """Bind private raw-text ledger to original DWG and converted DXF read-only."""
    import ezdwg
    import ezdxf
    from importlib import metadata

    source, converted, ledger = map(Path, (source_dwg, dxf_path, private_ledger_csv))
    if (source.suffix.lower() != ".dwg" or not source.is_file()
            or not 6 < source.stat().st_size <= MAX_DWG_BYTES):
        raise ValueError("Original AC1018 DWG required")
    with source.open("rb") as header_stream:
        if header_stream.read(6) != b"AC1018":
            raise ValueError("Original AC1018 DWG required")
    if (converted.suffix.lower() != ".dxf" or not converted.is_file()
            or not 100 < converted.stat().st_size <= MAX_DXF_BYTES):
        raise ValueError("Bounded converted DXF required")
    if (ledger.suffix.lower() != ".csv" or not ledger.is_file()
            or not 10 < ledger.stat().st_size <= MAX_LEDGER_BYTES):
        raise ValueError("Private SHX ledger CSV missing or too large")
    source_hash = _digest(source)
    dxf_hash = _digest(converted)
    ledger_hash = _digest(ledger)
    with ledger.open(encoding="utf-8-sig", newline="") as inp:
        rows = validate_private_shx_ledger(list(csv.DictReader(inp)), source_sha256=source_hash)
    if expected_record_count is not None and (
        type(expected_record_count) is not int or expected_record_count != len(rows)
    ):
        raise ValueError("SHX source evidence roster size differs")
    if metadata.version("ezdwg") != "0.17.0":
        raise ValueError("Pinned native DWG decoder required")
    raw = ezdwg.read(str(source))
    if raw.version != "AC1018":
        raise ValueError("Decoder source version changed")
    dxf = ezdxf.readfile(converted)
    native = {}
    for obj in raw.modelspace().iter_entities():
        if str(obj.dxftype) == "TEXT":
            handle = format(int(obj.handle), "X")
            if handle in native:
                raise ValueError("Duplicate native TEXT handle")
            native[handle] = obj
    modelspace_owner = str(dxf.modelspace().block_record_handle).upper()
    classified = []
    for row in rows:
        entity = dxf.entitydb.get(row["handle"])
        classified.append(classify_shx_record(row, native.get(row["handle"]), entity,
                                              modelspace_record_handle=modelspace_owner))
    if any(_digest(p) != prior for p, prior in (
        (source, source_hash), (converted, dxf_hash), (ledger, ledger_hash)
    )):
        raise ValueError("Original DWG / DXF / SHX evidence changed while auditing")
    counts: dict[str, int] = {}
    for item in classified:
        status = item["source_location_status"]
        counts[status] = counts.get(status, 0) + 1
    return {
        "policy": "phase8_p2_private_shx_source_provenance_v1",
        "source_sha256": source_hash,
        "converted_dxf_sha256": dxf_hash,
        "private_ledger_sha256": ledger_hash,
        "private_shx_candidate_count": len(rows),
        "source_provenance_by_type": dict(sorted(counts.items())),
        "private_records": classified,
        "original_shx_fonts_verified": False,
        "legacy_text_glyph_mapping_verified": False,
        "dimension_references_approved": 0,
        "financial_quantities_approved": 0,
        "engineering_verdict": "PARTIAL_NO_GO",
    }