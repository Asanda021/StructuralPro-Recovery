"""Original AC1018 BLOCK ownership audit. Aggregates only; no payable approval.

The independent ezdwg reader's standard INSERT/DIMENSION links do not include
opaque MAP/AEC references and cannot prove that a block is globally unused.
"""
from __future__ import annotations

from hashlib import file_digest
from importlib import metadata
from pathlib import Path

MAX_ITEMS = 1_000_000


def _index(rows, label, *, min_cols=2):
    if not isinstance(rows, (tuple, list)) or len(rows) > MAX_ITEMS:
        raise ValueError("Unbounded original " + label)
    records = {}
    for row in rows:
        if (not isinstance(row, (list, tuple)) or len(row) < min_cols
                or type(row[0]) is not int or not 0 < row[0] < 2**64
                or row[0] in records):
            raise ValueError("Malformed or repeated original " + label)
        records[row[0]] = row
    return records


def summarize_source_block_ref_coverage(
    *, source_headers, original_line_owners, source_insert_properties,
    source_dimensions, decoded_block_header_names, disputed_line_handles,
):
    """Require complete typed source rosters and verify 1..64 selected LINE owners."""
    objects = _index(source_headers, "object headers", min_cols=6)
    if not objects or any(not isinstance(row[4], str) for row in objects.values()):
        raise ValueError("Missing original object type inventory")
    types = {h: row[4].upper() for h, row in objects.items()}
    lines = {h for h, kind in types.items() if kind == "LINE"}
    inserts = {h for h, kind in types.items() if kind == "INSERT"}
    dimensions = {h for h, kind in types.items() if kind.startswith("DIM_")}
    blocks = {h for h, kind in types.items() if kind == "BLOCK_HEADER"}
    if (not isinstance(disputed_line_handles, (tuple, list))
            or not 1 <= len(disputed_line_handles) <= 64
            or any(type(h) is not int or not 0 < h < 2**64
                   for h in disputed_line_handles)
            or len(set(disputed_line_handles)) != len(disputed_line_handles)
            or not set(disputed_line_handles) <= lines):
        raise ValueError("Invalid disputed original LINE selection")
    owners = _index(original_line_owners, "LINE owners")
    if (set(owners) != lines
            or any(row[1] is not None and type(row[1]) is not int
                   for row in owners.values())):
        raise ValueError("Original LINE owner inventory incomplete")
    target_owners = {owners[h][1] for h in disputed_line_handles}
    if len(target_owners) != 1 or None in target_owners:
        raise ValueError("Selected LINE owner unresolved or not unique")
    target = next(iter(target_owners))
    if target not in blocks:
        raise ValueError("Selected LINE owner not a BLOCK_HEADER")
    names = _index(decoded_block_header_names, "BLOCK_HEADER names")
    named = set(names) & blocks
    if any(not isinstance(names[h][1], str) or not names[h][1].strip()
           for h in named):
        raise ValueError("Invalid original BLOCK_HEADER name")
    if not isinstance(source_insert_properties, (tuple, list)):
        raise ValueError("Missing INSERT reference data")
    insert_refs = _index(source_insert_properties, "INSERT references", min_cols=4)
    if (set(insert_refs) != inserts
            or any(type(row[2]) is not int or row[2] not in blocks
                   for row in insert_refs.values())):
        raise ValueError("INSERT roster lacks original block references")
    if not isinstance(source_dimensions, (tuple, list)):
        raise ValueError("Missing DIMENSION reference data")
    dim_refs = {}
    for item in source_dimensions:
        if (not isinstance(item, (tuple, list)) or len(item) != 2
                or not isinstance(item[1], (tuple, list)) or len(item[1]) < 11):
            raise ValueError("Malformed source DIMENSION")
        record = item[1]
        if (type(record[0]) is not int or record[0] in dim_refs
                or not isinstance(record[10], (tuple, list))
                or len(record[10]) != 2 or type(record[10][1]) is not int):
            raise ValueError("Invalid original DIMENSION block reference")
        dim_refs[record[0]] = record[10][1]
    if set(dim_refs) != dimensions or any(ref not in blocks for ref in dim_refs.values()):
        raise ValueError("DIMENSION block reference roster incomplete")
    match_inserts = sum(row[2] == target for row in insert_refs.values())
    match_dims = sum(ref == target for ref in dim_refs.values())
    return {
        "policy": "p8p2_original_ac1018_typed_block_roster_v1",
        "source_object_header_count": len(objects),
        "original_line_count": len(lines),
        "disputed_lines_source_owner_verified_count": len(disputed_line_handles),
        "source_block_header_count": len(blocks),
        "source_block_header_names_decoded_count": len(named),
        "source_block_header_names_missing_count": len(blocks - named),
        "disputed_block_header_name_decoded": target in named,
        "source_insert_typed_references_covered": len(insert_refs),
        "source_dimension_typed_references_covered": len(dim_refs),
        "source_insert_typed_refs_to_disputed_block": match_inserts,
        "source_dimension_typed_refs_to_disputed_block": match_dims,
        "typed_standard_ref_roster_complete_in_reader": True,
        "custom_MAP_AEC_reference_graph_verified": False,
        "all_original_DWG_references_verified": False,
        "block_proven_unused_in_original_DWG": False,
        "payable_modelspace_geometry_authorized": False,
        "financial_quantity_approved": False,
        "status": ("SOURCE_STANDARD_REFERENCES_OBSERVED_TO_TARGET_STILL_NO_GO"
                   if match_inserts or match_dims else
                   "NO_STANDARD_SOURCE_REFERENCES_TO_TARGET_BUT_OTHER_LINKS_UNVERIFIED_NO_GO"),
    }


def audit_original_dwg_block_references(
    original_dwg, disputed_line_handles, *, expected_original_sha256
):
    """SHA-bound original-DWG diagnostic with no private source details returned."""
    import ezdwg
    source = Path(original_dwg)
    if (not source.is_file() or source.is_symlink()
            or source.suffix.casefold() != ".dwg"
            or not 6 < source.stat().st_size <= 50 * 1024 * 1024):
        raise ValueError("Original DWG missing or outside size cap")
    if (not isinstance(expected_original_sha256, str)
            or len(expected_original_sha256) != 64
            or any(c not in "0123456789abcdefABCDEF"
                   for c in expected_original_sha256)):
        raise ValueError("Invalid frozen source SHA")
    if metadata.version("ezdwg") != "0.17.0":
        raise ValueError("Original DWG reader must be ezdwg==0.17.0")
    with source.open("rb") as fh:
        if fh.read(6) != b"AC1018":
            raise ValueError("Original raw audit supports AC1018 only")
        fh.seek(0)
        initial = file_digest(fh, "sha256").hexdigest()
    if initial != expected_original_sha256.lower():
        raise ValueError("Source mismatches private manifest")
    path = str(source)
    receipt = summarize_source_block_ref_coverage(
        source_headers=ezdwg.raw.list_object_headers_with_type(path, limit=MAX_ITEMS),
        original_line_owners=ezdwg.raw.decode_line_owner_handles(path),
        source_insert_properties=ezdwg.raw.decode_insert_write_properties(path),
        source_dimensions=ezdwg.raw.decode_dimension_entities(path),
        decoded_block_header_names=ezdwg.raw.decode_block_header_names(path),
        disputed_line_handles=disputed_line_handles,
    )
    with source.open("rb") as fh:
        if file_digest(fh, "sha256").hexdigest() != initial:
            raise ValueError("Original source changed while auditing")
    return {**receipt, "source_manifest_matched_and_unchanged": True,
            "reader": "ezdwg==0.17.0"}
