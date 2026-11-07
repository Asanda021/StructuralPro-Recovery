"""Read-only, private-input DXF SORTENTSTABLE pair parity oracle for P8/P2.

Two different readers must independently convert the *same verified source DWG*;
this function cannot establish provenance itself. Never prints or returns
source handles, geometry, sort values, user paths, file SHA, or names.
Matched pairs are not evidence of reliable proprietary objects, units or BOQ.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

_MAX_DXF_BYTES = 250_000_000
_MAX_ENTITIES = 1_000_000


class SortParityInputError(ValueError):
    """Unsupported input, missing sort associations or unreliable DXF data."""


def _handle(value: object) -> str:
    if not isinstance(value, str):
        raise SortParityInputError("Invalid handle representation")
    value = value.upper().strip()
    if not value or any(c not in "0123456789ABCDEF" for c in value):
        raise SortParityInputError("Invalid hexadecimal handle")
    return value.lstrip("0") or "0"


def _extract(path: str | Path) -> tuple[dict[str, str], dict[str, str]]:
    import ezdxf
    path = Path(path)
    if (path.suffix.casefold() != ".dxf" or path.is_symlink()
            or not path.is_file() or not 0 < path.stat().st_size <= _MAX_DXF_BYTES):
        raise SortParityInputError("Unsupported DXF input")
    try:
        doc = ezdxf.readfile(str(path))
        tables = list(doc.objects.query("SORTENTSTABLE"))
        if len(tables) != 1:
            raise SortParityInputError("Exactly one SORTENTSTABLE is required")
        raw_table = tables[0].table
        if not 0 < len(raw_table) <= _MAX_ENTITIES:
            raise SortParityInputError("Missing or unbounded sort associations")
        association: dict[str, str] = {}
        for raw_entity, raw_sort in raw_table.items():
            entity, order = _handle(raw_entity), _handle(raw_sort)
            if entity in association:
                raise SortParityInputError("Duplicate normalized sort entity handle")
            association[entity] = order
        model: dict[str, str] = {}
        for item in doc.modelspace():
            handle = _handle(item.dxf.handle)
            if handle in model:
                raise SortParityInputError("Duplicate ModelSpace handle")
            model[handle] = item.dxftype()
            if len(model) > _MAX_ENTITIES:
                raise SortParityInputError("Unbounded ModelSpace entities")
        return association, model
    except SortParityInputError:
        raise
    except Exception as exc:
        raise SortParityInputError("Cannot independently inspect DXF sort associations") from exc


def compare_sortentstable(
    independent_dxf: str | Path, candidate_dxf: str | Path,
) -> dict[str, Any]:
    """Count 1:1 mapping differences without exposing private mapping or origin."""
    source, source_msp = _extract(independent_dxf)
    candidate, candidate_msp = _extract(candidate_dxf)
    source_keys, target_keys = set(source), set(candidate)
    common = source_keys & target_keys
    missing = len(source_keys - target_keys)
    extra = len(target_keys - source_keys)
    different = sum(source[k] != candidate[k] for k in common)
    modelspace_diff = len(set(source_msp.items()) ^ set(candidate_msp.items()))
    source_outside = len(source_keys - set(source_msp))
    candidate_outside = len(target_keys - set(candidate_msp))
    source_unmapped = len(set(source_msp) - source_keys)
    candidate_unmapped = len(set(candidate_msp) - target_keys)
    matched = all(x == 0 for x in (
        missing, extra, different, modelspace_diff, source_outside,
        candidate_outside, source_unmapped, candidate_unmapped,
    )) and len(source) == len(candidate) and len(source_msp) == len(candidate_msp)
    return {
        "policy": "p8p2_two_reader_sort_pair_structural_parity_v1",
        "independent_reader_sort_pairs": len(source),
        "candidate_sort_pairs": len(candidate),
        "independent_modelspace_entities": len(source_msp),
        "candidate_modelspace_entities": len(candidate_msp),
        "missing_sort_pair_keys": missing,
        "extra_sort_pair_keys": extra,
        "different_order_values_on_common_keys": different,
        "modelspace_handle_type_symmetric_difference": modelspace_diff,
        "sort_keys_not_in_independent_modelspace": source_outside,
        "sort_keys_not_in_candidate_modelspace": candidate_outside,
        "independent_modelspace_entities_without_sort_key": source_unmapped,
        "candidate_modelspace_entities_without_sort_key": candidate_unmapped,
        "independent_sort_values_unique": len(set(source.values())) == len(source),
        "candidate_sort_values_unique": len(set(candidate.values())) == len(candidate),
        "pair_parity_pass": matched,
        "status": ("MATCHED_TWO_CONVERTER_DXF_PAIRS_ONLY_REQUIRES_SOURCE_PROVENANCE"
                   if matched else "MISMATCH_NO_GO"),
        "original_dwg_source_provenance_verified_by_this_function": False,
        "raw_dwg_object_bytes_independently_verified": False,
        "engineering_source_integrity_approved": False,
        "financial_quantity_approved": False,
        "automatic_converter_integration_authorized": False,
    }
