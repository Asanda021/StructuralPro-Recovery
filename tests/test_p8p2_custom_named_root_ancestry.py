"""Synthetic source graph tests: no private DWG/object identities or geometry."""
from copy import deepcopy

import pytest

from core.drawings.dwg_custom_named_root_ancestry import audit_custom_named_root_ancestry


def ref(n):
    return [5, 1, n]


def sample():
    objects = [
        dict(handle=ref(1), object="DICTIONARY",
             items={"Autodesk_MAP": ref(2), "AEC_VARS": ref(3)}),
        dict(handle=ref(2), object="DICTIONARY",
             items={"MAP": ref(10), "STYLE": ref(11)}),
        dict(handle=ref(3), object="DICTIONARY",
             items={"AEC": ref(21)}),
        dict(handle=ref(10), object="UNKNOWN_OBJ", type=514,
             ownerhandle=ref(2), reactors=[ref(2)]),
        dict(handle=ref(11), object="UNKNOWN_OBJ", type=515,
             ownerhandle=ref(2), reactors=[]),
        dict(handle=ref(12), object="UNKNOWN_OBJ", type=516,
             ownerhandle=ref(10), reactors=[ref(10)]),
        dict(handle=ref(13), object="UNKNOWN_OBJ", type=517,
             ownerhandle=ref(12), reactors=[ref(12)]),
        dict(handle=ref(14), object="UNKNOWN_OBJ", type=518,
             ownerhandle=ref(13), reactors=[]),
        dict(handle=ref(21), object="UNKNOWN_OBJ", type=521,
             ownerhandle=ref(3), reactors=[ref(3)]),
    ]
    classes = [
        {"number": code, "dxfname": name,
         "appname": ("AcMapDisplayManagement" if code != 521 else
                     "AecBase40|Product Desc: Autodesk Architectural Desktop 2005")}
        for code, name in [
            (514, "DM1"), (515, "DM2"), (516, "DM3"),
            (517, "DM4"), (518, "DM5"), (521, "AEC1")
        ]
    ]
    raw = [{"handle": format(h, "X"), "native_type_code": c}
           for h, c in [(10, 514), (11, 515), (12, 516),
                        (13, 517), (14, 518), (21, 521)]]
    return objects, classes, raw


def test_named_root_lineage_counts_unique_reciprocal_edges():
    r = audit_custom_named_root_ancestry(*sample())
    assert r["independent_source_record_type_matches"] == 6
    assert r["decoded_custom_count_by_named_root"] == {
        "Autodesk_MAP": 5, "AEC_VARS": 1,
    }
    assert r["decoded_custom_owner_depth_histogram"] == {1: 3, 2: 1, 3: 1, 4: 1}
    assert r["maximum_source_custom_owner_depth"] == 4
    assert r["direct_named_dictionary_custom_children"] == 3
    assert r["reciprocal_named_dictionary_entries_verified"] == 3
    assert r["decoded_custom_reactor_points_to_own_owner"] == 4
    assert r["status"].endswith("NO_GO")
    assert not r["independent_custom_owner_edges_verified"]
    assert not r["original_custom_payload_semantics_verified"]
    assert not r["financial_quantity_approved"]


def test_same_source_handle_does_not_become_private_output_key():
    r = audit_custom_named_root_ancestry(*sample())
    assert not any(str(v) == 'A' or str(v) == '15' for v in r.values())
    assert not any("source_sha" in k or "handle" in k or "coordinates" in k for k in r)


@pytest.mark.parametrize("mutation", [
    "missing_named_root", "ambiguous_named_root", "root_collision",
    "not_a_dictionary", "duplicate_decoded_obj", "missing_raw_record",
    "duplicate_raw_id", "wrong_raw_type", "unknown_class_family",
    "wrong_class_code", "missing_raw_ancestor", "cyclic_owner",
    "missing_direct_backlink", "duplicate_direct_backlink",
    "cross_vendor_root", "invalid_reactor", "invalid_root_pointer",
    "null_owner", "wrong_root_child_type",
])
def test_broken_source_named_root_or_raw_record_fails_closed(mutation):
    objects, classes, raw = deepcopy(sample())
    if mutation == "missing_named_root":
        objects[0]["items"].pop("Autodesk_MAP")
    elif mutation == "ambiguous_named_root":
        clone = deepcopy(objects[0])
        clone["handle"] = ref(99)
        objects.append(clone)
    elif mutation == "root_collision":
        objects[0]["items"]["AEC_VARS"] = ref(2)
    elif mutation == "not_a_dictionary":
        objects[1]["object"] = "LINE"
    elif mutation == "duplicate_decoded_obj":
        objects.append(dict(objects[4]))
    elif mutation == "missing_raw_record":
        raw.pop()
    elif mutation == "duplicate_raw_id":
        raw.append(dict(raw[0]))
    elif mutation == "wrong_raw_type":
        raw[0]["native_type_code"] = 999
    elif mutation == "unknown_class_family":
        classes[0]["appname"] = "some-other-proprietary-app"
    elif mutation == "wrong_class_code":
        classes[0]["number"] = 999
    elif mutation == "missing_raw_ancestor":
        raw = [r for r in raw if r["handle"] != format(12, "X")]
    elif mutation == "cyclic_owner":
        objects[3]["ownerhandle"] = ref(14)
    elif mutation == "missing_direct_backlink":
        objects[1]["items"].pop("MAP")
    elif mutation == "duplicate_direct_backlink":
        objects[1]["items"]["DUPLICATE"] = ref(10)
    elif mutation == "cross_vendor_root":
        objects[8]["ownerhandle"] = ref(2)
        objects[2]["items"].pop("AEC")
        objects[1]["items"]["WRONG_FAMILY"] = ref(21)
    elif mutation == "invalid_reactor":
        objects[3]["reactors"] = ["bad"]
    elif mutation == "invalid_root_pointer":
        objects[0]["items"]["AEC_VARS"] = "bad"
    elif mutation == "null_owner":
        objects[3]["ownerhandle"] = ref(0)
    elif mutation == "wrong_root_child_type":
        objects[2]["object"] = "INSERT"
    with pytest.raises(ValueError):
        audit_custom_named_root_ancestry(objects, classes, raw)


def test_no_source_byte_semantics_are_inferred_from_all_links_matching():
    r = audit_custom_named_root_ancestry(*sample())
    assert r["source_to_converted_custom_instance_parity_verified"] is False
    assert r["automatic_missing_custom_repair_authorized"] is False
    assert r["financial_quantity_approved"] is False
