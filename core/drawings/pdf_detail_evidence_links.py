"""Non-financial provenance ledger for PDF geometry, detail titles and type marks.

Coordinates and same-tile text are REVIEW EVIDENCE only. This deliberately
does not solve semantic detail segmentation or cross-sheet member identity.
Every provisional group and every explicit title gets an auditable status.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Mapping


def link_pdf_detail_geometry_evidence(
    coverage: Mapping, detail_objects: list[dict], vector_group_pages: list[dict],
    *, max_records: int = 40000,
) -> dict:
    """A page-local, strictly provisional and loss-accounted evidence graph.

    Groups from blocked pages cannot produce title/type links. One-to-many
    title/group associations stay blocked, rather than choosing the closest
    geometry. Same-region type labels are not reliable point locations.
    """
    if type(max_records) is not int or not 1 <= max_records <= 80000:
        raise ValueError('Bounded evidence link budget required')
    pages = {(p['document_id'], p['page']) for p in coverage.get('sheet_inventory', ())}
    titles = {}
    for item in detail_objects:
        if item.get('kind') != 'EXPLICIT_DETAIL_TITLE':
            continue
        aid = item.get('title_anchor_id')
        key = (item.get('document_id'), item.get('page'))
        if (key not in pages or not isinstance(aid, str) or aid in titles):
            raise ValueError('Invalid explicit title provenance for geometry link')
        titles[aid] = item
    anchors = coverage.get('detail_title_anchors', ())
    if len(titles) != len(anchors) or {
        a.get('anchor_id') for a in anchors
    } != set(titles):
        raise ValueError('Title/geometry provenance mismatch')

    page_groups = {}
    for item in vector_group_pages:
        key = (item.get('document_id'), item.get('page'))
        if key not in pages or key in page_groups:
            raise ValueError('Missing, foreign or repeated page geometry witness')
        page_groups[key] = item
    if vector_group_pages and set(page_groups) != pages:
        raise ValueError('Incomplete page geometry witness')
    if sum(len(p.get('groups', ())) for p in vector_group_pages) + len(titles) > max_records:
        raise ValueError('Detail geometry link record budget exhausted')

    groups = []
    title_to_groups = defaultdict(set)
    seen_group_ids = set()
    blocked_pages = set()
    rejected_partial_groups = 0
    for key, entry in sorted(page_groups.items()):
        if not entry.get('all_source_paths_grouped'):
            blocked_pages.add(key)
            # Keep the page blocked if an upstream grouping attempt returned
            # partial candidates. Never let those provisional groups influence
            # title or type linking, but record how many were discarded.
            rejected_partial_groups += len(entry.get('groups', ()))
            continue
        for group in entry.get('groups', ()):
            group_id = group.get('candidate_id')
            if (group_id in seen_group_ids or not isinstance(group_id, str)
                    or not group_id.startswith(f'{key[0]}:p{key[1]}:')
                    or (group.get('document_id'), group.get('page')) != key
                    or group.get('financially_payable') is not False
                    or group.get('detail_boundary_verified') is not False):
                raise ValueError('Invalid, duplicate or approved geometry group')
            seen_group_ids.add(group_id)
            nearby = group.get('nearby_title_anchor_ids', ())
            if not isinstance(nearby, (list, tuple)) or len(nearby) != len(set(nearby)):
                raise ValueError('Duplicate or invalid nearby title witnesses')
            for aid in nearby:
                title = titles.get(aid)
                if title is None or (title['document_id'], title['page']) != key:
                    raise ValueError('Foreign or missing title anchor in geometry group')
                title_to_groups[aid].add(group_id)
            groups.append((group, sorted(nearby)))

    title_records = []
    title_link_status = {}
    for aid, title in sorted(titles.items()):
        key = (title['document_id'], title['page'])
        group_ids = sorted(title_to_groups[aid])
        if key in blocked_pages:
            status = 'BLOCKED_GEOMETRY_GROUPING_INCOMPLETE'
        elif key not in page_groups:
            status = 'BLOCKED_NO_VECTOR_GROUP_INDEX'
        elif title['status'].startswith('BLOCKED_'):
            status = 'BLOCKED_TITLE_SOURCE_OR_CLASSIFICATION'
        elif len(group_ids) == 0:
            status = 'UNRESOLVED_TITLE_WITHOUT_NEARBY_VECTOR_GROUP'
        elif len(group_ids) > 1:
            status = 'BLOCKED_TITLE_NEAR_MULTIPLE_VECTOR_GROUPS'
        else:
            status = 'PROPOSED_TITLE_NEAR_SINGLE_VECTOR_GROUP'
        title_link_status[aid] = status
        title_records.append({
            'title_candidate_id': title['candidate_id'],
            'title_anchor_id': aid,
            'document_id': key[0], 'page': key[1],
            'possible_vector_group_ids': group_ids,
            'status': status,
            'detail_boundary_verified': False,
            'physical_member_verified': False,
            'quantity_approved': False,
            'financially_payable': False,
        })

    type_by_id = {
        item['candidate_id']: item
        for item in detail_objects if item.get('kind') == 'EXPLICIT_TEXT_TYPE_MARK'
    }
    linked_groups = []
    for group, nearby in groups:
        key = (group['document_id'], group['page'])
        title = titles[nearby[0]] if len(nearby) == 1 else None
        proposed_title = None
        type_ids = []
        if not nearby:
            status = 'UNRESOLVED_GROUP_WITHOUT_TITLE'
        elif len(nearby) > 1:
            status = 'BLOCKED_GROUP_NEAR_MULTIPLE_TITLES'
        elif title_link_status[nearby[0]] != 'PROPOSED_TITLE_NEAR_SINGLE_VECTOR_GROUP':
            status = 'BLOCKED_TITLE_OR_GROUP_AMBIGUITY'
        else:
            status = 'PROPOSED_GROUP_NEAR_SINGLE_EXPLICIT_TITLE'
            proposed_title = title['candidate_id']
            # A type mark is on a coarse page tile, not a glyph-localized
            # coordinate. Preserve the weak reference without claiming that
            # this vector geometry is the corresponding physical member.
            possible_marks = sorted(title.get('linked_type_candidate_ids', ()))
            if len(possible_marks) == 1:
                mark = type_by_id.get(possible_marks[0])
                if (mark is None or mark.get('proposed_detail_title_id') != proposed_title
                        or (mark.get('document_id'), mark.get('page')) != key
                        or mark.get('status', '').startswith('BLOCKED_')):
                    raise ValueError('Untrusted cross-source type mark in geometry link')
                type_ids = possible_marks
        linked_groups.append({
            'vector_group_candidate_id': group['candidate_id'],
            'document_id': key[0], 'page': key[1],
            'source_path_indices': list(group['source_path_indices']),
            'possible_title_anchor_ids': nearby,
            'proposed_title_candidate_id': proposed_title,
            'coarse_zone_type_mark_candidate_ids': type_ids,
            'type_source_quality': (
                'COARSE_PAGE_TILE_ONLY_NOT_GLYPH_POSITION'
                if type_ids else 'NONE'
            ),
            'status': status,
            'detail_boundary_verified': False,
            'type_verified': False,
            'physical_member_verified': False,
            'quantity_approved': False,
            'financially_payable': False,
        })
    if {g['vector_group_candidate_id'] for g in linked_groups} != seen_group_ids:
        raise AssertionError('Geometry candidate disappeared in title/link processing')
    status_counts = Counter(x['status'] for x in linked_groups)
    return {
        'source_page_count': len(pages),
        'pages_with_vector_group_index': len(page_groups),
        'blocked_geometry_page_count': len(blocked_pages),
        'rejected_partial_group_count': rejected_partial_groups,
        'geometry_group_link_records': linked_groups,
        'geometry_group_link_count': len(linked_groups),
        'geometry_group_link_status_counts': dict(sorted(status_counts.items())),
        'title_coverage_records': title_records,
        'title_coverage_count': len(title_records),
        'possible_page_local_links': sum(
            x['proposed_title_candidate_id'] is not None for x in linked_groups),
        'possible_coarse_type_references': sum(bool(x['coarse_zone_type_mark_candidate_ids'])
                                              for x in linked_groups),
        'all_vector_groups_accounted_for': len(linked_groups) == len(seen_group_ids),
        'all_titles_accounted_for': len(title_records) == len(titles),
        'cross_document_links_approved': 0,
        'physical_member_count': None,
        'quantity_approval_count': 0,
        'complete': False,
        'acceptance': 'PARTIAL_NO_GO',
    }
