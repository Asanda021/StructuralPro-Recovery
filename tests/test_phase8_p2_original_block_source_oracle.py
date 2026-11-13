"""Synthetic original DWG standard reference regressions; no private drawings."""
import pytest

from core.drawings.dwg_original_block_source_oracle import (
    summarize_source_block_ref_coverage,
)


def example():
    headers = [
        (10, 0, 2, 49, "BLOCK_HEADER", "O"),
        (11, 1, 2, 49, "BLOCK_HEADER", "O"),
        (20, 2, 2, 14, "LINE", "E"),
        (21, 3, 2, 14, "LINE", "E"),
        (30, 4, 2, 7, "INSERT", "E"),
        (40, 5, 2, 55, "DIM_LINEAR", "E"),
    ]
    dimdata = [None] * 12
    dimdata[0] = 40
    dimdata[10] = (99, 11)
    return dict(
        source_headers=headers,
        original_line_owners=[(20, 10), (21, 10)],
        source_insert_properties=[(30, (0., 0., 1.), 11, [])],
        source_dimensions=[("linear", tuple(dimdata))],
        decoded_block_header_names=[(11, "SYNTHETIC")],
        disputed_line_handles=[20, 21],
    )


def test_missing_target_block_name_and_no_standard_links_is_not_unused_proof():
    result = summarize_source_block_ref_coverage(**example())
    assert result["source_object_header_count"] == 6
    assert result["disputed_lines_source_owner_verified_count"] == 2
    assert result["source_block_header_names_missing_count"] == 1
    assert result["disputed_block_header_name_decoded"] is False
    assert result["source_insert_typed_refs_to_disputed_block"] == 0
    assert result["source_dimension_typed_refs_to_disputed_block"] == 0
    assert result["all_original_DWG_references_verified"] is False
    assert result["block_proven_unused_in_original_DWG"] is False
    assert result["financial_quantity_approved"] is False
    assert set(result).isdisjoint({
        "source_sha256", "private_handles", "raw_record_bytes",
        "private_path", "coordinates", "geometry_values",
    })
    assert all(isinstance(value, (str, int, bool)) for value in result.values())


def test_real_target_insert_observed_without_financial_authority():
    sample = example()
    sample["source_insert_properties"] = [(30, (0., 0., 1.), 10, [])]
    result = summarize_source_block_ref_coverage(**sample)
    assert result["source_insert_typed_refs_to_disputed_block"] == 1
    assert result["status"] == "SOURCE_STANDARD_REFERENCES_OBSERVED_TO_TARGET_STILL_NO_GO"
    assert result["financial_quantity_approved"] is False


def test_real_target_dimension_reference_observed_without_automatic_takeoff():
    sample = example()
    data = list(sample["source_dimensions"][0][1])
    data[10] = (99, 10)
    sample["source_dimensions"] = [("linear", tuple(data))]
    result = summarize_source_block_ref_coverage(**sample)
    assert result["source_dimension_typed_refs_to_disputed_block"] == 1
    assert result["payable_modelspace_geometry_authorized"] is False


@pytest.mark.parametrize("change", [
    "missing_line", "wrong_owner", "missing_insert", "missing_dimension",
    "unknown_insert_block", "unknown_dimension_block", "missing_block_header",
    "duplicate_headers", "duplicate_line_owner", "duplicate_selected",
    "selected_different_owners", "wrong_selected_type", "blank_block_name",
])
def test_invalid_or_incomplete_source_fails_closed(change):
    f = example()
    if change == "missing_line":
        f["original_line_owners"].pop()
    elif change == "wrong_owner":
        f["original_line_owners"][0] = (20, 999)
    elif change == "missing_insert":
        f["source_insert_properties"] = []
    elif change == "missing_dimension":
        f["source_dimensions"] = []
    elif change == "unknown_insert_block":
        f["source_insert_properties"][0] = (30, (0,0,1), 999, [])
    elif change == "unknown_dimension_block":
        d = list(f["source_dimensions"][0][1])
        d[10] = (99, 999)
        f["source_dimensions"] = [("linear", tuple(d))]
    elif change == "missing_block_header":
        f["source_headers"] = f["source_headers"][1:]
    elif change == "duplicate_headers":
        f["source_headers"].append(f["source_headers"][0])
    elif change == "duplicate_line_owner":
        f["original_line_owners"].append((20, 10))
    elif change == "duplicate_selected":
        f["disputed_line_handles"] = [20, 20]
    elif change == "selected_different_owners":
        f["original_line_owners"][0] = (20, 11)
    elif change == "wrong_selected_type":
        f["source_headers"][2] = (20, 2, 2, 7, "INSERT", "E")
    elif change == "blank_block_name":
        f["decoded_block_header_names"] = [(11, "")]
    with pytest.raises(ValueError):
        summarize_source_block_ref_coverage(**f)


def test_named_block_never_authorizes_any_payable_geometry():
    f = example()
    f["decoded_block_header_names"].append((10, "SYNTHETIC_TARGET"))
    r = summarize_source_block_ref_coverage(**f)
    assert r["disputed_block_header_name_decoded"] is True
    assert r["financial_quantity_approved"] is False


def test_unowned_unrelated_line_can_be_in_source_roster():
    f = example()
    f["source_headers"].append((60, 6, 2, 14, "LINE", "E"))
    f["original_line_owners"].append((60, None, 0))
    r = summarize_source_block_ref_coverage(**f)
    assert r["original_line_count"] == 3
    assert r["disputed_lines_source_owner_verified_count"] == 2


def test_selected_line_without_owner_rejected():
    f = example()
    f["original_line_owners"][0] = (20, None, 0)
    with pytest.raises(ValueError):
        summarize_source_block_ref_coverage(**f)
