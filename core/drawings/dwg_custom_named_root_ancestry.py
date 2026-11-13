"""Bounded original-AC1018 MAP/AEC source ownership ancestry diagnostic.

Read-only, aggregate counts only. The source OBJECTS and CLASSES come from a
SHA-bound but impaired LibreDWG decoder snapshot. Independently read raw DWG
record identity/type must be authenticated by the caller. This check proves
only consistency of decoded ownership and reciprocal named-dictionary entries;
it does NOT decode the private custom payload, all reactors, or their semantics,
and NEVER approves quantity or replacement geometry.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

MAX_SOURCE_OBJECTS = 1_000_000
MAX_CLASSES = 512
MAX_CUSTOM_RECORDS = 64
MAX_OWNER_DEPTH = 64
ROOTS = ("Autodesk_MAP", "AEC_VARS")


def _ref(value):
    if (not isinstance(value, (tuple, list)) or len(value) < 3
            or type(value[-1]) is not int or not 0 < value[-1] < 2**64):
        raise ValueError("Invalid original DWG source reference")
    return value[-1]


def _raw_id(value):
    if (not isinstance(value, str) or not value
            or any(ch not in "0123456789abcdefABCDEF" for ch in value)):
        raise ValueError("Invalid independent source record identity")
    h = int(value, 16)
    if not 0 < h < 2**64:
        raise ValueError("Null or oversized independent source identity")
    return h


def _class_root(app):
    if app == "AcMapDisplayManagement":
        return "Autodesk_MAP"
    if (isinstance(app, str) and app.startswith("AecBase40|")
            and "Autodesk Architectural Desktop 2005" in app):
        return "AEC_VARS"
    raise ValueError("Unknown original class source family, cannot infer named root")


def audit_custom_named_root_ancestry(
    decoded_objects: Sequence[Mapping],
    original_classes: Sequence[Mapping],
    independently_verified_raw_records: Sequence[Mapping],
) -> dict:
    """Crosscheck decoded custom ownership paths vs original class family.

    All source files/reader revisions and raw record byte hashes must have
    been verified outside this pure auditor before invoking it.
    """
    if (not isinstance(decoded_objects, (list, tuple))
            or not 1 <= len(decoded_objects) <= MAX_SOURCE_OBJECTS
            or not isinstance(original_classes, (list, tuple))
            or not 1 <= len(original_classes) <= MAX_CLASSES
            or not isinstance(independently_verified_raw_records, (list, tuple))
            or not 1 <= len(independently_verified_raw_records) <= MAX_CUSTOM_RECORDS):
        raise ValueError("Missing or unbounded authenticated source evidence")

    index = {}
    for item in decoded_objects:
        if not isinstance(item, Mapping):
            raise ValueError("Invalid original object entry")
        h = _ref(item.get("handle"))
        if h in index:
            raise ValueError("Repeated original DWG object identity")
        index[h] = item

    classes = {}
    for item in original_classes:
        if not isinstance(item, Mapping) or type(item.get("number")) is not int:
            raise ValueError("Malformed original class")
        number = item["number"]
        if number in classes:
            raise ValueError("Duplicate original custom class ID")
        classes[number] = item

    candidates = []
    for h, item in index.items():
        if item.get("object") != "DICTIONARY":
            continue
        entries = item.get("items")
        if not isinstance(entries, Mapping):
            raise ValueError("Malformed original source dictionary entries")
        if all(k in entries for k in ROOTS):
            candidates.append((h, item))
    if len(candidates) != 1:
        raise ValueError("Named root dictionary missing or ambiguous")
    root_object = candidates[0][1]
    root_handles = {_ref(root_object["items"][key]): key for key in ROOTS}
    if len(root_handles) != len(ROOTS):
        raise ValueError("Named MAP/AEC roots collide")
    for root_handle in root_handles:
        if index.get(root_handle, {}).get("object") != "DICTIONARY":
            raise ValueError("Named MAP/AEC root is not a source dictionary")

    verified_ids = {_raw_id(record.get("handle")) for record in independently_verified_raw_records
                    if isinstance(record, Mapping)}
    if len(verified_ids) != len(independently_verified_raw_records):
        raise ValueError("Duplicate original raw record identities")

    # A missing *leaf* custom record can otherwise pass all ancestry checks:
    # the remaining raw records still reach the named root. Compare the
    # authenticated raw roster to the entire decoded family-specific inventory.
    # This is only a consistency check against an impaired decoder snapshot,
    # not an independent proof that every original DWG object was discovered.
    decoded_family_ids = set()
    for object_handle, candidate in index.items():
        if candidate.get("object") != "UNKNOWN_OBJ":
            continue
        native_type = candidate.get("type")
        if type(native_type) is not int:
            raise ValueError("Malformed decoded source custom object type")
        family_class = classes.get(native_type)
        if family_class is None:
            continue
        app = family_class.get("appname")
        if app == "AcMapDisplayManagement" or (
            isinstance(app, str)
            and app.startswith("AecBase40|")
            and "Autodesk Architectural Desktop 2005" in app
        ):
            decoded_family_ids.add(object_handle)
    if decoded_family_ids != verified_ids:
        raise ValueError("Independent raw roster differs from decoded MAP/AEC inventory")
    seen = set()
    depth_counts = Counter()
    family_counts = Counter()
    direct_children_checked = set()
    owner_reactors = 0
    for record in independently_verified_raw_records:
        if not isinstance(record, Mapping) or type(record.get("native_type_code")) is not int:
            raise ValueError("Invalid independently verified raw DWG object")
        h = _raw_id(record.get("handle"))
        code = record["native_type_code"]
        obj = index.get(h)
        if (h in seen or not obj or obj.get("object") != "UNKNOWN_OBJ"
                or type(obj.get("type")) is not int or obj["type"] != code):
            raise ValueError("Raw record does not match source object/class")
        seen.add(h)
        cls = classes.get(code)
        if not cls:
            raise ValueError("Unknown original class type code")
        family = _class_root(cls.get("appname"))
        if (not isinstance(cls.get("dxfname"), str)
                or not cls["dxfname"]):
            raise ValueError("Malformed original class identity")

        visited = set()
        current = h
        depth = 0
        while current not in root_handles:
            if current in visited or depth >= MAX_OWNER_DEPTH:
                raise ValueError("Original custom ownership is cyclic/deep")
            visited.add(current)
            current_obj = index.get(current)
            if current_obj is None:
                raise ValueError("Original owner path disappeared")
            parent = _ref(current_obj.get("ownerhandle"))
            depth += 1
            if parent not in root_handles:
                parent_obj = index.get(parent)
                if (parent not in verified_ids or parent_obj is None
                        or parent_obj.get("object") != "UNKNOWN_OBJ"
                        or parent == current or type(parent_obj.get("type")) is not int):
                    raise ValueError("Unverified custom ancestry or non-MAP/AEC parent")
            else:
                # Named-dictionary direct children must be reciprocally
                # addressable from their owning dictionary in the source.
                if current not in direct_children_checked:
                    children = index[parent].get("items")
                    if not isinstance(children, Mapping):
                        raise ValueError("Source named dictionary entries unavailable")
                    matches = sum(_ref(ref) == current for ref in children.values())
                    if matches != 1:
                        raise ValueError("Source named dictionary owner is not reciprocal")
                    direct_children_checked.add(current)
            current = parent
        if root_handles[current] != family:
            raise ValueError("Original MAP/AEC ownership crosses vendor root")
        family_counts[family] += 1
        depth_counts[depth] += 1
        reactors = obj.get("reactors", ())
        if not isinstance(reactors, (list, tuple)):
            raise ValueError("Malformed original custom reactor list")
        if any(_ref(r) == _ref(obj.get("ownerhandle")) for r in reactors):
            owner_reactors += 1

    if not all(family_counts.get(root, 0) > 0 for root in ROOTS):
        raise ValueError("Required named source custom family not represented")

    return {
        "policy": "p8p2_custom_named_source_ancestry_consistency_only_v1",
        "independent_source_record_type_matches": len(seen),
        "decoded_custom_count_by_named_root": dict(sorted(family_counts.items())),
        "decoded_custom_owner_depth_histogram": dict(sorted(depth_counts.items())),
        "maximum_source_custom_owner_depth": max(depth_counts),
        "direct_named_dictionary_custom_children": len(direct_children_checked),
        "reciprocal_named_dictionary_entries_verified": len(direct_children_checked),
        "decoded_custom_reactor_points_to_own_owner": owner_reactors,
        "original_custom_payload_semantics_verified": False,
        "independent_custom_owner_edges_verified": False,
        "independent_reactor_graph_complete": False,
        "source_to_converted_custom_instance_parity_verified": False,
        "automatic_missing_custom_repair_authorized": False,
        "financial_quantity_approved": False,
        "status": "DECODED_NAMED_ROOT_ANCESTRY_CONSISTENT_SEMANTICS_UNVERIFIED_NO_GO",
    }
