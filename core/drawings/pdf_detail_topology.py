"""Index stroke topology on one PDF page using exact extracted coordinates.

Path/operator ordinals refer to get_drawings() on the exact source snapshot.
The ledger supports review of drawn shapes, with semantic boundary, scale and
physical ownership left to independent witnesses.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import pairwise
from math import isclose, isfinite


_SPACE = "unrotated_pdf_points"
_REASONS = {
    "CLOSED_CONTOUR": "Straight segments form a single endpoint cycle without another detected contact.",
    "CURVED_ENDPOINT_CYCLE": "Curve endpoints form a cycle. Control hull and curve intersections require review.",
    "CURVE_CONTROL_HULL": "Exact source controls are retained. Interior curve intersections require review.",
    "FRAME_CANDIDATE": "An enclosing axis-aligned rectangle spans most of this page.",
    "ENCLOSING_CONTOUR_CANDIDATE": "A rectangle encloses multiple disconnected contours. The drawing scope requires review.",
    "FILL_BOUNDARY_UNRESOLVED": "The fill path has an open extracted chain. The painted boundary requires review.",
    "TABLE_OR_PLAN_GRID": "Several orthogonal lines intersect within a common stroke component.",
    "PARALLEL_STROKES": "Three or more equally spaced parallel segments share one source path.",
    "BRANCHED_STROKES": "Branches, overlapping segments or non-endpoint contacts need manual separation.",
    "OPEN_CHAIN": "Stroke endpoints form an open chain. Its drawing role needs independent evidence.",
    "DEGENERATE_QUAD_STROKE_REVIEW_ONLY": (
        "Source Quad contains only two unique endpoints. Original four vertices "
        "are preserved; topology uses a single segment, never a certified area or member."
    ),
}


def _coordinates(value, length):
    raw = tuple(value)
    if len(raw) != length or any(isinstance(n, bool) for n in raw):
        raise ValueError("Invalid PDF geometry coordinates")
    out = tuple(float(n) for n in raw)
    if not all(isfinite(n) and abs(n) <= 10_000_000 for n in out):
        raise ValueError("PDF geometry coordinates out of range")
    return out


def _bounds(points):
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _operator_points(item):
    op = item[0]
    if op == "l":
        points = tuple(_coordinates(p, 2) for p in item[1:])
        if len(points) == 2 and points[0] != points[1]:
            return points
    elif op == "c":
        points = tuple(_coordinates(p, 2) for p in item[1:])
        if len(points) == 4 and len(set(points)) > 1:
            return points
    elif op == "re":
        x0, y0, x1, y1 = _coordinates(item[1], 4)
        if x0 < x1 and y0 < y1:
            return (x0, y0), (x1, y0), (x1, y1), (x0, y1)
    elif op == "qu":
        ul, ur, ll, lr = (_coordinates(p, 2) for p in item[1])
        unique = {ul, ur, ll, lr}
        if len(unique) == 4:
            return ul, ur, lr, ll
        # PyMuPDF can return a zero-area Quad for CAD strokes: four
        # source corners collapse onto the two ends of ONE line. Retain the
        # operator and its four original vertices (below), but normalize
        # topology to one explicit straight segment. No fake quad area.
        if len(unique) == 2 and all(
            (ul, ur, ll, lr).count(point) == 2 for point in unique
        ):
            return tuple(sorted(unique))
    raise ValueError("Invalid or degenerate PDF vector operator")


@dataclass(frozen=True, slots=True)
class _Stroke:
    owner: int
    start: tuple[float, float]
    end: tuple[float, float]
    box: tuple[float, float, float, float]
    curved: bool = False

    @property
    def axis(self):
        if self.start[1] == self.end[1]:
            return "h"
        if self.start[0] == self.end[0]:
            return "v"
        return None


def _stroke_parts(operator, points, owner):
    if operator == "c":
        return [_Stroke(owner, points[0], points[-1], _bounds(points), curved=True)]
    if operator == "re" or (operator == "qu" and len(points) == 4):
        points = (*points, points[0])
    return [_Stroke(owner, a, b, _bounds((a, b))) for a, b in pairwise(points)]


def _cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _inside_bounds(box, p):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def _non_endpoint_contact(a, b):
    """The caller checks boxes first. Common endpoints already join components."""
    u, v = _cross(a.start, a.end, b.start), _cross(a.start, a.end, b.end)
    s, t = _cross(b.start, b.end, a.start), _cross(b.start, b.end, a.end)
    if u == v == s == t == 0:
        k = 0 if a.start[0] != a.end[0] else 1
        return min(a.box[k+2], b.box[k+2]) > max(a.box[k], b.box[k])
    if {a.start, a.end} & {b.start, b.end}:
        return False
    return ((u * v < 0 and s * t < 0) or
            any(value == 0 and _inside_bounds(box, point) for value, box, point in (
                (u, a.box, b.start), (v, a.box, b.end),
                (s, b.box, a.start), (t, b.box, a.end))))


def _exact_parallel_runs(operators):
    """Locate explicit repeated ink in a single path without joining its strokes."""
    by_path = defaultdict(list)
    for i, record in enumerate(operators):
        by_path[record["path_index"]].append((i, record))
    out = set()
    for items in by_path.values():
        if len(items) < 3 or any(record["operator"] != "l" for _, record in items):
            continue
        position = []
        vectors = set()
        for _, record in items:
            (x0, y0), (x1, y1) = sorted(record["points_pt"])
            dx, dy = x1 - x0, y1 - y0
            vectors.add((dx, dy))
            position.append(dx * y0 - dy * x0)
        gaps = [b - a for a, b in pairwise(sorted(position))]
        if len(vectors) == 1 and gaps[0] > 0 and all(
                isclose(gap, gaps[0], rel_tol=1e-9, abs_tol=1e-10) for gap in gaps):
            out.update(i for i, _ in items)
    return out


def _disposition(strokes, degree, page_bounds, box, *, crossing, parallel):
    curved = any(stroke.curved for stroke in strokes)
    cycle = all(n == 2 for n in degree.values())
    horizontal = {s.start[1] for s in strokes if not s.curved and s.axis == "h"}
    vertical = {s.start[0] for s in strokes if not s.curved and s.axis == "v"}
    branch = crossing or any(n > 2 for n in degree.values())
    if branch and min(len(horizontal), len(vertical)) >= 2 and max(len(horizontal), len(vertical)) >= 3:
        return "TABLE_OR_PLAN_GRID"
    if branch:
        return "BRANCHED_STROKES"
    if curved:
        return "CURVED_ENDPOINT_CYCLE" if cycle else "CURVE_CONTROL_HULL"
    if cycle:
        w, h = page_bounds[2]-page_bounds[0], page_bounds[3]-page_bounds[1]
        if (len(strokes) == 4 and len(horizontal) == len(vertical) == 2
                and box[2]-box[0] >= 0.8*w and box[3]-box[1] >= 0.8*h):
            return "FRAME_CANDIDATE"
        return "CLOSED_CONTOUR"
    return "PARALLEL_STROKES" if parallel else "OPEN_CHAIN"


def _connected_strokes(operators, parsed, max_pair_checks):
    parent = list(range(len(operators)))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a, b):
        x, y = sorted((root(a), root(b)))
        parent[y] = x

    endpoints = {}
    for stroke in parsed:
        for coord in (stroke.start, stroke.end):
            union(stroke.owner, endpoints.setdefault(coord, stroke.owner))
    # Compare only actual lines whose envelopes can intersect. Curves retain
    # their exact endpoints and controls, without chord-derived intersections.
    comparisons = 0
    extra = set()
    active = []
    straight = (s for s in parsed if not s.curved)
    for s in sorted(straight, key=lambda s: (s.box, s.owner)):
        active = [t for t in active if t.box[2] >= s.box[0]]
        for t in active:
            comparisons += 1
            if comparisons > max_pair_checks:
                return None, None
            if t.box[3] < s.box[1] or s.box[3] < t.box[1]:
                continue
            if _non_endpoint_contact(s, t):
                union(s.owner, t.owner)
                extra.add(s.owner)
        active.append(s)
    members = defaultdict(list)
    for s in parsed:
        members[root(s.owner)].append(s)
    return members, {root(i) for i in extra}


def _mark_enclosing_contours(groups, possible_frames, max_pair_checks):
    """Keep internal drawing frames and disconnected contours independently indexed."""
    active = []
    enclosed = defaultdict(list)
    checks = 0
    ordered = sorted(groups, key=lambda g: (g["bbox_pt"][0], g["candidate_id"]))
    for inner in ordered:
        if inner["role"] not in {"CLOSED_CONTOUR", "CURVED_ENDPOINT_CYCLE"}:
            continue
        x0, y0, x1, y1 = inner["bbox_pt"]
        active = [g for g in active if g["bbox_pt"][2] > x0]
        for outer in active:
            checks += 1
            if checks > max_pair_checks:
                return False
            a0, b0, a1, b1 = outer["bbox_pt"]
            if a0 < x0 < x1 < a1 and b0 < y0 < y1 < b1:
                enclosed[outer["candidate_id"]].append(inner["candidate_id"])
        if inner["candidate_id"] in possible_frames:
            active.append(inner)
    for group in groups:
        contained = enclosed[group["candidate_id"]]
        if len(contained) >= 2:
            role = "ENCLOSING_CONTOUR_CANDIDATE"
            group.update(role=role, enclosed_contour_candidate_ids=sorted(contained))
            if group["status"] != "BLOCKED":
                group["reason"] = _REASONS[role]
    return True


def scan_detail_topology(page, *, document_id: str, page_number: int, paths=None,
                         source_blocked: bool = False, max_paths: int = 12000,
                         max_operators: int = 24000, max_pair_checks: int = 3_000_000) -> dict:
    """Inspect every available drawing operator and account for blocked work.

    The caller may supply its cached PyMuPDF paths from the same immutable
    page, preserving the input order and avoiding repeated extraction.
    """
    if (not isinstance(document_id, str) or not document_id.strip()
            or type(page_number) is not int or page_number < 1 or page.number != page_number-1):
        raise ValueError("A matching PDF document and page identity are required")
    if any(type(n) is not int or n < 1 for n in (max_paths, max_operators, max_pair_checks)):
        raise ValueError("Positive PDF topology budgets required")
    bounds = _coordinates(page.rect * page.derotation_matrix, 4)
    if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        raise ValueError("Invalid PDF page bounds")
    prefix = f"{document_id}:p{page_number}"
    out = {
        "document_id": document_id, "page": page_number, "page_bbox_pt": list(bounds),
        "rotation": page.rotation, "coordinate_space": _SPACE, "source_path_count": None,
        "source_operator_count": None, "source_operators_accounted_for": False,
        "group_count": 0, "groups": [], "unresolved_operators": [], "unresolved_paths": [],
        "source_degenerate_operator_count": 0,
        "source_degenerate_operator_ids": [],
        "source_degenerate_quads_review_required": False,
        "detail_boundary_verified": False, "physical_member_count": None,
        "quantity_approval_count": 0, "financially_payable": False,
    }

    def finish(status, code, reason):
        return {**out, "status": status, "reason_code": code, "reason": reason}

    try:
        source_paths = page.get_drawings() if paths is None else paths
        out["source_path_count"] = len(source_paths)
        if out["source_path_count"] > max_paths:
            return finish("BLOCKED", "BLOCKED_VECTOR_TOPOLOGY_PATH_BUDGET",
                          "Path budget exceeded. Inspect this page with corroborating source detail.")
        items = [p.get("items") if isinstance(p, dict) else None for p in source_paths]
        out["source_operator_count"] = sum(len(p) for p in items if isinstance(p, (tuple, list)))
    except (RuntimeError, ValueError, TypeError, MemoryError):
        return finish("BLOCKED", "BLOCKED_VECTOR_TOPOLOGY_EXTRACTION",
                      "The reader could not extract a complete page vector snapshot.")
    if source_blocked:
        return finish("BLOCKED", "BLOCKED_SOURCE_EVIDENCE_INCOMPLETE",
                      "The source page intake is incomplete. No provisional topology is promoted.")
    if out["source_operator_count"] > max_operators:
        return finish("BLOCKED", "BLOCKED_VECTOR_TOPOLOGY_OPERATOR_BUDGET",
                      "Operator budget exceeded. The source page remains unresolved.")
    operators, strokes = [], []
    for path_index, path_items in enumerate(items, 1):
        if not isinstance(path_items, (tuple, list)) or not path_items:
            out["unresolved_paths"].append({
                "path_index": path_index, "source_id": f"{prefix}:d{path_index}",
                "status": "BLOCKED", "reason": "Source path has no readable operator list.",
            })
            continue
        for op_index, item in enumerate(path_items, 1):
            op = item[0] if isinstance(item, (list, tuple)) and item else None
            record = {"path_index": path_index, "operator_index": op_index,
                      "source_id": f"{prefix}:d{path_index}:s{op_index}",
                      "operator": op if isinstance(op, str) else None}
            try:
                if not isinstance(op, str) or op not in {"l", "re", "qu", "c"}:
                    raise ValueError
                points = _operator_points(item)
            except (IndexError, TypeError, ValueError, OverflowError):
                out["unresolved_operators"].append({
                    **record, "status": "BLOCKED", "reason": "Unsupported or invalid vector operator.",
                })
                continue
            geometry_quality = "EXACT_OPERATOR_GEOMETRY"
            original_quad = None
            if op == "qu" and len(points) == 2:
                # Never discard the source four-corner record, even though
                # it collapses into a 2-point zero-area stroke.
                original_quad = [list(_coordinates(p, 2)) for p in item[1]]
                geometry_quality = "DEGENERATE_QUAD_STROKE_REVIEW_ONLY"
                out["source_degenerate_operator_ids"].append(record["source_id"])
            strokes.extend(_stroke_parts(op, points, len(operators)))
            paint = source_paths[path_index-1].get("type")
            operators.append({**record, "points_pt": [list(p) for p in points],
                              "source_quad_corners_pt": original_quad,
                              "geometry_quality": geometry_quality,
                              "paint": paint if paint in ("s", "f", "fs", "sf") else None})
    out["source_degenerate_operator_count"] = len(out["source_degenerate_operator_ids"])
    out["source_degenerate_quads_review_required"] = bool(out["source_degenerate_operator_ids"])
    # Independently compare the source operator manifest with accounted source
    # operators; a missing/duplicated operator is never a successful intake.
    if len(operators) + len(out["unresolved_operators"]) != out["source_operator_count"]:
        return finish("BLOCKED", "BLOCKED_VECTOR_OPERATOR_MANIFEST_DISAGREEMENT",
                      "The source operator count differs from parsed/rejected records.")
    parts, crossings = _connected_strokes(operators, strokes, max_pair_checks)
    if parts is None:
        return finish("BLOCKED", "BLOCKED_VECTOR_TOPOLOGY_PAIR_BUDGET",
                      "Intersection budget exceeded. No partial connected groups are retained.")
    incomplete = bool(out["unresolved_operators"] or out["unresolved_paths"])
    parallels = _exact_parallel_runs(operators)
    possible_frames = set()
    for part_index, connected in sorted(parts.items()):
        ids = sorted({s.owner for s in connected})
        degree = Counter(p for s in connected for p in (s.start, s.end))
        witnesses = [operators[i] for i in ids]
        box = _bounds(p for i in ids for p in operators[i]["points_pt"])
        role = _disposition(connected, degree, bounds, box, crossing=part_index in crossings,
                            parallel=all(i in parallels for i in ids))
        if any(w["geometry_quality"] == "DEGENERATE_QUAD_STROKE_REVIEW_ONLY"
               for w in witnesses):
            # Even if nearby strokes form a plausible contour, the origin
            # includes a degenerate operator. Do not infer a valid section.
            role = "DEGENERATE_QUAD_STROKE_REVIEW_ONLY"
        elif role == "OPEN_CHAIN" and any(w["paint"] in ("f", "fs", "sf") for w in witnesses):
            role = "FILL_BOUNDARY_UNRESOLVED"
        reference = witnesses[0]
        candidate_id = f"{prefix}:topology{reference['path_index']}.{reference['operator_index']}"
        if role == "CLOSED_CONTOUR" and len(connected) == 4 and all(s.axis for s in connected):
            possible_frames.add(candidate_id)
        out["groups"].append({
            "candidate_id": candidate_id,
            "document_id": document_id, "page": page_number, "role": role,
            "bbox_pt": list(box), "source_operators": witnesses,
            "source_path_indices": sorted({r["path_index"] for r in witnesses}),
            "status": "BLOCKED" if incomplete or role == "BRANCHED_STROKES" else "UNRESOLVED",
            "reason": "Source page has unparsed vector operators." if incomplete else _REASONS[role],
            "detail_boundary_verified": False, "physical_member_verified": False,
            "quantity_approved": False, "financially_payable": False,
        })
    if possible_frames and not _mark_enclosing_contours(out["groups"], possible_frames, max_pair_checks):
        out["groups"].clear()
        return finish("BLOCKED", "BLOCKED_VECTOR_TOPOLOGY_ENCLOSURE_BUDGET",
                      "Containment budget exceeded. No partial connected groups are retained.")
    out["group_count"] = len(out["groups"])
    out["source_operators_accounted_for"] = not incomplete
    if incomplete:
        return finish("BLOCKED", "BLOCKED_UNSUPPORTED_VECTOR_OPERATORS",
                      "Unsupported or unreadable vector data remains in the source ledger.")
    if not operators:
        return finish("EXAMINED", "NO_VECTOR_PATHS", "No vector operators were present in the page snapshot.")
    if out["source_degenerate_quads_review_required"]:
        return finish("UNRESOLVED", "DEGENERATE_QUAD_STROKES_ACCOUNTED_FOR",
                      "All source operators were indexed; collapsed zero-area Quads require "
                      "manual geometry interpretation and cannot certify areas or members.")
    return finish("UNRESOLVED", "VECTOR_TOPOLOGY_CANDIDATES_INDEXED",
                  "Stroke topology is available. Verify the drawing role and semantic boundary.")
