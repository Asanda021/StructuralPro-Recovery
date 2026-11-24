"""Non-financial evidence ledger for PDF column-layout grid positions.

An individual outlined C1/C2/C3 label, corroborating grid plan and type detail
provide a traceable *candidate* at a drawing position. They cannot establish
an installed/structural member, per-floor occurrence, quantity or payable BOQ.
This module never accepts user approval flags, and never multiplies floors.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any, Mapping


_COLUMN_KINDS = {"column_type_plan"}
_REGISTRATION = "PROPOSED_INDEPENDENT_GRID_REGISTRATION"
_TYPE = "GRID_LOCATION_VECTOR_TYPE_CANDIDATE"
_SYMBOL = "COMPACT_VECTOR_SYMBOL_CANDIDATE"


def _int(value: Any) -> int | None:
    return value if type(value) is int and value > 0 else None


def _position_key(node: Mapping) -> tuple | None:
    doc, page, row, col = node.get("document_id"), _int(node.get("page")), _int(node.get("row")), _int(node.get("column"))
    if not isinstance(doc, str) or not doc or None in (page, row, col):
        return None
    return (doc, page, row, col)


def _source_ok(node: Mapping, documents: dict) -> bool:
    doc = node.get("document_id")
    return isinstance(doc, str) and doc in documents and _int(node.get("page")) is not None and node["page"] <= documents[doc]


def _valid_detail(node: Mapping, *, source_docs: dict) -> dict | None:
    """An L dimension is a type-detail length, not member height or mass."""
    ref = node.get("cross_sheet_type_reference")
    if not isinstance(ref, Mapping) or ref.get("status") != "PROPOSED_UNVERIFIED" or ref.get("tag") != node.get("suggested_type"):
        return None
    details = ref.get("details")
    if not isinstance(details, (list, tuple)) or not details:
        return None
    chosen = []
    for d in details:
        if not isinstance(d, Mapping) or d.get("status") != "PROPOSED_UNVERIFIED":
            return None
        source, page = d.get("document_id"), _int(d.get("page"))
        if source not in source_docs or page is None or page > source_docs[source]:
            return None
        # Do not attribute a detail on another file to this drawing without
        # authoritative revision/ownership crosswalk.
        if source != node.get("document_id") or page == node.get("page"):
            return None
        if d.get("dimension_kind") != "length":
            return None
        try:
            value = Decimal(str(d.get("dimension_m")))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not value.is_finite() or value <= 0:
            return None
        chosen.append((value, source, page))
    # Conflicting or duplicate-presented type dimensions remain unresolved.
    if len({v for v, _, _ in chosen}) != 1:
        return None
    return {"source_document_id": chosen[0][1], "page": chosen[0][2],
            "type_detail_length_m": str(chosen[0][0]),
            "meaning": "TYPE_DETAIL_LENGTH_ONLY_NOT_FLOOR_HEIGHT",
            "status": "PROPOSED_UNVERIFIED"}


def compile_column_position_ledger(report: Mapping) -> dict:
    """Build auditable 4-way witnesses without accepting physical quantities.

    All inputs are untrusted parser candidates. A duplicate identity is blocked
    rather than silently counted twice. Type tally counts labeled *positions on
    a specific sheet*, not total members of a building.
    """
    if not isinstance(report, Mapping):
        raise ValueError("PDF source report required")
    docs = {}
    for d in report.get("documents", ()):
        if not isinstance(d, Mapping):
            raise ValueError("invalid PDF document record")
        key, pages = d.get("document_id"), _int(d.get("page_count"))
        if not isinstance(key, str) or not key or pages is None or key in docs:
            raise ValueError("duplicate/invalid PDF document provenance")
        docs[key] = pages
    kinds = {}
    for v in report.get("page_view_summaries", ()):
        if not isinstance(v, Mapping):
            continue
        k = (v.get("document_id"), v.get("page"))
        if k[0] in docs and _int(k[1]) and k[1] <= docs[k[0]]:
            if k in kinds and kinds[k] != (v.get("status"), v.get("sheet_kind")):
                raise ValueError("contradictory sheet title classification")
            kinds[k] = (v.get("status"), v.get("sheet_kind"))
    registrations = {}
    for item in report.get("independent_axis_grid_registrations", ()):
        if not isinstance(item, Mapping):
            continue
        col, ax = item.get("column_plan"), item.get("axis_plan")
        if (item.get("status") == _REGISTRATION and isinstance(col, Mapping) and
                isinstance(ax, Mapping)):
            col_key = (col.get("document_id"), col.get("page"))
            ax_key = (ax.get("document_id"), ax.get("page"))
            if (col_key[0] not in docs or ax_key[0] not in docs or
                col_key[0] != ax_key[0] or col_key == ax_key or
                not _int(col_key[1]) or not _int(ax_key[1]) or
                col_key[1] > docs[col_key[0]] or ax_key[1] > docs[ax_key[0]] or
                kinds.get(col_key) != ("EXPLICIT_SHEET_TITLE", "column_type_plan") or
                kinds.get(ax_key) != ("EXPLICIT_SHEET_TITLE", "axis_plan")):
                continue
            if col_key in registrations:
                # Two registration claims for one column plan cannot establish a unique map.
                registrations[col_key] = None
            else:
                registrations[col_key] = item
    rows = []
    errors = []
    seen = set()
    coordinates = set()
    for index, node in enumerate(report.get("grid_location_candidates", ())):
        if not isinstance(node, Mapping) or not node.get("column_context_candidate"):
            continue
        key = _position_key(node)
        if key is None or not _source_ok(node, docs):
            errors.append({"index": index, "status": "BLOCKED_INVALID_POSITION_PROVENANCE"})
            continue
        if kinds.get(key[:2]) != ("EXPLICIT_SHEET_TITLE", "column_type_plan"):
            # Other grid or table drawings must not be reclassified as columns.
            continue
        if key in seen:
            errors.append({"index": index, "status": "BLOCKED_DUPLICATE_GRID_IDENTITY"})
            continue
        seen.add(key)
        try:
            x, y = float(node["x_pt"]), float(node["y_pt"])
        except (KeyError, ValueError, TypeError, OverflowError):
            errors.append({"index": index, "status": "BLOCKED_INVALID_POSITION_COORDINATES"})
            continue
        if not isfinite(x) or not isfinite(y):
            errors.append({"index": index, "status": "BLOCKED_INVALID_POSITION_COORDINATES"})
            continue
        loc = (*key[:2], round(x, 2), round(y, 2))
        if loc in coordinates:
            errors.append({"index": index, "status": "BLOCKED_DUPLICATE_GEOMETRY"})
            continue
        coordinates.add(loc)
        expected_id = f"{key[0]}:p{key[1]}:r{key[2]}:c{key[3]}"
        if node.get("candidate_id") != expected_id:
            errors.append({"index": index, "status": "BLOCKED_MISMATCHED_POSITION_ID"})
            continue
        axis = None
        reg = registrations.get(key[:2])
        witness = node.get("independent_axis_grid_witness")
        if reg and isinstance(witness, Mapping) and witness.get("status") == _REGISTRATION:
            source = reg["axis_plan"]
            if (witness.get("axis_document_id") == source["document_id"] and
                    witness.get("axis_page") == source["page"] and
                    witness.get("axis_candidate_id") ==
                    f"{source['document_id']}:p{source['page']}:r{key[2]}:c{key[3]}"):
                axis = {"document_id": source["document_id"], "page": source["page"],
                        "axis_candidate_id": witness["axis_candidate_id"],
                        "status": "PROPOSED_INDEPENDENT_GRID_REGISTRATION"}
        tag = node.get("suggested_type")
        glyph = node.get("vector_type_label_evidence")
        type_ok = (node.get("status") == _TYPE and node.get("symbol_status") == _SYMBOL
                   and isinstance(glyph, Mapping) and glyph.get("tag") == tag
                   and isinstance(tag, str) and tag in {"C1", "C2", "C3"})
        detail = _valid_detail(node, source_docs=docs) if type_ok else None
        if not axis:
            status = "REVIEW_UNCORROBORATED_AXIS"
        elif not type_ok:
            status = "REVIEW_MISSING_OR_AMBIGUOUS_TYPE"
        elif not detail:
            status = "REVIEW_MISSING_OR_CONFLICTING_DETAIL"
        else:
            status = "FOUR_WAY_DRAWING_EVIDENCE_CANDIDATE"
        rows.append({"candidate_id": expected_id, "document_id": key[0],
                     "page": key[1], "grid_row": key[2], "grid_column": key[3],
                     "location_pt": [round(x, 3), round(y, 3)],
                     "proposed_type": tag if type_ok else None,
                     "type_evidence": dict(glyph) if type_ok else None,
                     "axis_evidence": axis,
                     "type_detail_evidence": detail,
                     "status": status,
                     "floor_scope_status": "BLOCKED_NO_INDEPENDENT_COLUMN_PLACEMENT_BY_LEVEL",
                     "floor_instances_verified": None,
                     "physical_member_verified": False,
                     "physical_member_quantity": None,
                     "approved": False, "financially_payable": False})
    rows.sort(key=lambda v: (v["document_id"], v["page"],v["grid_row"],v["grid_column"]))
    groups = {}
    for row in rows:
        k = (row["document_id"],row["page"])
        groups.setdefault(k, []).append(row)
    per_sheet=[]
    for (doc,page), values in sorted(groups.items()):
        typed=Counter(v["proposed_type"] for v in values if v["proposed_type"])
        per_sheet.append({"document_id":doc,"page":page,
                          "grid_position_candidates":len(values),
                          "type_label_position_candidates":dict(sorted(typed.items())),
                          "four_way_drawing_candidates":sum(v["status"] == "FOUR_WAY_DRAWING_EVIDENCE_CANDIDATE" for v in values),
                          "approved_physical_member_count":None,
                          "floor_multiplier":None,"financially_payable":False})
    floors = [dict(x) for x in report.get("architectural_floor_plan_candidates", ())
              if isinstance(x, Mapping) and x.get("document_id") in docs
              and _int(x.get("page")) and x["page"] <= docs[x["document_id"]]]
    return {"positions":rows,"per_sheet":per_sheet,"invalid":errors,
            "source_floor_plan_inventory":floors,
            "floor_repetition_evidence_status":"BLOCKED_NO_INDEPENDENT_COLUMN_PLACEMENT_BY_LEVEL",
            "floor_multiplier":None,"verified_total_physical_members":None,
            "quantity_approval_count":0,"financially_payable":False,"complete":False,
            "acceptance":"PARTIAL_NO_GO"}