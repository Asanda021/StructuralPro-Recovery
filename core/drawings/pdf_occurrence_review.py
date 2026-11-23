"""Evaluate per-occurrence PDF evidence and a limited non-financial quantity."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from core.drawings.pdf_detail_object_index import _tag


_UNITS = {"M": Decimal(1), "CM": Decimal("0.01"), "MM": Decimal("0.001")}
_UNITS_TOLERANCE = Decimal("0.01")
_SCOPE_FIELDS = ("project_id", "issue_id")
_REQUIREMENTS = (
    "OCCURRENCE_IDENTITY", "INDEPENDENT_AXIS", "GOVERNING_REVISION", "OCCURRENCE_DETAIL",
    "INSTALLATION_LEVEL_RANGE", "SECTION_DIMENSIONS", "MEASUREMENT_UNIT", "MATERIAL",
    "CONNECTION_SCOPE", "EXECUTED_LENGTH", "DEDUCTIONS", "LOCAL_SCALE_CALIBRATION",
    "FLOOR_AND_OVERLAP_SCOPE",
)
_AXIS_LINKS = {"AT_AXIS", "COLUMN_AXIS_CORROBORATION"}
_DETAIL_LINKS = {"DETAIL_CALLOUT", "COLUMN_DETAIL_TYPE_REFERENCE", "PLAN_DETAIL_PRINTED_MEMBER_ID", "PRINTED_SCHEDULE_CONFLICT"}


def _page_of(pages, anchor):
    return pages.get((anchor["document_id"], anchor["page"]))


def _registered(page):
    authority = page.get("authority") or {}
    return (page["linkable"] and not page["authority_block"] and page["sheet_id"]
            and authority.get("status") == "CURRENT" and page["printed_revisions"] == [authority["revision"]])


def _issue_scope(page):
    authority = page.get("authority") or {}
    return tuple(authority[k] for k in _SCOPE_FIELDS) if authority else (page["sha256"],)


def _dimension(record, value, unit):
    if not record or record.get(unit) not in _UNITS:
        return None
    return Decimal(record[value]) * _UNITS[record[unit]]


def _unique(records, predicate):
    matches = [item for item in records if predicate(item)]
    return matches[0] if len(matches) == 1 else None


def _disjoint(a, b):
    return a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def _rectangular_section(page, node):
    if not node or node.get("topology_role") != "CLOSED_CONTOUR":
        return False
    geometry = next((g for g in page["raw"]["detail_topology"]["groups"]
                     if g["candidate_id"] == node.get("geometry_candidate_id")), None)
    # Only an explicitly rectangular vector operator is supported for the
    # provisional concrete volume. A generic outline's bounding box is not a section.
    operators = geometry["source_operators"] if geometry else ()
    return len(operators) == 1 and operators[0].get("operator") == "re"


def _calibrated(page, detail, width, depth, dimensional_anchors):
    if (not page or not _rectangular_section(page, detail) or not width or not depth
            or not all(dimensional_anchors) or not detail.get("printed_scale")):
        return False
    a, b = dimensional_anchors
    if a["source_line"] == b["source_line"] or not _disjoint(a["bbox_pt"], b["bbox_pt"]):
        return False
    scale = Decimal(detail["printed_scale"].split(":")[1])
    x0, y0, x1, y1 = map(lambda n: Decimal(str(n)), detail["bbox_pt"])
    per_point = Decimal("0.0254") * scale / 72
    plotted = ((x1 - x0) * per_point, (y1 - y0) * per_point)
    return all(abs(value - expected) <= expected * _UNITS_TOLERANCE
               for value, expected in zip(plotted, (width, depth), strict=True))


def _decimal_text(value):
    return format(value.normalize(), "f")


def _plan_anchors(pages, node):
    return [a for a in node["anchors"] if a.get("kind") in {"INSTANCE", "GRID_LOCATION_CANDIDATE"}
            and _page_of(pages, a)["page_role"] == "PLAN"]


def _review_one(pages, nodes, seen_ranges, node, links):
    plans = _plan_anchors(pages, node)
    plan = _page_of(pages, plans[0]) if plans else None
    scope = _issue_scope(plan) if plan else None
    axis_links = [e for e in links if e["relationship"] in _AXIS_LINKS and e["target_id"]]
    details = [e for e in links if e["relationship"] in _DETAIL_LINKS and e["target_id"]]
    direct = [e for e in details if e["relationship"] == "DETAIL_CALLOUT" and e["status"] == "VALIDATED_REFERENCE"]
    explicit_detail = nodes[direct[0]["target_id"]] if len(direct) == 1 else None
    display_detail = explicit_detail or (nodes[details[0]["target_id"]] if details else None)
    detail_page = _page_of(pages, explicit_detail["anchors"][0]) if explicit_detail else None
    native_plan = len(plans) == 1 and plans[0]["kind"] == "INSTANCE" and node.get("plan_geometry_present")
    named_axis = _unique(axis_links, lambda e: e["relationship"] == "AT_AXIS" and e["status"] == "VALIDATED_REFERENCE")
    level_links = [e for e in links if e["relationship"] == "AT_LEVEL" and e["status"] == "VALIDATED_REFERENCE"]
    member = plans[0].get("member") if plans else None
    tag = node.get("type_tag")
    detail_fields = detail_page["anchors_by_kind"] if detail_page else {}
    def for_occurrence(anchor):
        canonical = _tag(anchor.get("tag")) or (None, None)
        return anchor["member"] == member and canonical[0] == tag

    dimensions = [a for a in detail_fields.get("COLUMN_DIMENSION", ()) if for_occurrence(a)]
    width_ref = _unique(dimensions, lambda a: a["dimension"] == "WIDTH")
    depth_ref = _unique(dimensions, lambda a: a["dimension"] == "DEPTH")
    specs = [a for a in detail_fields.get("COLUMN_SPEC", ()) if for_occurrence(a)]
    spec = specs[0] if len(specs) == 1 else None
    width, depth = (_dimension(ref, "value", "unit") for ref in (width_ref, depth_ref))
    ranges = [a for a in seen_ranges.get((scope, member), ()) if a["level"] == node.get("level")]
    level_rect = ranges[0] if len(ranges) == 1 else None
    if level_rect and level_rect["axis"].replace(" ", "") != node.get("axis"):
        level_rect = None
    level_page = _page_of(pages, level_rect) if level_rect else None
    level_reference = bool(level_page and any(
        nodes[e["target_id"]]["anchors"][0]["anchor_id"] in
        {a["anchor_id"] for a in level_page["anchors_by_kind"]["LEVEL"]}
        for e in level_links
    ))
    bottom, top, length = (
        _dimension(level_rect, value, unit) for value, unit in (
            ("bottom", "bottom_unit"), ("top", "top_unit"), ("length", "length_unit"),
        )
    )
    valid_range = bottom is not None and top is not None and top > bottom and length == top - bottom
    gross = width * depth * length if width and depth and length and valid_range else None
    cuts = Decimal(spec["deductions"]) if spec else None
    valid_cuts = cuts is not None and gross is not None and 0 <= cuts < gross
    source_documents = [plan, detail_page, level_page]
    if len(direct) == 1:
        source_documents.extend(_page_of(pages, anchor) for anchor in direct[0]["anchors"]
                                if anchor["kind"] == "CALLOUT")
    if named_axis:
        source_documents.append(_page_of(pages, nodes[named_axis["target_id"]]["anchors"][0]))
    official = bool(native_plan and named_axis and all(
        page and _registered(page) and _issue_scope(page) == scope for page in source_documents
    ))
    section_area = bool(width and depth and min(width, depth) > 0)
    geometry = bool(detail_page and _rectangular_section(detail_page, explicit_detail))
    conflicts = node.get("printed_schedule_conflicts", ())
    fits = {
        "OCCURRENCE_IDENTITY": native_plan or node.get("printed_id_review_status") == "CORROBORATED_DRAWN_IDS",
        "INDEPENDENT_AXIS": named_axis is not None or node.get("independent_axis_reference_found"),
        "GOVERNING_REVISION": official,
        "OCCURRENCE_DETAIL": bool(explicit_detail and explicit_detail["family"] == "column" and explicit_detail.get("type_tag") == tag),
        "INSTALLATION_LEVEL_RANGE": valid_range and level_reference,
        "SECTION_DIMENSIONS": section_area and geometry,
        "MEASUREMENT_UNIT": section_area and length is not None,
        "MATERIAL": spec is not None,
        "CONNECTION_SCOPE": spec is not None,
        "EXECUTED_LENGTH": valid_range,
        "DEDUCTIONS": valid_cuts,
        "LOCAL_SCALE_CALIBRATION": _calibrated(detail_page, explicit_detail, width, depth, (width_ref, depth_ref)),
        "FLOOR_AND_OVERLAP_SCOPE": native_plan and valid_range and level_rect["occurrence_count"] == "1",
    }
    missing = [field for field in _REQUIREMENTS if not fits[field]]
    if conflicts:
        missing.append("DESIGN_AUTHORITY_DECISION")
    refs = {a["anchor_id"]: a for a in (
        *node["anchors"], *(a for e in [*axis_links, *details, *level_links] for a in e["anchors"]),
        *dimensions, *specs, *ranges,
    )}
    opposing = {a["anchor_id"]: a for event in conflicts for a in event["anchors"]}
    contradictory = bool(len(ranges) > 1 or (ranges and not valid_range) or len(specs) > 1 or len(dimensions) > 2)
    blocked = bool(conflicts or node["status"] == "BLOCKED" or contradictory or len(plans) > 1)
    record = {
        "node_id": node["node_id"], "source_id": node["node_id"],
        "target_id": display_detail["node_id"] if display_detail else None,
        "axis_node_ids": list(dict.fromkeys(e["target_id"] for e in axis_links)),
        "edge_ids": [e["edge_id"] for e in [*axis_links, *details, *level_links]],
        "printed_member_id": node.get("printed_member_id") or member, "type_tag": tag, "family": node["family"],
        "axis": node.get("axis"), "grid_row": node.get("grid_row"), "grid_column": node.get("grid_column"),
        "level": node.get("level"), "governing_revision": plan["authority"]["revision"] if official else None,
        "status": "BLOCKED" if blocked else "INCOMPLETE",
        "decision_code": "DESIGN_AUTHORITY_REQUIRED" if conflicts else "EVIDENCE_REQUIRED",
        "reason_code": conflicts[0]["reason_code"] if conflicts else (
            "OCCURRENCE_EVIDENCE_CONFLICT" if blocked else "MISSING_OCCURRENCE_EVIDENCE"),
        "missing_evidence": missing, "anchors": list(refs.values()), "conflicting_anchors": list(opposing.values()),
        "quantity_status": "NO_QUANTITY", "member_quantity": None, "quantity_unit": None,
        "quantity_formula": None, "quantity_approval_count": 0, "financially_payable": False,
        "observations": {
            "detail_id_kind": node.get("printed_id_review_status"),
            "section_width_m": _decimal_text(width) if width else None,
            "section_depth_m": _decimal_text(depth) if depth else None,
            "length_m": _decimal_text(length) if valid_range and length is not None else None,
            "installation_from_m": _decimal_text(bottom) if bottom is not None else None,
            "installation_to_m": _decimal_text(top) if top is not None else None,
            "deductions_m3": _decimal_text(cuts) if cuts is not None else None,
            "material": "CONCRETE" if spec else None,
            "printed_scale": explicit_detail.get("printed_scale") if explicit_detail else None,
        },
    }
    position = (scope, node["axis"]) if scope and node.get("axis") and plans else None
    interval = (bottom, top) if valid_range else None
    return record, position, interval, gross - cuts if valid_cuts else None


def _block_overlapping(entries):
    def block(row):
        row["status"] = "BLOCKED"
        if row["decision_code"] != "DESIGN_AUTHORITY_REQUIRED":
            row["reason_code"] = "OCCURRENCE_OVERLAP_UNRESOLVED"
        if "FLOOR_AND_OVERLAP_SCOPE" not in row["missing_evidence"]:
            row["missing_evidence"].append("FLOOR_AND_OVERLAP_SCOPE")

    if len(entries) <= 1:
        return
    if any(interval is None for _, interval in entries):
        for row, _ in entries:
            block(row)
        return
    ordered = sorted(entries, key=lambda item: item[1])
    upper = ordered[0]
    for item in ordered[1:]:
        if item[1][0] < upper[1][1]:
            block(upper[0])
            block(item[0])
        if item[1][1] > upper[1][1]:
            upper = item


def build_pdf_occurrence_reviews(pages, nodes, edges):
    """Attach review decisions to existing graph candidates without BOQ side effects."""
    ranges, links, footprint = defaultdict(list), defaultdict(list), defaultdict(list)
    for page in pages.values():
        if page["page_role"] in {"SECTION", "ELEVATION", "SCHEDULE"} and _registered(page):
            for record in page["anchors_by_kind"]["COLUMN_RANGE"]:
                ranges[(_issue_scope(page), record["member"])].append(record)
    for edge in edges:
        links[edge["source_id"]].append(edge)
    review = []
    for node in nodes.values():
        if node["kind"] == "INSTANCE_CANDIDATE":
            row, position, interval, net = _review_one(pages, nodes, ranges, node, links[node["node_id"]])
            review.append((row, net))
            if position:
                footprint[position].append((row, interval))
    for entries in footprint.values():
        _block_overlapping(entries)
    for row, net in review:
        if not row["missing_evidence"] and row["status"] != "BLOCKED" and net is not None:
            row.update(status="COMPLETE_NONFINANCIAL", decision_code="COMPLETE_DRAWING_EVIDENCE", reason_code=None,
                       quantity_status="TEMPORARY_NONFINANCIAL", member_quantity=_decimal_text(net),
                       quantity_unit="m3", quantity_formula="section width × section depth × executed length − deductions")
        row["physical_member_verified"] = row["status"] == "COMPLETE_NONFINANCIAL"
        nodes[row["node_id"]].update(occurrence_review_status=row["status"], missing_evidence=row["missing_evidence"],
                                    quantity_status=row["quantity_status"], member_quantity=row["member_quantity"],
                                    quantity_reason=row["reason_code"], quantity_unit=row["quantity_unit"],
                                    quantity_formula=row["quantity_formula"],
                                    physical_member_verified=row["physical_member_verified"])
    return [row for row, _ in review]
