"""Private-safe, read-only comparison of original-DWG custom-link observations.

The source 'OBJECTS' roster can derive from an impaired LibreDWG reader; the
independent reader confirms *raw record identity*, but its standard graph API
does not establish completeness of custom owner/reactor/dictionary links.
This audit NEVER calls those links proven, used/unused or payable. Only
aggregate counts are returned, without source IDs, names, bytes or coordinates.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

_MAX_SOURCE_OBJECTS = 1_000_000
_MAX_CUSTOM = 64
_MAX_EDGES = 1_000_000


def _source_handle(value):
    """Decode a LibreDWG reference list without exposing the private ID."""
    if (not isinstance(value, (tuple, list)) or len(value) < 3
            or type(value[-1]) is not int or not 0 <= value[-1] < 2**64):
        raise ValueError("Malformed original DWG handle/reference")
    return value[-1]


def _verified_raw_handle(text):
    if (not isinstance(text, str) or not text
            or any(ch not in "0123456789ABCDEFabcdef" for ch in text)):
        raise ValueError("Invalid independent raw source identity")
    number = int(text, 16)
    if not 0 < number < 2**64:
        raise ValueError("Invalid independent raw source identity")
    return number


def audit_custom_graph_coverage(
    decoded_source_objects: Sequence[Mapping],
    independently_recorded_custom_objects: Sequence[Mapping],
    independent_standard_graph_edges: Sequence,
    *,
    converted_dxf=None,
):
    """Bounded source inventory vs incomplete standard-reader graph check.

    Caller must verify original DWG SHA and independently authenticated record
    metadata before invoking. A matched graph is still NOT semantic parity.
    """
    if (not isinstance(decoded_source_objects, (list, tuple))
            or not 1 <= len(decoded_source_objects) <= _MAX_SOURCE_OBJECTS
            or not isinstance(independently_recorded_custom_objects, (list, tuple))
            or not 1 <= len(independently_recorded_custom_objects) <= _MAX_CUSTOM
            or not isinstance(independent_standard_graph_edges, (list, tuple))
            or len(independent_standard_graph_edges) > _MAX_EDGES):
        raise ValueError("Missing, unbounded or invalid original source evidence")

    index = {}
    for obj in decoded_source_objects:
        if not isinstance(obj, Mapping):
            raise ValueError("Malformed decoded original source object")
        handle = _source_handle(obj.get("handle"))
        if not handle or handle in index:
            raise ValueError("Duplicate or null original source object")
        index[handle] = obj

    custom = {}
    for record in independently_recorded_custom_objects:
        if (not isinstance(record, Mapping)
                or type(record.get("native_type_code")) is not int):
            raise ValueError("Independent custom source type receipt missing")
        h = _verified_raw_handle(record.get("handle"))
        obj = index.get(h)
        if (h in custom or obj is None or obj.get("object") != "UNKNOWN_OBJ"
                or type(obj.get("type")) is not int
                or obj["type"] != record["native_type_code"]):
            raise ValueError("Original custom type/identity disagrees with independent raw receipt")
        custom[h] = obj

    custom_ids = set(custom)
    owner_custom = owner_dictionary = reactor_custom = reactor_dictionary = 0
    unresolved_links = 0
    owner_graph = {}
    for h, obj in custom.items():
        parent = _source_handle(obj.get("ownerhandle"))
        parent_obj = index.get(parent)
        if parent in custom_ids:
            owner_custom += 1
            owner_graph[h] = parent
        elif parent_obj is not None and parent_obj.get("object") == "DICTIONARY":
            owner_dictionary += 1
        else:
            # An unknown or zero owner cannot be treated as a benign empty
            # ownership path; abort rather than continue with false coverage.
            raise ValueError("Custom object owner missing or unsupported")
        reactors = obj.get("reactors", [])
        if not isinstance(reactors, (list, tuple)):
            raise ValueError("Malformed custom object reactor vector")
        for ref in reactors:
            target = _source_handle(ref)
            other = index.get(target)
            if target in custom_ids:
                reactor_custom += 1
            elif other is not None and other.get("object") == "DICTIONARY":
                reactor_dictionary += 1
            else:
                unresolved_links += 1

    # Cyclic ownership in the decoded roster is a blocker, not a repair hint.
    for h in custom_ids:
        visited = set()
        node = h
        while node in owner_graph:
            if node in visited or len(visited) > _MAX_CUSTOM:
                raise ValueError("Cyclic source custom ownership")
            visited.add(node)
            node = owner_graph[node]

    dictionary_direct = 0
    for obj in index.values():
        if obj.get("object") != "DICTIONARY":
            continue
        entries = obj.get("items", {})
        if not isinstance(entries, Mapping):
            raise ValueError("Malformed source dictionary entries")
        for value in entries.values():
            if _source_handle(value) in custom_ids:
                dictionary_direct += 1

    # An independent graph API that omits all custom nodes cannot prove they
    # have no real links. Validate tuples, count only matching custom endpoints.
    independent_custom_edge_count = 0
    corroborating_custom_edges = 0
    conflicting_custom_edges = 0
    seen_independent_edges = set()
    for edge in independent_standard_graph_edges:
        if (not isinstance(edge, (tuple, list)) or len(edge) != 3
                or type(edge[0]) is not int or type(edge[2]) is not int
                or not isinstance(edge[1], str) or not 0 < len(edge[1]) <= 128):
            raise ValueError("Malformed independent graph edge")
        source, relationship, target = edge
        # A reader's unbacked endpoint must not be counted as evidence
        # that it independently covered a proprietary object link.
        if source not in index or target not in index:
            raise ValueError("Independent graph edge references an unindexed source object")
        identity = (source, relationship, target)
        if identity in seen_independent_edges:
            raise ValueError("Duplicate independent graph edge cannot increase coverage")
        seen_independent_edges.add(identity)
        if source in custom_ids or target in custom_ids:
            independent_custom_edge_count += 1
            # An arbitrary relationship label or merely touching an unknown
            # custom node is NOT proof of cross-reader link agreement.
            # Check only established, direction-specific standard relationships.
            decoded_match = None
            if relationship == "owner" and source in custom_ids:
                decoded_match = _source_handle(custom[source].get("ownerhandle")) == target
            elif relationship == "reactor" and source in custom_ids:
                decoded_match = any(_source_handle(ref) == target
                                    for ref in custom[source].get("reactors", []))
            elif (relationship in ("dictionary", "dictionary_item", "item")
                  and target in custom_ids
                  and index[source].get("object") == "DICTIONARY"):
                decoded_match = any(_source_handle(ref) == target
                                    for ref in index[source].get("items", {}).values())
            if decoded_match is True:
                corroborating_custom_edges += 1
            elif decoded_match is False:
                conflicting_custom_edges += 1

    dxfs_found = None
    if converted_dxf is not None:
        if not hasattr(converted_dxf, "entitydb"):
            raise ValueError("DXF lacks entity identity index")
        dxfs_found = sum(converted_dxf.entitydb.get(format(h, "X")) is not None
                         for h in custom_ids)

    return {
        "policy": "p8p2_custom_source_graph_coverage_not_semantic_parity_v1",
        "raw_source_custom_identity_count": len(custom_ids),
        "decoded_custom_owner_to_custom_count": owner_custom,
        "decoded_custom_owner_to_dictionary_count": owner_dictionary,
        "decoded_custom_reactor_to_custom_count": reactor_custom,
        "decoded_custom_reactor_to_dictionary_count": reactor_dictionary,
        "decoded_dictionary_entry_to_custom_count": dictionary_direct,
        "decoded_unresolved_custom_links_count": unresolved_links,
        "independent_standard_graph_edges_count": len(independent_standard_graph_edges),
        "independent_graph_edges_touching_custom_count": independent_custom_edge_count,
        "independent_custom_links_corresponding_to_decoded_count": corroborating_custom_edges,
        "independent_custom_links_conflicting_with_decoded_count": conflicting_custom_edges,
        "independent_custom_edges_not_comparable_count": (
            independent_custom_edge_count - corroborating_custom_edges - conflicting_custom_edges
        ),
        "converted_original_custom_ids_present_count": dxfs_found,
        "independent_reader_custom_link_coverage_verified": False,
        "source_proprietary_payload_semantics_verified": False,
        "all_source_custom_links_verified": False,
        "original_block_proven_unused": False,
        "automatic_reconstruction_authorized": False,
        "financial_quantity_approved": False,
        "status": ("CROSS_READER_CUSTOM_LINK_CONFLICT_NO_GO"
                   if conflicting_custom_edges
                   else "CROSS_READER_CUSTOM_LINK_COVERAGE_GAP_NO_GO"
                   if (owner_custom + owner_dictionary + reactor_custom +
                       reactor_dictionary + dictionary_direct) and
                      corroborating_custom_edges == 0
                   else "CUSTOM_GRAPH_SEMANTICS_UNVERIFIED_NO_GO"),
    }
