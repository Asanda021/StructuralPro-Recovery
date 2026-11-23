"""Read-only quantity evidence for explicit selections from the PDF intake ledger."""

from collections import Counter, defaultdict
from itertools import pairwise
from math import dist, fsum

from core.drawings.pdf_type_word_witness import _box


def _page_key(row):
    return row.get("document_id"), row.get("page")


def _within(points, bbox):
    return all(bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3] for x, y in points)


def _metric(kind, value, unit, formula, points, refs, component):
    return {
        "kind": kind, "value": value, "unit": unit, "formula": formula,
        "points_pt": points, "source_operator_ids": refs,
        "bbox_pt": [min(x for x, _ in points), min(y for _, y in points),
                    max(x for x, _ in points), max(y for _, y in points)],
        "component_id": component["component_id"], "parent_component_ids": component["parent_component_ids"],
        "boundary_role": component["boundary_role"], "boundary_status": component["classification_status"],
    }


def _raw_geometry(refs, bbox, operators, components):
    groups = {}
    contained = set()
    metrics = []
    for ref in refs:
        op = operators[ref]
        points = op.get("points_pt", ())
        if (not points or not _within(points, bbox)
                or op.get("geometry_quality") == "DEGENERATE_QUAD_STROKE_REVIEW_ONLY"):
            continue
        component = components[ref]
        contained.add(ref)
        groups[component["component_id"]] = component
        if op["operator"] == "l":
            metrics.append(_metric("STRAIGHT_SEGMENT_LENGTH", dist(*points), "pt",
                                   "sqrt((x2-x1)^2 + (y2-y1)^2)", points, [ref], component))
    for component in groups.values():
        points = component["outline_pt"]
        outline_refs = component["source_operator_ids"]
        if not points or not set(outline_refs) <= contained or not _within(points, bbox):
            continue
        x0, y0 = points[0]
        area = abs(fsum((ax-x0)*(by-y0) - (ay-y0)*(bx-x0)
                        for (ax, ay), (bx, by) in pairwise([*points, points[0]]))) / 2
        metrics.append(_metric("CLOSED_OUTLINE_AREA", area, "pt2", "abs(sum(x_i*y_(i+1)-y_i*x_(i+1)))/2",
                               points, outline_refs, component))
    measured = {ref for row in metrics for ref in row["source_operator_ids"]}
    return metrics, contained, [ref for ref in refs if ref not in measured]


def _quantity_candidate(occurrence):
    if (not occurrence or occurrence["status"] != "COMPLETE_NONFINANCIAL"
            or occurrence["quantity_status"] != "TEMPORARY_NONFINANCIAL"
            or occurrence["member_quantity"] is None):
        return None
    return {
        "value": occurrence["member_quantity"], "unit": occurrence["quantity_unit"],
        "formula": occurrence["quantity_formula"], "node_id": occurrence["node_id"],
        "governing_revision": occurrence["governing_revision"],
        "evidence": occurrence["anchors"], "dimension_observations": occurrence["observations"],
        "conversion_method": "OCCURRENCE_NATIVE_UNITS_AND_INDEPENDENT_LOCAL_PRINTED_SCALE_CHECK",
        "engineering_approved": False, "financially_payable": False,
    }


def _gates(page, occurrence, links, only_non_member, repeated, geometry_unresolved):
    missing = set(occurrence["missing_evidence"]) if occurrence else set()
    states = {row["verification_state"] for row in links}
    gates = []
    if repeated or "CONFLICTED" in states or (occurrence and occurrence["status"] == "BLOCKED"):
        gates.append("BLOCKED_CONFLICT")
    if (page["authority_status"] != "CURRENT" or len(page["printed_revisions"]) != 1
            or "BLOCKED_REVISION" in states or "GOVERNING_REVISION" in missing):
        gates.append("BLOCKED_REVISION")
    if not occurrence or geometry_unresolved or {"OCCURRENCE_IDENTITY", "OCCURRENCE_DETAIL"} & missing:
        gates.append("BLOCKED_TYPE")
    if not occurrence or {"MEASUREMENT_UNIT", "LOCAL_SCALE_CALIBRATION", "SECTION_DIMENSIONS"} & missing:
        gates.append("BLOCKED_UNIT")
    if only_non_member:
        gates.append("NON_MEMBER_OR_BLOCKED_GEOMETRY")
    if geometry_unresolved:
        gates.append("UNRESOLVED_GEOMETRY_ROLE")
    gates.extend(sorted(missing))
    candidate = _quantity_candidate(occurrence) if not gates else None
    if candidate:
        return "QUANTITY_CANDIDATE", ["ENGINEERING_APPROVAL_REQUIRED"], candidate
    if not gates:
        gates.append("ENGINEERING_APPROVAL_REQUIRED")
    return (gates[0] if gates[0].startswith("BLOCKED_") else "GEOMETRY_ONLY"), gates, None


