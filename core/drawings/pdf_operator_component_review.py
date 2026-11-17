"""Independent operator-component review and source-local, name-only plan/detail crosscheck.

The upstream bbox grouping and exact-stroke topology may disagree. Preserve
that disagreement explicitly instead of treating a connected ink component,
nearby title, or same type name as a verified detail or physical member.
This module has no DB, network, revision authority or payable output.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from math import isfinite
import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TAG = re.compile(r"(?:BR|BP|SC|SW|B|C|F|T|W|S|P)[1-9][0-9]{0,2}\Z", re.I)
_PLAN_KINDS = frozenset(("beam_layout_plan", "column_type_plan", "foundation_plan", "formwork_plan"))
_MAX_PAGES = 600
_MAX_COMPONENTS = 24000
_MAX_MEMBERS = 5000
_NEAR_TITLE_PT = 36.0


def _box(raw):
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise ValueError("Missing source-local operator component rectangle")
    try:
        value = tuple(float(x) for x in raw)
    except (ValueError, TypeError):
        raise ValueError("Invalid operator component coordinates") from None
    if not all(isfinite(x) for x in value) or value[0] >= value[2] or value[1] >= value[3]:
        raise ValueError("Invalid operator component rectangle")
    return value


def _distance(a, b):
    return max(0, a[0]-b[2], b[0]-a[2], a[1]-b[3], b[1]-a[3])


def build_pdf_operator_component_review(page_summaries, inventory, detail_index,
                                        member_type_candidates=()):
    """Compare *independent* stroke components to bbox groups on every PDF page.

    If topology was blocked by an extraction/complexity budget, report that
    complete page as blocked. Never reduce this to fewer apparent details.
    """
    if (not isinstance(inventory, dict) or inventory.get("all_input_pages_indexed") is not True
            or inventory.get("errors") or inventory.get("acceptance") != "PARTIAL_NO_GO"
            or not isinstance(detail_index, dict) or detail_index.get("acceptance") != "PARTIAL_NO_GO"
            or detail_index.get("complete") is not False
            or detail_index.get("quantity_approval_count") != 0):
        raise ValueError("Full unresolved PDF source inventory required")
    docs = inventory.get("documents", ())
    page_rows = inventory.get("sheet_inventory", ())
    title_rows = inventory.get("detail_title_anchors", ())
    bbox_pages = inventory.get("vector_geometry_groupings", ())
    if (not isinstance(docs, list) or not docs or
            not isinstance(page_rows, list) or not 1 <= len(page_rows) <= _MAX_PAGES
            or not isinstance(bbox_pages, list) or len(bbox_pages) != len(page_rows)
            or not isinstance(page_summaries, list) or len(page_summaries) != len(page_rows)
            or not isinstance(title_rows, list)):
        raise ValueError("Missing or unbounded page/component evidence")
    hashes = {}
    expected = set()
    for doc in docs:
        name, digest, pages = doc.get("document_id"), doc.get("sha256"), doc.get("page_count")
        if (not isinstance(name, str) or not name or name in hashes or
                not isinstance(digest, str) or not _SHA.fullmatch(digest) or
                type(pages) is not int or not 1 <= pages <= _MAX_PAGES):
            raise ValueError("Missing or duplicate source PDF document SHA")
        hashes[name] = digest
        expected.update((name, page) for page in range(1, pages+1))

    def keyed(rows, label):
        result = {}
        for item in rows:
            if not isinstance(item, dict):
                raise ValueError("Malformed " + label)
            key = item.get("document_id"), item.get("page")
            if key not in expected or key in result:
                raise ValueError("Foreign/duplicated " + label)
            result[key] = item
        if set(result) != expected:
            raise ValueError("Missing original PDF page in " + label)
        return result

    sheet_map = keyed(page_rows, "sheet inventory")
    summaries = keyed(page_summaries, "operator source")
    boxes = keyed(bbox_pages, "vector bbox group record")
    titles = defaultdict(list)
    title_ids = set()
    for item in title_rows:
        key = item.get("document_id"), item.get("page")
        aid = item.get("anchor_id")
        if (key not in expected or not isinstance(aid, str) or not aid
                or aid in title_ids or item.get("financially_payable") is not False):
            raise ValueError("Invalid or duplicated document title anchor")
        title_ids.add(aid)
        titles[key].append((aid, _box(item.get("bbox_pt"))))

    components = []
    page_checks = []
    seen_components = set()
    for key in sorted(expected):
        doc, page = key
        topology = summaries[key].get("detail_topology")
        grouping = boxes[key]
        if (not isinstance(topology, dict) or
                (topology.get("document_id"), topology.get("page")) != key or
                (grouping.get("document_id"), grouping.get("page")) != key):
            raise ValueError("Missing independent page-local operator topology")
        top_groups = topology.get("groups")
        bbox_groups = grouping.get("groups")
        if not isinstance(top_groups, list) or not isinstance(bbox_groups, list):
            raise ValueError("Malformed operator/bbox geometry groups")
        blocked = (topology.get("status") == "BLOCKED" or
                   topology.get("source_operators_accounted_for") is not True or
                   grouping.get("all_source_paths_grouped") is not True or
                   sheet_map[key].get("coverage_status") == "BLOCKED")
        if blocked:
            page_checks.append({
                "document_id": doc, "page": page, "source_pdf_sha256": hashes[doc],
                "status": "BLOCKED_TOPOLOGY_OR_SOURCE_INCOMPLETE",
                "operator_component_count": len(top_groups),
                "recorded_component_count": 0,
                "bbox_group_count": len(bbox_groups),
                "geometry_coverage_verified": False,
                "detail_boundaries_verified": False,
                "financially_payable": False,
            })
            continue
        operators_seen = set()
        path_to_bbox = {}
        bbox_to_components = defaultdict(set)
        for item in bbox_groups:
            gid = item.get("candidate_id")
            inds = item.get("source_path_indices")
            if (not isinstance(gid, str) or not gid.startswith(f"{doc}:p{page}:")
                    or not isinstance(inds, list)
                    or not inds or item.get("financially_payable") is not False
                    or item.get("detail_boundary_verified") is not False):
                raise ValueError("Invalid bbox group source identity")
            for path_index in inds:
                if type(path_index) is not int or path_index in path_to_bbox:
                    raise ValueError("Duplicate original PDF path across bbox groups")
                path_to_bbox[path_index] = gid
        npaths = grouping.get("source_path_count")
        if type(npaths) is not int or set(path_to_bbox) != set(range(1, npaths+1)):
            raise ValueError("Missing source paths in bbox grouping")
        if topology.get("source_path_count") != npaths:
            raise ValueError("Independent topology and bbox path budgets disagree")
        for comp in top_groups:
            cid = comp.get("candidate_id")
            if (not isinstance(cid, str) or not cid.startswith(f"{doc}:p{page}:topology")
                    or cid in seen_components or
                    (comp.get("document_id"), comp.get("page")) != key
                    or comp.get("detail_boundary_verified") is not False
                    or comp.get("physical_member_verified") is not False
                    or comp.get("financially_payable") is not False):
                raise ValueError("Foreign/duplicate or promoted operator component")
            seen_components.add(cid)
            witnesses = comp.get("source_operators")
            if not isinstance(witnesses, list) or not witnesses:
                raise ValueError("Component requires source operator witnesses")
            bbox_links = set()
            for op in witnesses:
                ident = (op.get("path_index"), op.get("operator_index"))
                if (type(ident[0]) is not int or type(ident[1]) is not int
                        or ident in operators_seen or ident[0] not in path_to_bbox
                        or not isinstance(op.get("source_id"), str)
                        or op["source_id"] != f"{doc}:p{page}:d{ident[0]}:s{ident[1]}"):
                    raise ValueError("Missing, repeated or foreign PDF vector operator")
                operators_seen.add(ident)
                bbox_links.add(path_to_bbox[ident[0]])
            for bbox_id in bbox_links:
                bbox_to_components[bbox_id].add(cid)
            near_titles = sorted(aid for aid, anchor_box in titles[key]
                                 if _distance(_box(comp["bbox_pt"]), anchor_box) <= _NEAR_TITLE_PT)
            components.append({
                "component_id": cid, "document_id": doc, "page": page,
                "source_pdf_sha256": hashes[doc], "bbox_pt": list(comp["bbox_pt"]),
                "stroke_topology_role": comp.get("role"),
                "source_operator_ids": sorted(op["source_id"] for op in witnesses),
                "bbox_group_candidate_ids": sorted(bbox_links),
                "nearby_title_anchor_ids": near_titles,
                "proposed_title_anchor_id": None,
                "status": "UNRESOLVED_OPERATOR_COMPONENT",
                "source_quality": "ORIGINAL_PDF_OPERATOR_TOPOLOGY_NOT_SEMANTIC_DETAIL",
                "detail_boundary_verified": False,
                "span_specific_detail_verified": False,
                "physical_member_verified": False, "physical_member_count": None,
                "quantity_approval_count": 0, "financially_payable": False,
            })
            if len(components) > _MAX_COMPONENTS:
                raise ValueError("Operator component review budget exhausted")
        if (len(operators_seen) != topology.get("source_operator_count") or
                len(top_groups) != topology.get("group_count")):
            raise ValueError("Independent PDF vector operators not fully accounted for")
        page_checks.append({
            "document_id": doc, "page": page, "source_pdf_sha256": hashes[doc],
            "status": "REVIEW_OPEN_OPERATOR_COMPONENTS_ACCOUNTED_FOR",
            "operator_component_count": len(top_groups),
            "recorded_component_count": len(top_groups),
            "bbox_group_count": len(bbox_groups),
            "geometry_coverage_verified": True,
            "detail_boundaries_verified": False, "financially_payable": False,
        })
        # Each title or bbox group can refer to multiple distinct operator
        # components. That is a VETO, not an opportunity to pick one arbitrarily.
        near_owner_count = Counter(tid for row in components
                                   if (row["document_id"], row["page"]) == key
                                   for tid in row["nearby_title_anchor_ids"])
        for row in components:
            if (row["document_id"], row["page"]) != key:
                continue
            gids, tids = row["bbox_group_candidate_ids"], row["nearby_title_anchor_ids"]
            unsafe_role = row["stroke_topology_role"] not in ("CLOSED_CONTOUR", "OPEN_CHAIN")
            if len(gids) != 1 or any(len(bbox_to_components[gid]) != 1 for gid in gids):
                status = "BLOCKED_BBOX_GROUP_AND_OPERATOR_COMPONENT_DISAGREE"
            elif unsafe_role:
                status = "UNRESOLVED_FRAME_GRID_OR_COMPLEX_OPERATOR_ROLE"
            elif not tids:
                status = "UNRESOLVED_COMPONENT_WITHOUT_EXPLICIT_TITLE"
            elif len(tids) != 1 or near_owner_count[tids[0]] != 1:
                status = "BLOCKED_AMBIGUOUS_TITLE_COMPONENT_CORRESPONDENCE"
            else:
                status = "PROPOSED_SINGLE_OPERATOR_COMPONENT_NEAR_UNIQUE_TITLE"
                row["proposed_title_anchor_id"] = tids[0]
            row["status"] = status

    detail_titles = {
        obj.get("title_anchor_id"): obj
        for obj in detail_index.get("detail_candidates", ())
        if obj.get("kind") == "EXPLICIT_DETAIL_TITLE"
    }
    for row in components:
        title_id = row["proposed_title_anchor_id"]
        row["proposed_title_candidate_id"] = (detail_titles[title_id]["candidate_id"]
                                              if title_id in detail_titles else None)
    # Cross-sheet type tags are only names, never installed spans. Even a
    # unique detail title/component is not an authorized plan-detail reference.
    details = [
        rec for rec in detail_index.get("detail_candidates", ())
        if rec.get("kind") == "EXPLICIT_TEXT_TYPE_MARK" and
        isinstance(rec.get("type_tag"), str) and
        rec.get("proposed_detail_title_id") is not None
    ]
    if not isinstance(member_type_candidates, (tuple, list)) or len(member_type_candidates) > _MAX_MEMBERS:
        raise ValueError("Unbounded plan type-mark witness count")
    plan_links = []
    by_title = defaultdict(list)
    for row in components:
        if row["proposed_title_candidate_id"] is not None:
            by_title[row["proposed_title_candidate_id"]].append(row["component_id"])
    for marker in member_type_candidates:
        key = (marker.get("document_id"), marker.get("page"))
        if key not in expected or marker.get("financially_payable") is not False:
            raise ValueError("Foreign or promoted plan type mark")
        if sheet_map[key].get("sheet_kind") not in _PLAN_KINDS:
            continue
        tag = marker.get("tag")
        if not isinstance(tag, str) or not _TAG.fullmatch(tag):
            continue
        candidates = [obj for obj in details
                      if obj.get("document_id") == key[0] and obj.get("page") != key[1]
                      and obj.get("type_tag") == tag]
        matches = sorted({x["candidate_id"] for x in candidates})
        components_near = sorted({cid for d in candidates
                                  for cid in by_title.get(d["proposed_detail_title_id"], ())})
        status = ("UNRESOLVED_NO_SAME_SOURCE_DETAIL_TYPE_REFERENCE" if not matches
                  else "BLOCKED_MULTIPLE_NAME_ONLY_DETAIL_REFERENCES" if len(matches) > 1
                  else "PROPOSED_TYPE_NAME_ONLY_NOT_SPAN_REFERENCE")
        plan_links.append({
            "plan_document_id": key[0], "plan_pdf_sha256": hashes[key[0]],
            "plan_page": key[1], "plan_sheet_kind": sheet_map[key].get("sheet_kind"),
            "printed_type_tag": tag, "plan_mark_bbox_pt": marker.get("mark_bbox_pt"),
            "candidate_detail_type_ids": matches,
            "nearby_operator_component_ids": components_near,
            "status": status, "governing_revision_verified": False,
            "plan_to_section_detail_verified": False,
            "span_specific_detail_verified": False,
            "physical_member_verified": False, "physical_member_count": None,
            "approved_length_m": None, "quantity_approval_count": 0,
            "financially_payable": False,
        })
    states = Counter(c["status"] for c in components)
    return {
        "status": "PARTIAL_OPERATOR_COMPONENT_AND_TYPE_ONLY_REVIEW",
        "page_count": len(expected), "page_reviews": page_checks,
        "operator_component_review_count": len(components),
        "operator_components": components,
        "operator_component_status_counts": dict(sorted(states.items())),
        "plan_detail_type_only_candidate_count": len(plan_links),
        "plan_detail_type_only_references": plan_links,
        "all_source_pages_accounted_for": len(page_checks) == len(expected),
        "detail_boundaries_verified": False, "plan_to_section_detail_verified": False,
        "physical_member_count": None, "quantity_approval_count": 0,
        "complete": False, "acceptance": "PARTIAL_NO_GO",
    }
