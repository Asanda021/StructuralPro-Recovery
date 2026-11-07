"""Synthetic-only source MAP/AEC edge-coverage veto. No private DWG data."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.drawings.dwg_custom_graph_coverage import audit_custom_graph_coverage


def ref(handle):
    return [5, 1, handle]


def fixture():
    objects = [
        dict(handle=ref(1), object="DICTIONARY",
             items={"MAP": ref(10), "STYLE": ref(11)}),
        dict(handle=ref(10), object="UNKNOWN_OBJ", type=514,
             ownerhandle=ref(1), reactors=[ref(1)]),
        dict(handle=ref(11), object="UNKNOWN_OBJ", type=515,
             ownerhandle=ref(1), reactors=[ref(10)]),
        dict(handle=ref(12), object="UNKNOWN_OBJ", type=516,
             ownerhandle=ref(10), reactors=[ref(10), ref(11)]),
        dict(handle=ref(30), object="LINE", type=1),
        dict(handle=ref(40), object="LAYER", type=2),
    ]
    raw = [
        {"handle": "A", "native_type_code": 514},
        {"handle": "B", "native_type_code": 515},
        {"handle": "C", "native_type_code": 516},
    ]
    return objects, raw, [(30, "layer", 40)]


def test_custom_owners_reactors_not_exposed_by_standard_graph():
    obj, raw, edges = fixture()
    r = audit_custom_graph_coverage(
        obj, raw, edges, converted_dxf=SimpleNamespace(entitydb={})
    )
    assert r["raw_source_custom_identity_count"] == 3
    assert r["decoded_custom_owner_to_custom_count"] == 1
    assert r["decoded_custom_owner_to_dictionary_count"] == 2
    assert r["decoded_custom_reactor_to_custom_count"] == 3
    assert r["decoded_custom_reactor_to_dictionary_count"] == 1
    assert r["decoded_dictionary_entry_to_custom_count"] == 2
    assert r["independent_graph_edges_touching_custom_count"] == 0
    assert r["converted_original_custom_ids_present_count"] == 0
    assert r["status"] == "CROSS_READER_CUSTOM_LINK_COVERAGE_GAP_NO_GO"
    assert not r["original_block_proven_unused"]
    assert not r["financial_quantity_approved"]
    assert not any(isinstance(v, (list, tuple, dict)) for v in r.values())


def test_independent_reader_some_links_still_not_sufficient():
    obj, raw, edges = fixture()
    edges += [(10, "owner", 1)]
    r = audit_custom_graph_coverage(obj, raw, edges)
    assert r["independent_graph_edges_touching_custom_count"] == 1
    assert r["status"] == "CUSTOM_GRAPH_SEMANTICS_UNVERIFIED_NO_GO"
    assert r["all_source_custom_links_verified"] is False


def test_synthetic_dxfs_with_same_handles_cannot_pass_semantics():
    obj, raw, edges = fixture()
    r = audit_custom_graph_coverage(
        obj, raw, edges,
        converted_dxf=SimpleNamespace(entitydb={
            "A": object(), "B": object(), "C": object(),
        }),
    )
    assert r["converted_original_custom_ids_present_count"] == 3
    assert r["source_proprietary_payload_semantics_verified"] is False
    assert r["automatic_reconstruction_authorized"] is False


@pytest.mark.parametrize("bad", [
    "empty", "duplicated_source_handle", "duplicate_raw", "raw_type_conflict",
    "unknown_raw_handle", "null_owner", "unknown_owner",
    "invalid_reactor_reference", "cyclic_ownership", "invalid_dictionary_items",
    "invalid_graph_edge", "invalid_raw_type", "malformed_raw_handle",
])
def test_bad_source_or_unverifiable_graph_fails_closed(bad):
    objects, raw, edges = deepcopy(fixture())
    if bad == "empty":
        objects = []
    elif bad == "duplicated_source_handle":
        objects.append(dict(objects[1]))
    elif bad == "duplicate_raw":
        raw.append(dict(raw[0]))
    elif bad == "raw_type_conflict":
        raw[0]["native_type_code"] = 999
    elif bad == "unknown_raw_handle":
        raw[0]["handle"] = "DDDD"
    elif bad == "null_owner":
        objects[1]["ownerhandle"] = ref(0)
    elif bad == "unknown_owner":
        objects[1]["ownerhandle"] = ref(900)
    elif bad == "invalid_reactor_reference":
        objects[2]["reactors"] = ["INVALID"]
    elif bad == "cyclic_ownership":
        objects[1]["ownerhandle"] = ref(12)
    elif bad == "invalid_dictionary_items":
        objects[0]["items"] = "bad"
    elif bad == "invalid_graph_edge":
        edges.append((10, "owner"))
    elif bad == "invalid_raw_type":
        raw[0]["native_type_code"] = True
    elif bad == "malformed_raw_handle":
        raw[0]["handle"] = "A??"
    with pytest.raises(ValueError):
        audit_custom_graph_coverage(objects, raw, edges)
