"""Partition already-accounted PDF ink for read-only boundary review.

The connectivity and coarse bbox indexes keep their original identities.
Painted closed contours can survive contacts with unrelated strokes without
turning proximity, ink containment, or a printed scale into engineering proof.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from itertools import combinations, pairwise
import re

from core.drawings.pdf_detail_topology import _Stroke, _bounds, _non_endpoint_contact
from core.drawings.pdf_vector_type_labels import stroked_plate_annotations

_MAX_OUTLINE_EDGES = 48
_MAX_ENCLOSURE_CHECKS = 1_000_000


@dataclass(frozen=True)
class _Unit:
    refs: tuple[str, ...]
    role: str
    status: str
    reason: str
    outline: tuple = ()
    witness_id: str | None = None
    annotation_text: str | None = None


def _simple_outline(points):
    if not 3 <= len(points) <= _MAX_OUTLINE_EDGES or len(set(points)) != len(points):
        return False
    edges = [(a, b) for a, b in pairwise((*points, points[0]))]
    ox, oy = points[0]
    area_twice = sum((x - ox) * (v - oy) - (u - ox) * (y - oy) for (x, y), (u, v) in edges)
    if not area_twice:
        return False
    lines = [_Stroke(i, a, b, _bounds((a, b))) for i, (a, b) in enumerate(edges)]
    return not any(_non_endpoint_contact(a, b) for a, b in combinations(lines, 2))


def _source_path_outlines(records):
    """Use only primitive closed operators or an explicitly closed line run."""
    paths = defaultdict(list)
    for op in records:
        paths[op["path_index"]].append(op)
    for path in paths.values():
        points, refs = [], []
        last = 0
        for op in sorted(path, key=lambda row: row["operator_index"]):
            ordinal = op["operator_index"]
            vertices = tuple(map(tuple, op["points_pt"]))
            if op["paint"] != "s" or op["operator"] != "l":
                points, refs = [], []
                if op["paint"] == "s" and op["operator"] in {"re", "qu"} and _simple_outline(vertices):
                    yield _Unit((op["source_id"],), "CLOSED_OUTLINE", "CANDIDATE",
                                "EXPLICIT_PAINTED_POLYGON", vertices)
            else:
                a, b = vertices
                if not points or points[-1] != a or ordinal != last + 1:
                    points, refs = [a], []
                points.append(b)
                refs.append(op["source_id"])
                if b == points[0]:
                    if _simple_outline(points[:-1]):
                        yield _Unit(tuple(refs), "CLOSED_OUTLINE", "CANDIDATE",
                                    "CLOSED_LINE_RUN_IN_SAME_PAINT_PATH", tuple(points[:-1]))
                    points, refs = [], []
            last = ordinal


def _closed_component_lines(ops):
    """An exact cycle may have been painted as several separate line paths."""
    if not 3 <= len(ops) <= _MAX_OUTLINE_EDGES or any(
            op["operator"] != "l" or op["paint"] != "s" for op in ops):
        return ()
    neighbors = defaultdict(list)
    for op in ops:
        a, b = map(tuple, op["points_pt"])
        neighbors[a].append(b)
        neighbors[b].append(a)
    if any(len(adjacent) != 2 for adjacent in neighbors.values()):
        return ()
    start = min(neighbors)
    previous, current = start, min(neighbors[start])
    points = [start]
    while current != start and len(points) <= len(ops):
        points.append(current)
        following = [p for p in neighbors[current] if p != previous]
        if len(following) != 1:
            return ()
        previous, current = current, following[0]
    return tuple(points) if current == start and len(points) == len(ops) and _simple_outline(points) else ()


def _axis_ids(witness, prefix, digest, sheet_kind, operators):
    if witness is None:
        return ()
    if (sheet_kind != "axis_plan" or witness.get("source_sha256") != digest
            or f'{witness.get("document_id")}:p{witness.get("page")}' != prefix
            or witness.get("financially_payable") is not False):
        raise ValueError("Foreign or ineligible PDF axis witness")
    if witness.get("status") != "PROPOSED_UNLABELED_AXIS_GRID":
        return ()
    refs = []
    for ref in witness.get("source_operator_refs", ()):
        if not isinstance(ref, str) or not ref.startswith(prefix + ":"):
            raise ValueError("Foreign PDF grid operator")
        match = re.fullmatch(r"drawing(\d+):stroke(\d+)", ref[len(prefix) + 1:])
        if not match:
            raise ValueError("Malformed PDF grid operator")
        identity = f"{prefix}:d{int(match[1]) + 1}:s{int(match[2]) + 1}"
        if identity not in operators or operators[identity]["operator"] != "l":
            raise ValueError("Missing original PDF grid operator")
        refs.append(identity)
    if not refs or len(set(refs)) != len(refs):
        raise ValueError("Missing or repeated PDF grid operator")
    return tuple(refs)


def _same_outline_key(points):
    return frozenset(tuple(sorted((a, b))) for a, b in pairwise((*points, points[0])))


def _axis_aligned_rectangle(points, box):
    x0, y0, x1, y1 = box
    return len(points) == 4 and set(points) == {(x0, y0), (x0, y1), (x1, y0), (x1, y1)}


def _review_enclosures(outlines, page_box, max_checks):
    """Coincident outlines and nested rectangles need separate role review."""
    coincident = defaultdict(list)
    for outline in outlines:
        coincident[_same_outline_key(outline.outline)].append(outline)
    distinct = []
    for units in coincident.values():
        original = units[0]
        if len(units) > 1:
            original = replace(original, refs=tuple(ref for shape in units for ref in shape.refs),
                               status="AMBIGUOUS", reason="COINCIDENT_PAINT_OUTLINES")
        distinct.append(original)
    boxes = [_bounds(unit.outline) for unit in distinct]
    px0, py0, px1, py1 = page_box
    width, height = px1 - px0, py1 - py0
    wide = set()
    for i, (unit, box) in enumerate(zip(distinct, boxes, strict=True)):
        x0, y0, x1, y1 = box
        if (_axis_aligned_rectangle(unit.outline, box) and px0 <= x0 < x1 <= px1 and py0 <= y0 < y1 <= py1
                and x1 - x0 >= .8 * width and y1 - y0 >= .8 * height):
            wide.add(i)
    checked, out = 0, []
    for i, (unit, box) in enumerate(zip(distinct, boxes, strict=True)):
        if i in wide:
            selected = len(wide) == 1 and unit.status == "CANDIDATE"
            unit = replace(unit, role="PAGE_FRAME" if selected else "PAGE_FRAME_REVIEW",
                           status="NON_MEMBER" if selected else "AMBIGUOUS",
                           reason="EXPLICIT_SHEET_PERIMETER" if selected else "MULTIPLE_OR_REPEATED_PAGE_FRAMES")
        elif unit.status == "CANDIDATE" and _axis_aligned_rectangle(unit.outline, box):
            x0, y0, x1, y1 = box
            contained = 0
            for a, b, c, d in boxes:
                checked += 1
                if checked > max_checks:
                    return None
                if x0 < a < c < x1 and y0 < b < d < y1:
                    contained += 1
                    if contained == 2:
                        unit = replace(unit, role="ENCLOSING_OUTLINE_REVIEW", status="AMBIGUOUS",
                                       reason="OUTLINE_ENCLOSES_DISTINCT_CONTOURS")
                        break
        out.append(unit)
    return out


def _remaining_unit(parent, refs):
    role = parent["role"]
    if role == "TABLE_OR_PLAN_GRID":
        return _Unit(refs, "ORTHOGONAL_NETWORK_REVIEW", "AMBIGUOUS",
                     "GRID_TABLE_OR_DRAWN_MEMBER_ROLE_UNRESOLVED")
    if role in {"BRANCHED_STROKES", "ENCLOSING_CONTOUR_CANDIDATE", "DEGENERATE_QUAD_STROKE_REVIEW_ONLY"}:
        return _Unit(refs, "MIXED_STROKES", "AMBIGUOUS", "CONNECTED_INK_HAS_MULTIPLE_POSSIBLE_ROLES")
    if role.startswith("CURV"):
        return _Unit(refs, "CURVE_REVIEW", "UNCLASSIFIED", "CURVE_ROLE_AND_INTERSECTIONS_UNRESOLVED")
    return _Unit(refs, "UNCLASSIFIED_INK", "UNCLASSIFIED", "NO_EXPLICIT_BOUNDARY_OR_DRAWING_ROLE")


def build_pdf_component_boundary_page(topology, *, document_id, page, digest, sheet_kind,
                                      path_groups, paint_sequences=(), words=(), axis_witness=None,
                                      source_blocked=False, max_enclosure_checks=_MAX_ENCLOSURE_CHECKS):
    """Account for each readable origin once, including explicit rejected operators."""
    if type(max_enclosure_checks) is not int or max_enclosure_checks < 1:
        raise ValueError("Positive outline comparison budget required")
    prefix = f"{document_id}:p{page}"
    if (topology.get("document_id"), topology.get("page")) != (document_id, page):
        raise ValueError("Foreign PDF boundary page")
    parents = topology["groups"]
    operators, owner = {}, {}
    for parent, source in [
        *((group["candidate_id"], group["source_operators"]) for group in parents),
        (None, topology.get("unresolved_operators", ())),
    ]:
        for op in source:
            ref = op["source_id"]
            path, order = op["path_index"], op["operator_index"]
            if (type(path) is not int or type(order) is not int or path < 1 or order < 1
                    or ref != f"{prefix}:d{path}:s{order}" or ref in operators):
                raise ValueError("Invalid or duplicate boundary source operator")
            operators[ref], owner[ref] = op, parent
    count = topology["source_operator_count"]
    if count is not None and len(operators) > count:
        raise ValueError("PDF boundary manifest exceeds source operator count")
    missing = None if count is None else count - len(operators)
    reason = ("BLOCKED_PAGE_SOURCE_CONTEXT" if source_blocked or missing != 0 else None)
    if paint_sequences and len(paint_sequences) != topology["source_path_count"]:
        raise ValueError("PDF paint manifest differs from source paths")
    networks = [group["bbox_pt"] for group in parents if group["role"] == "TABLE_OR_PLAN_GRID"]

    def blocked_units(code):
        by_parent = defaultdict(list)
        for ref, parent in owner.items():
            by_parent[parent].append(ref)
        return [_Unit(tuple(refs), "BLOCKED_SOURCE_INK", "BLOCKED", code)
                for refs in by_parent.values()]

    if reason:
        units = blocked_units(reason)
    else:
        units, used = [], set()

        def add(unit):
            if used.intersection(unit.refs):
                raise ValueError("A PDF operator belongs to more than one boundary record")
            units.append(unit)
            used.update(unit.refs)

        for parent in parents:
            collapsed = tuple(op["source_id"] for op in parent["source_operators"]
                              if op.get("geometry_quality") == "DEGENERATE_QUAD_STROKE_REVIEW_ONLY")
            if collapsed:
                add(_Unit(collapsed, "COLLAPSED_QUAD_STROKE", "BLOCKED", "COLLAPSED_QUAD_REVIEW_ONLY"))
        grid = _axis_ids(axis_witness, prefix, digest, sheet_kind, operators)
        if grid:
            add(_Unit(grid, "AXIS_GRID", "NON_MEMBER", "SOURCE_GRID_ON_EXPLICIT_AXIS_SHEET"))
        glyphs = [word for word in words if word["method"] == "VECTOR_STROKE_LABEL"
                  and word["status"] == "ISOLATED_TYPE_WORD_POSITION_CANDIDATE"]
        claims = Counter(ref for word in glyphs for ref in word["source_operator_ids"])
        if claims.keys() - operators.keys():
            raise ValueError("Missing original PDF glyph operator")
        for word in glyphs:
            refs = tuple(word["source_operator_ids"])
            if refs and not used.intersection(refs) and all(claims[ref] == 1 for ref in refs):
                add(_Unit(refs, "CAD_TEXT", "NON_MEMBER", "SOURCE_OPERATORS_OF_RECOGNIZED_GLYPHS",
                          witness_id=word["source_id"]))

        captions = list(stroked_plate_annotations(operators.values()))
        caption_claims = Counter(ref for _, refs in captions for ref in refs)
        parent_refs = {parent["candidate_id"]: {op["source_id"] for op in parent["source_operators"]}
                       for parent in parents}
        for token, refs in captions:
            ref_set = set(refs)
            if (used.intersection(ref_set) or any(caption_claims[ref] != 1 for ref in refs)
                    or any(owner[ref] is None for ref in refs)
                    or any(parent_refs[parent] - ref_set for parent in {owner[ref] for ref in refs})):
                continue
            add(_Unit(refs, "CAD_TEXT", "NON_MEMBER", "SOURCE_STROKES_OF_PLATE_ANNOTATION",
                      witness_id=f"PLATE_TEXT:{refs[0]}", annotation_text=token))

        outlines = list(_source_path_outlines(op for ref, op in operators.items() if ref not in used))
        outline_refs = {ref for unit in outlines for ref in unit.refs}
        for parent in parents:
            ops = parent["source_operators"]
            refs = tuple(op["source_id"] for op in ops)
            if parent["role"] in {"CLOSED_CONTOUR", "FRAME_CANDIDATE", "ENCLOSING_CONTOUR_CANDIDATE"} and not (
                    used.intersection(refs) or outline_refs.intersection(refs)):
                points = _closed_component_lines(ops)
                if points:
                    outlines.append(_Unit(refs, "CLOSED_OUTLINE", "CANDIDATE", "EXACT_ENDPOINT_CYCLE", points))
        reviewed = None
        if len(outlines) * len(networks) <= max_enclosure_checks:
            reviewed = _review_enclosures(outlines, topology["page_bbox_pt"], max_enclosure_checks)
        if reviewed is None:
            reason = "BLOCKED_BOUNDARY_COMPARISON_BUDGET"
            units = blocked_units(reason)
        else:
            for unit in reviewed:
                add(unit)
            for parent in parents:
                refs = tuple(op["source_id"] for op in parent["source_operators"] if op["source_id"] not in used)
                if refs:
                    add(_remaining_unit(parent, refs))

    rows = []
    parent_uses, bbox_uses = Counter(), Counter()
    accounted = set()
    for unit in units:
        if accounted.intersection(unit.refs):
            raise ValueError("Duplicate operator in the PDF boundary partition")
        accounted.update(unit.refs)
        origins = sorted((operators[ref] for ref in unit.refs), key=lambda row: (row["path_index"], row["operator_index"]))
        first = origins[0]
        source_ids = [op["source_id"] for op in origins]
        source_paths = {}
        for op in origins:
            index = op["path_index"]
            source_paths[index] = {"path_index": index, "paint": op.get("paint"),
                                   "paint_sequence": paint_sequences[index - 1] if paint_sequences else None}
        bbox_ids = sorted({path_groups[p] for p in source_paths if p in path_groups})
        parent_ids = sorted({owner[ref] for ref in unit.refs if owner[ref] is not None})
        parent_uses.update(parent_ids)
        bbox_uses.update(bbox_ids)
        points = [point for op in origins for point in op.get("points_pt", ())]
        rows.append({
            "component_id": f'{prefix}:boundary{first["path_index"]}.{first["operator_index"]}',
            "document_id": document_id, "page": page, "source_pdf_sha256": digest, "sheet_kind": sheet_kind,
            "bbox_pt": list(_bounds(points)) if points else None,
            "outline_pt": [list(point) for point in unit.outline],
            "boundary_role": unit.role, "classification_status": unit.status, "reason_code": unit.reason,
            "source_operator_ids": source_ids, "source_paths": list(source_paths.values()),
            "parent_component_ids": parent_ids, "bbox_group_candidate_ids": bbox_ids,
            "role_witness_id": unit.witness_id, "detail_boundary_verified": False,
            "physical_member_verified": False, "physical_member_count": None,
            "quantity_approval_count": 0, "financially_payable": False,
        })
        if unit.annotation_text is not None:
            rows[-1]["role_witness"] = {
                "source_id": unit.witness_id, "document_id": document_id, "page": page,
                "source_sha256": digest, "bbox_pt": rows[-1]["bbox_pt"],
                "method": "ISOLATED_VECTOR_PLATE_ANNOTATION", "normalized_text": unit.annotation_text,
                "source_operator_ids": source_ids, "status": "TEXT_ONLY_UNCALIBRATED",
            }
    if accounted != operators.keys():
        raise ValueError("PDF boundary partition does not account for every retained source operator")
    for row in rows:
        flags = []
        if any(parent_uses[ref] > 1 for ref in row["parent_component_ids"]):
            flags.append("SHARED_TOPOLOGY_PARENT")
            if row["classification_status"] == "CANDIDATE":
                row.update(classification_status="AMBIGUOUS", reason_code="OUTLINE_TOUCHES_OTHER_SOURCE_INK")
        if row["classification_status"] == "CANDIDATE":
            x0, y0, x1, y1 = row["bbox_pt"]
            if any(a < x0 < x1 < c and b < y0 < y1 < d for a, b, c, d in networks):
                row.update(classification_status="AMBIGUOUS", reason_code="OUTLINE_WITHIN_ORTHOGONAL_NETWORK")
        if any(bbox_uses[ref] > 1 for ref in row["bbox_group_candidate_ids"]):
            flags.append("SHARED_ROUGH_BBOX_GROUP")
        row["relation_flags"] = flags
    return rows, {
        "document_id": document_id, "page": page, "source_pdf_sha256": digest,
        "status": "BLOCKED" if reason else "INDEXED_FOR_REVIEW",
        "reason_code": reason, "source_operator_count": count,
        "accounted_operator_count": len(accounted), "unaccounted_operator_count": missing,
        "components_by_status": dict(Counter(row["classification_status"] for row in rows)),
        "split_topology_parent_count": sum(uses > 1 for uses in parent_uses.values()),
        "detail_boundaries_verified": False, "financially_payable": False,
    }