def build_pdf_quantity_evidence_review(report, regions):
    """Bind each region to PDF custody. Reuse the occurrence engine for real units."""
    if not isinstance(regions, (list, tuple)) or not 1 <= len(regions) <= 1000:
        raise ValueError("PDF quantity review requires bounded, explicit source regions")
    if any(not isinstance(row, dict) or not isinstance(row.get("document_id"), str)
           or type(row.get("page")) is not int for row in regions):
        raise ValueError("Invalid PDF quantity region source identity")
    graph = report["detail_evidence_graph"]
    pages = {_page_key(page): page for page in graph["pages"]}
    documents = {row["document_id"]: row for row in report["documents"]}
    selected_pages = {_page_key(row) for row in regions}
    operators = {}
    for page in graph["topology_pages"]:
        if _page_key(page) in selected_pages:
            for source in [*(group["source_operators"] for group in page["groups"]),
                           page.get("unresolved_operators", ())]:
                for op in source:
                    ref = op["source_id"]
                    if ref in operators:
                        raise ValueError("Shared source operator in PDF topology")
                    operators[ref] = op
    components = {}
    for row in report["operator_component_review"]["boundary_components"]:
        if _page_key(row) in selected_pages:
            for ref in row["source_operator_ids"]:
                if ref in components:
                    raise ValueError("Shared source operator in PDF boundary partition")
                components[ref] = row
    occurrence_by_id = {row["node_id"]: row for row in graph["occurrence_reviews"]}
    geometries, refs_by_page, refs_by_edge = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in graph["edges"]:
        if edge["relationship"] == "INSTANCE_SHOWN_IN_VIEW" and edge["source_id"] in occurrence_by_id:
            for anchor in edge["anchors"]:
                key = _page_key(anchor)
                if (anchor["kind"] == "VECTOR_TOPOLOGY" and anchor.get("source_operator_ids")
                        and pages[key]["page_role"] == "PLAN"):
                    geometries[key].append((edge["source_id"], anchor))
    for link in graph["reference_links"]:
        refs_by_page[link["source_document_id"], link["source_sheet"]].append(link)
        refs_by_edge[link["graph_edge_id"]].append(link)

    selections = []
    ids = set()
    occurrence_uses = Counter()
    for region in regions:
        sample_id = region.get("sample_id")
        key = _page_key(region)
        bbox = _box(region.get("bbox_pt"))
        refs = region.get("source_operator_ids")
        document = documents.get(key[0])
        if (not isinstance(sample_id, str) or not sample_id or sample_id in ids
                or key not in pages or not bbox
                or not document or document["sha256"] != region.get("source_sha256")
                or not isinstance(refs, (tuple, list)) or not refs or not all(isinstance(ref, str) for ref in refs)
                or len(refs) != len(set(refs))
                or any(ref not in operators or ref not in components or _page_key(components[ref]) != key for ref in refs)):
            raise ValueError("Invalid, foreign or repeated PDF quantity source selection")
        ids.add(sample_id)
        raw, contained, omitted = _raw_geometry(refs, bbox, operators, components)
        matches = [(node_id, anchor) for node_id, anchor in geometries[key]
                   if set(anchor["source_operator_ids"]) <= contained]
        occurrence_uses.update({node_id for node_id, _ in matches})
        selections.append((region, key, bbox, refs, raw, contained, omitted, matches))

    rows = []
    for region, key, bbox, refs, raw, contained, omitted, matches in selections:
        page = pages[key]
        occurrence = occurrence_by_id[matches[0][0]] if len(matches) == 1 else None
        related_by_id = {link["link_id"]: link for link in refs_by_page[key]
                         if contained.intersection(link["source_operator_ids"])}
        if occurrence:
            related_by_id.update((link["link_id"], link) for edge in occurrence["edge_ids"] for link in refs_by_edge[edge])
        related = list(related_by_id.values())
        repeated = len(matches) > 1 or any(occurrence_uses[node] > 1 for node, _ in matches)
        only_non_member = all(components[ref]["classification_status"] in {"NON_MEMBER", "BLOCKED"} for ref in refs)
        geometry = matches[0][1] if occurrence else None
        geometry_unresolved = bool(geometry and any(
            components[ref]["classification_status"] != "CANDIDATE"
            or "SHARED_TOPOLOGY_PARENT" in components[ref]["relation_flags"]
            for ref in geometry["source_operator_ids"]
        ))
        status, gates, quantity = _gates(page, occurrence, related, only_non_member, repeated, geometry_unresolved)
        if quantity:
            quantity["plan_geometry_evidence"] = geometry
            quantity["source_operator_ids"] = geometry["source_operator_ids"]
        type_tags = {anchor["normalized_tag"] for link in related for anchor in link["evidence"]
                     if anchor["kind"] == "COLUMN_PLAN_GLYPH" and _page_key(anchor) == key
                     and anchor.get("normalized_tag") and contained.intersection(anchor["source_operator_ids"])}
        if occurrence and occurrence["type_tag"]:
            type_tags.add(occurrence["type_tag"])
        rows.append({
            "sample_id": region["sample_id"], "document_id": key[0], "page": key[1],
            "source_sha256": documents[key[0]]["sha256"], "source_name": documents[key[0]]["source_name"],
            "bbox_pt": list(bbox), "source_operator_ids": list(refs),
            "component_ids": sorted({components[ref]["component_id"] for ref in refs}),
            "parent_component_ids": sorted({p for ref in refs for p in components[ref]["parent_component_ids"]}),
            "boundary_roles": sorted({components[ref]["boundary_role"] for ref in refs}),
            "raw_measurements": raw, "omitted_operator_ids": omitted,
            "type_tags": sorted(type_tags),
            "scale_evidence": [a for a in occurrence["anchors"] if a["kind"] == "PRINTED_SCALE"] if occurrence else [],
            "reference_link_ids": [link["link_id"] for link in related],
            "revision_status": page["authority_status"], "status": status, "gate_reasons": gates,
            "unit_status": "VERIFIED_FOR_PREVIEW" if quantity else "UNIT_UNVERIFIED",
            "quantity_candidate": quantity, "engineering_approved": False,
            "physical_member_verified": False, "financially_payable": False,
        })
    return {"rows": rows, "aggregate_permitted": False, "quantity_approval_count": 0, "financially_payable": False}
