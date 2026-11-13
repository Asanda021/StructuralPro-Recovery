"""Synthetic-only sort table parity regressions; no user's DWG/DXF input."""
from pathlib import Path
import ezdxf
import pytest
from tools.p8p2_independent_sort_pair_parity import (
    compare_sortentstable, SortParityInputError,
)


def _synthetic(path: Path, orders: tuple[str, str] = ("A", "B"),
               *, omit_sort: bool = False, reverse: bool = False,
               wrong_type: bool = False):
    d = ezdxf.new("R2018")
    msp = d.modelspace()
    a = msp.add_line((0, 0), (1, 1))
    b = msp.add_line((2, 2), (3, 3)) if not wrong_type else msp.add_circle((2, 2), 1)
    if not omit_sort:
        t = d.objects.new_entity("SORTENTSTABLE", dxfattribs={"owner": d.rootdict.dxf.handle})
        values = [(a.dxf.handle, orders[0]), (b.dxf.handle, orders[1])]
        t.set_handles(reversed(values) if reverse else values)
    d.saveas(str(path))
    return path


def test_exact_pair_match_preserves_financial_veto(tmp_path):
    a = _synthetic(tmp_path / "independent.dxf")
    b = _synthetic(tmp_path / "candidate.dxf", reverse=True)
    result = compare_sortentstable(a, b)
    assert result["pair_parity_pass"] is True
    assert result["independent_reader_sort_pairs"] == 2
    assert result["missing_sort_pair_keys"] == 0
    assert result["different_order_values_on_common_keys"] == 0
    assert result["financial_quantity_approved"] is False
    assert result["automatic_converter_integration_authorized"] is False
    assert result["raw_dwg_object_bytes_independently_verified"] is False
    assert not any("handle_value" in k or "path" in k for k in result)


def test_mutated_sort_value_is_rejected(tmp_path):
    a = _synthetic(tmp_path / "independent.dxf")
    b = _synthetic(tmp_path / "candidate.dxf", orders=("A", "C"))
    r = compare_sortentstable(a, b)
    assert r["pair_parity_pass"] is False
    assert r["different_order_values_on_common_keys"] == 1
    assert r["status"] == "MISMATCH_NO_GO"


def test_wrong_entity_kind_is_rejected(tmp_path):
    a = _synthetic(tmp_path / "independent.dxf")
    b = _synthetic(tmp_path / "candidate.dxf", wrong_type=True)
    r = compare_sortentstable(a, b)
    assert r["pair_parity_pass"] is False
    assert r["modelspace_handle_type_symmetric_difference"] > 0


def test_missing_sortents_table_fails_closed(tmp_path):
    a = _synthetic(tmp_path / "independent.dxf")
    b = _synthetic(tmp_path / "candidate.dxf", omit_sort=True)
    with pytest.raises(SortParityInputError, match="Exactly one"):
        compare_sortentstable(a, b)


def test_missing_or_invalid_file_fails_closed(tmp_path):
    a = _synthetic(tmp_path / "independent.dxf")
    with pytest.raises(SortParityInputError, match="Unsupported"):
        compare_sortentstable(a, tmp_path / "missing.dxf")
    with pytest.raises(SortParityInputError, match="Unsupported"):
        compare_sortentstable(a, tmp_path / "other.txt")


def test_partial_sort_mapping_fails_closed(tmp_path):
    a = _synthetic(tmp_path / "independent.dxf")
    b = _synthetic(tmp_path / "candidate.dxf")
    d = ezdxf.readfile(str(b))
    table = list(d.objects.query("SORTENTSTABLE"))[0]
    key = next(iter(table.table.keys()))
    table.table.pop(key)
    d.saveas(str(b))
    r = compare_sortentstable(a, b)
    assert r["pair_parity_pass"] is False
    assert r["missing_sort_pair_keys"] == 1
    assert r["candidate_modelspace_entities_without_sort_key"] == 1
