"""Conservative source-indexed geometric path groups for PDF review.

These are BBOX-PROXIMITY HYPOTHESES, not independently segmented sections,
member identities, semantic details, calibrated measurements or BOQ lines.
When a page is too dense or source evidence is missing, keep an explicit
blocked page record instead of silently reporting fewer details.
"""
from __future__ import annotations

from collections import defaultdict
from math import isfinite


def _bbox(value):
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise ValueError("Invalid PDF path/anchor bbox")
    try:
        b = tuple(float(n) for n in value)
    except (ValueError, TypeError):
        raise ValueError("Invalid PDF path/anchor bbox") from None
    if not all(isfinite(n) for n in b) or b[0] >= b[2] or b[1] >= b[3]:
        raise ValueError("Invalid PDF path/anchor bbox")
    return b


def _gap(a, b):
    dx = max(0.0, a[0] - b[2], b[0] - a[2])
    dy = max(0.0, a[1] - b[3], b[1] - a[3])
    return max(dx, dy)


def _framing(a, b):
    """An enclosing frame is not evidence that interior shapes are one detail."""
    def encloses(big, small):
        return (big[0] <= small[0] and big[1] <= small[1]
                and big[2] >= small[2] and big[3] >= small[3]
                and (big[2]-big[0])*(big[3]-big[1])
                > 5*(small[2]-small[0])*(small[3]-small[1]))
    return encloses(a, b) or encloses(b, a)


def index_pdf_vector_path_groups(path_boxes, title_anchors, *, document_id,
                                 page, source_blocked=False, max_paths=3000,
                                 max_pair_checks=250000, tolerance_pt=0.75,
                                 title_nearby_pt=36.0):
    """Keep every index accountable, even on failed or excessive grouping.

    Path IDs are 1-based get_drawings() order on this exact document/page.
    Spatial overlap is never proof of shared physical detail or a title link.
    """
    if not isinstance(document_id, str) or not document_id.strip() or type(page) is not int or page <= 0:
        raise ValueError("Stable PDF page identity required")
    if any(type(n) is not int or n < 1 for n in (max_paths, max_pair_checks)):
        raise ValueError("Positive group budgets required")
    if any(not isfinite(n) or n < 0 for n in (tolerance_pt, title_nearby_pt)):
        raise ValueError("Invalid proximity bounds")
    boxes = [_bbox(box) for box in path_boxes]
    count = len(boxes)
    def blocked(reason):
        return {'document_id': document_id, 'page': page,
                'status': reason, 'source_path_count': count,
                'grouped_path_count': 0, 'ungrouped_path_count': count,
                'group_count': 0, 'groups': [],
                'all_source_paths_grouped': False,
                'detail_boundaries_verified': False,
                'physical_member_count': None, 'quantity_approval_count': 0,
                'financially_payable': False}
    if source_blocked:
        return blocked('BLOCKED_SOURCE_EVIDENCE_INCOMPLETE')
    if count > max_paths:
        return blocked('BLOCKED_VECTOR_GROUP_PATH_BUDGET')
    anchors = []
    seen_anchors = set()
    for item in title_anchors:
        aid = item.get('anchor_id')
        if not isinstance(aid, str) or not aid or aid in seen_anchors:
            raise ValueError('Invalid PDF detail title anchor ID')
        if item.get('document_id') != document_id or item.get('page') != page:
            raise ValueError('Foreign PDF detail title anchor')
        seen_anchors.add(aid)
        anchors.append((aid, _bbox(item.get('bbox_pt'))))
    if not count:
        return {'document_id': document_id, 'page': page,
                'status': 'NO_VECTOR_PATHS', 'source_path_count': 0,
                'grouped_path_count': 0, 'ungrouped_path_count': 0,
                'group_count': 0, 'groups': [],
                'all_source_paths_grouped': True,
                'detail_boundaries_verified': False,
                'physical_member_count': None, 'quantity_approval_count': 0,
                'financially_payable': False}
    parent = list(range(count))
    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # X-sweep avoids unconditional all-pairs work. Very dense overlapping
    # sheets fail closed at a finite comparison budget, without partial groups.
    active = []
    comparisons = 0
    for idx, box in sorted(enumerate(boxes), key=lambda pair:(pair[1][0], pair[1][1], pair[0])):
        active = [(j, prev) for j, prev in active if prev[2] + tolerance_pt >= box[0]]
        for j, prev in active:
            comparisons += 1
            if comparisons > max_pair_checks:
                return blocked('BLOCKED_VECTOR_GROUP_PAIR_BUDGET')
            if _gap(box, prev) <= tolerance_pt and not _framing(box, prev):
                union(idx, j)
        active.append((idx, box))
    memberships = defaultdict(list)
    for idx, box in enumerate(boxes):
        memberships[root(idx)].append(idx)
    groups = []
    for seq, members in enumerate(sorted(memberships.values(), key=lambda m:min(m)), 1):
        rect = (min(boxes[i][0] for i in members),
                min(boxes[i][1] for i in members),
                max(boxes[i][2] for i in members),
                max(boxes[i][3] for i in members))
        nearby = sorted(aid for aid, abox in anchors if _gap(rect, abox) <= title_nearby_pt)
        groups.append({
            'candidate_id': f'{document_id}:p{page}:vector_group{seq:05d}',
            'document_id': document_id, 'page': page,
            'bbox_pt': [round(x, 3) for x in rect],
            'source_path_indices': [i+1 for i in sorted(members)],
            'source_path_count': len(members),
            'nearby_title_anchor_ids': nearby,
            'status': 'PROVISIONAL_BBOX_PROXIMITY_GROUP',
            'reason': 'Bounding-box proximity only; exact stroke connectivity, detail boundary and ownership not proven',
            'detail_boundary_verified': False, 'physical_member_verified': False,
            'quantity_approved': False, 'financially_payable': False})
    all_ids = [i for g in groups for i in g['source_path_indices']]
    if sorted(all_ids) != list(range(1, count+1)):
        raise AssertionError('Lost or duplicated PDF path during grouping')
    return {'document_id': document_id, 'page': page,
            'status': 'PROVISIONAL_VECTOR_GROUPS_INDEXED',
            'source_path_count': count,
            'grouped_path_count': len(all_ids),
            'ungrouped_path_count': 0,
            'group_count': len(groups), 'groups': groups,
            'all_source_paths_grouped': True,
            'detail_boundaries_verified': False,
            'physical_member_count': None, 'quantity_approval_count': 0,
            'financially_payable': False}
