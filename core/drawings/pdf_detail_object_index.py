"""Evidence-bound semantic *candidates* from exhaustive PDF page-zone inventories.

A named detail, a member type mark, and an indexed vector zone are three
DIFFERENT facts. Never turn a page tile, textual label, title or adjacency into
an accepted member, a measured detail, a floor repeat, or a billable quantity.

Input: assemble_pdf_detail_inventory() result (all documents/page tiles).
Output: separately traceable title/mark candidates, potential same-page links,
unknown visual zones, and a provisional same-document type reference index.

This is an explicit intermediate toward automatic detail recognition, not a
finished symbol classifier or a full geometric detail segmentation engine.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from math import isfinite
import re
import unicodedata
from typing import Mapping

from core.drawings.pdf_detail_evidence_links import link_pdf_detail_geometry_evidence

_MAX_SHEETS = 600
_MAX_REGIONS = 40000
_MAX_TITLES = 10000
_MAX_TYPE_MARKS = 10000
_MARK = re.compile(r'^\s*(BR|BP|SC|SW|C|B|F|T|W|S|P)\s*[-–.]?\s*([1-9][0-9]{0,2})\s*$', re.I)

# Type-letter families are only hypotheses without a classified context.
_FAMILY_FOR_MARK = {'B': 'beam', 'C': 'column', 'F': 'foundation',
                    'SC': 'column', 'SW': 'wall_opening', 'W': 'wall_opening',
                    'BR': 'bracing', 'BP': 'reinforcement_connection'}
# Long/explicit words, not short ambiguous syllables such as Persian "پی".
_TITLE_WORDS = {
    'bracing': ('بادبند', 'مهاربند', 'brace', 'bracing'),
    'beam': ('تیر', 'پل', 'beam', 'girder'),
    'column': ('ستون', 'column'),
    'foundation': ('فونداسیون', 'فنداسیون', 'شناژ', 'footing', 'foundation', 'grade beam'),
    'slab_roof': ('دال', 'سقف', 'بام', 'roof', 'slab'),
    'wall_opening': ('دیوار', 'تیغه', 'بازشو', 'پنجره', 'wall', 'partition', 'opening', 'window'),
    'stair_ramp': ('پله', 'رمپ', 'stair', 'ramp'),
    'reinforcement_connection': ('آرماتور', 'میلگرد', 'خاموت', 'اتصال', 'مدفون',
                                 'صفحه ستون', 'بیس پلیت', 'base plate', 'baseplate',
                                 'rebar', 'reinforcement', 'joint', 'connection', 'embedment'),
    'architecture_finishes': ('معماری', 'نازک کاری', 'کاشی', 'سرامیک', 'architectural', 'finish', 'tilework'),
    'mechanical': ('لوله', 'کانال', 'مکانیکی', 'mechanical', 'pipe', 'duct'),
    'electrical': ('برق', 'کابل', 'electrical', 'cable', 'wiring'),
}
_SHEET_FAMILY = {'beam_layout_plan': 'beam', 'column_type_plan': 'column',
                 'column_detail': 'column', 'foundation_plan': 'foundation',
                 'roof_drainage_plan': 'slab_roof', 'formwork_plan': 'slab_roof'}


def _norm(text: object) -> str:
    txt = unicodedata.normalize('NFKC', str(text or '')).casefold()
    txt = txt.translate(str.maketrans({'ي': 'ی', 'ى': 'ی', 'ك': 'ک', 'ة': 'ه'}))
    txt = txt.replace('ـ', '').replace('\u200c', '')
    return ''.join(ch for ch in txt if ch.isalnum())


def _bbox(box: object) -> tuple[float, float, float, float] | None:
    if not isinstance(box, (tuple, list)) or len(box) != 4:
        return None
    try:
        vals = tuple(float(x) for x in box)
    except (ValueError, TypeError):
        return None
    if not all(isfinite(x) for x in vals):
        return None
    return vals if vals[0] < vals[2] and vals[1] < vals[3] else None


def _touches(a: tuple, b: tuple) -> bool:
    # Interior overlap, not a mere tile-boundary touch.
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _family_words(title: object, *, sheet_kind: object = None) -> list[str]:
    norm = _norm(title)
    readable = unicodedata.normalize('NFKC', str(title or '')).casefold()
    readable = readable.translate(str.maketrans({'ي': 'ی', 'ى': 'ی', 'ك': 'ک', 'ة': 'ه'}))
    readable = readable.replace('ـ', '').replace('\u200c', ' ')
    def matches(word: str) -> bool:
        # The short Persian "پل" (bridge/beam) is a prefix of "پله" (stair).
        # It must be an isolated term; otherwise a stair detail gains a
        # fabricated beam family even though no beam evidence exists.
        if word == 'پل':
            return re.search(r'(?<!\w)پل(?!\w)', readable) is not None
        return _norm(word) in norm
    families = {family for family, words in _TITLE_WORDS.items()
                if any(matches(word) for word in words)}
    if not families and sheet_kind in _SHEET_FAMILY:
        families.add(_SHEET_FAMILY[sheet_kind])
    return sorted(families)


def _tag(raw: object) -> tuple[str, str | None] | None:
    match = _MARK.fullmatch(str(raw or ''))
    if not match:
        return None
    family, num = match.group(1).upper(), int(match.group(2))
    return f'{family}{num}', _FAMILY_FOR_MARK.get(family)


def build_pdf_detail_object_index(coverage: Mapping, *, max_candidates: int = 20000) -> dict:
    """Create a loss-aware detail/type candidate index from an *entire* PDF input.

    A page-zone is a search coverage unit, NOT an identified construction
    detail. A title remains unsegmented even if vector ink is nearby. No
    inferred family/type is accepted as a physical member or measured amount.
    """
    if type(max_candidates) is not int or not 1 <= max_candidates <= 40000:
        raise ValueError('bounded detail-candidate budget required')
    if not isinstance(coverage, Mapping) or not coverage.get('all_input_pages_indexed') or coverage.get('errors'):
        raise ValueError('Cannot index detail objects from incomplete PDF page coverage')
    pages = list(coverage.get('sheet_inventory', ()))
    zones = list(coverage.get('region_inventory', ()))
    anchors = list(coverage.get('detail_title_anchors', ()))
    if not (pages and len(pages) <= _MAX_SHEETS and len(zones) <= _MAX_REGIONS and len(anchors) <= _MAX_TITLES):
        raise ValueError('PDF detail evidence exceeds bounded indexing budget')
    doc_ids = [d.get('document_id') for d in coverage.get('documents', ())]
    if len(set(doc_ids)) != len(doc_ids) or not doc_ids:
        raise ValueError('Invalid document identity')
    page_ref = {}
    expected_pages = {(d['document_id'], i) for d in coverage['documents']
                      for i in range(1, int(d['page_count']) + 1)}
    for p in pages:
        k = (p.get('document_id'), p.get('page'))
        if k in page_ref or k[0] not in doc_ids or type(k[1]) is not int or k[1] < 1:
            raise ValueError('Duplicate or invalid PDF page identity')
        page_ref[k] = p
    if set(page_ref) != expected_pages:
        raise ValueError('Source document page inventory has missing or foreign pages')
    zone_ref, zone_by_page = {}, defaultdict(list)
    for zone in zones:
        k = (zone.get('document_id'), zone.get('page'))
        rid = zone.get('region_id')
        if (k not in page_ref or not isinstance(rid, str) or
                not rid.startswith(f'{k[0]}:p{k[1]}:') or rid in zone_ref or
                _bbox(zone.get('bbox_pt')) is None):
            raise ValueError('Invalid source zone identity or geometry')
        zone_ref[rid] = zone
        zone_by_page[k].append(zone)
    if any(not zone_by_page[k] for k in page_ref):
        raise ValueError('PDF page missing coverage zones')

    anchors_by_page = defaultdict(list)
    seen_title_ids = set()
    for title in anchors:
        k = (title.get('document_id'), title.get('page'))
        aid = title.get('anchor_id')
        if k not in page_ref or not isinstance(aid, str) or not aid or aid in seen_title_ids:
            raise ValueError('Duplicate or unbound detail title anchor')
        seen_title_ids.add(aid)
        anchors_by_page[k].append(title)

    # Geometric candidates are kept separate from explicit text/title
    # candidates. A proximity group cannot become a semantic detail or BOQ.
    vector_group_pages = list(coverage.get('vector_geometry_groupings', ()))
    vector_groups = []
    vector_group_blockers = []
    if vector_group_pages:
        by_key = {(g.get('document_id'), g.get('page')): g for g in vector_group_pages}
        if len(by_key) != len(vector_group_pages) or set(by_key) != set(page_ref):
            raise ValueError('Missing or duplicate vector grouping page identity')
        for key in sorted(by_key):
            g = by_key[key]
            if not g.get('all_source_paths_grouped'):
                vector_group_blockers.append({
                    'document_id': key[0], 'page': key[1],
                    'status': g.get('status', 'BLOCKED_VECTOR_GROUPING'),
                    'ungrouped_path_count': g.get('ungrouped_path_count'),
                    'financially_payable': False,
                })
                continue
            members = g.get('groups', ())
            if type(g.get('source_path_count')) is not int or len(members) != g.get('group_count'):
                raise ValueError('Invalid vector grouping counts')
            all_path_ids = [i for item in members for i in item.get('source_path_indices', ())]
            if sorted(all_path_ids) != list(range(1, g['source_path_count']+1)):
                raise ValueError('Missing or duplicate source PDF path in grouped evidence')
            for item in members:
                if (item.get('document_id'), item.get('page')) != key or item.get('financially_payable') is not False:
                    raise ValueError('Invalid or financially approved vector group')
            vector_groups.extend(members)
    objects = []
    used_visual_zones = set()
    title_candidate_ids = defaultdict(list)
    for k in sorted(page_ref):
        page = page_ref[k]
        for title in sorted(anchors_by_page[k], key=lambda t: t['anchor_id']):
            abox = _bbox(title.get('bbox_pt'))
            pzones = zone_by_page[k]
            matched = sorted(z['region_id'] for z in pzones
                             if abox is not None and _touches(abox, _bbox(z['bbox_pt'])))
            if not matched:
                raise ValueError('Title anchor has no location in indexed page zones')
            family = _family_words(title.get('title_preview'), sheet_kind=page.get('sheet_kind'))
            # A title such as "beam-column connection" is inherently multi-family.
            # Do NOT silently attach it only to a column or beam instance.
            page_boxes = [_bbox(z['bbox_pt']) for z in pzones]
            page_width = max(b[2] for b in page_boxes) - min(b[0] for b in page_boxes)
            # Full-width bill rows and paragraph descriptions often contain
            # 'detail' or 'connection'. They are NOT isolated drawing headings.
            broad = (abox is not None and (abox[2]-abox[0]) > .62*page_width)
            # A text label must not be promoted when any underlying source
            # tile has an incomplete extraction, even if its words are clear.
            blocked_source = any(zone_ref[rid]['status'] == 'BLOCKED' for rid in matched)
            status = ('BLOCKED_DETAIL_TITLE_SOURCE_INCOMPLETE' if blocked_source else
                      'BLOCKED_BROAD_TITLE_TEXT_NOT_DETAIL' if broad else
                      'BLOCKED_UNKNOWN_DETAIL_FAMILY' if not family else
                      'MULTI_FAMILY_DETAIL_TITLE_CANDIDATE' if len(family) > 1 else
                      'SINGLE_FAMILY_DETAIL_TITLE_CANDIDATE')
            cid = f"DETAIL_TITLE:{title['anchor_id']}"
            object_rec = {
                'candidate_id': cid, 'kind': 'EXPLICIT_DETAIL_TITLE',
                'document_id': k[0], 'page': k[1],
                'title_anchor_id': title['anchor_id'],
                'title_preview': str(title.get('title_preview', ''))[:96],
                'bbox_pt': list(title.get('bbox_pt', ())),
                'region_ids': matched, 'family_candidates': family,
                'type_tag': None, 'linked_type_candidate_ids': [],
                'status': status, 'detail_boundary_verified': False,
                'physical_member_verified': False, 'financially_payable': False,
                'quantity_approved': False,
                'reason': ('A source tile has incomplete PDF extraction; detail evidence cannot be trusted'
                           if blocked_source else
                           'Title is located, but exact drawing/section boundary and member ownership remain unverified'),
            }
            objects.append(object_rec)
            title_candidate_ids[k].append(object_rec)
            used_visual_zones.update(rid for rid in matched
                                     if zone_ref[rid].get('vector_path_count', 0) or zone_ref[rid].get('image_block_count', 0))

    mark_by_source = defaultdict(list)
    for k in sorted(page_ref):
        for zone in sorted(zone_by_page[k], key=lambda z: z['region_id']):
            if zone.get('status') not in ('UNRESOLVED', 'EXAMINED', 'BLOCKED'):
                raise ValueError('Unknown PDF zone disposition')
            raw_marks = zone.get('searchable_member_marks', ())
            if not isinstance(raw_marks, (tuple, list)) or len(raw_marks) > 1000:
                raise ValueError('Unbounded member-mark input')
            for raw in raw_marks:
                norm = _tag(raw)
                if norm is None:
                    raise ValueError('Unparseable member-type mark in indexed PDF zone')
                tag, family = norm
                mark_by_source[(k[0], k[1], tag)].append(zone)
    if len(mark_by_source) > _MAX_TYPE_MARKS:
        raise ValueError('Too many member-type marks for bounded detail indexing')

    type_objects = []
    for (doc_id, page, tag), grouped_zones in sorted(mark_by_source.items()):
        ids = sorted({z['region_id'] for z in grouped_zones})
        if any(z.get('status') == 'BLOCKED' for z in grouped_zones):
            status = 'BLOCKED_TYPE_MARK_SOURCE_INCOMPLETE'
        elif any(z.get('vector_path_count', 0) or z.get('image_block_count', 0) for z in grouped_zones):
            status = 'TYPE_MARK_WITH_VISUAL_EVIDENCE_CANDIDATE'
        else:
            status = 'TYPE_MARK_TEXT_ONLY_CANDIDATE'
        related_titles = [o for o in title_candidate_ids[(doc_id,page)]
                          if set(o['region_ids']) & set(ids)]
        type_tag_family = _tag(tag)[1]
        compatible = [o for o in related_titles
                      if type_tag_family and type_tag_family in o['family_candidates']]
        if (len(compatible) == 1 and len(related_titles) == 1 and
                not compatible[0]['status'].startswith('BLOCKED_') and
                status != 'BLOCKED_TYPE_MARK_SOURCE_INCOMPLETE'):
            proposed = compatible[0]['candidate_id']
            association = 'PROPOSED_SAME_REGION_TITLE_ASSOCIATION'
        elif related_titles:
            proposed = None
            association = 'BLOCKED_AMBIGUOUS_OR_INCOMPATIBLE_TITLE_ASSOCIATION'
        else:
            proposed = None
            association = 'NO_UNAMBIGUOUS_SAME_REGION_TITLE'
        type_obj = {
            'candidate_id': f'TYPE_MARK:{doc_id}:p{page}:{tag}',
            'kind': 'EXPLICIT_TEXT_TYPE_MARK', 'document_id': doc_id,
            'page': page, 'type_tag': tag,
            'family_candidates': [type_tag_family] if type_tag_family else [],
            'region_ids': ids,
            'source_title_candidate_ids': sorted(o['candidate_id'] for o in related_titles),
            'proposed_detail_title_id': proposed,
            'title_association_status': association,
            'status': status, 'physical_member_verified': False,
            'detail_boundary_verified': False, 'financially_payable': False,
            'quantity_approved': False,
            'reason': 'Text type mark, nearby title and visual regions are not proof of a bounded physical detail',
        }
        type_objects.append(type_obj)
        if proposed:
            obj = next(o for o in objects if o['candidate_id'] == proposed)
            obj['linked_type_candidate_ids'].append(type_obj['candidate_id'])
        # The associated type mark only accounts for the *marked* tile(s).
        used_visual_zones.update(rid for rid in ids
                                 if zone_ref[rid].get('vector_path_count', 0) or zone_ref[rid].get('image_block_count', 0))

    objects.extend(type_objects)
    if len(objects) > max_candidates:
        raise ValueError('PDF detail-candidate budget exhausted')
    # Preserve every unassigned visual zone. No unlabeled section/detail can
    # vanish merely because there is no searchable title or member symbol.
    visual = {z['region_id'] for z in zones
              if z.get('vector_path_count', 0) or z.get('image_block_count', 0)}
    unassigned = [{
        'region_id': rid,
        'document_id': zone_ref[rid]['document_id'], 'page': zone_ref[rid]['page'],
        'bbox_pt': zone_ref[rid]['bbox_pt'],
        'vector_path_count': zone_ref[rid].get('vector_path_count', 0),
        'image_block_count': zone_ref[rid].get('image_block_count', 0),
        'status': 'UNRESOLVED_UNLABELED_VISUAL_REGION',
        'reason': 'This visual region is indexed but is not attached to any explicit title/type mark; it still needs semantic detail identification',
        'financially_payable': False,
    } for rid in sorted(visual - used_visual_zones)]
    if (used_visual_zones | {v['region_id'] for v in unassigned}) != visual:
        raise AssertionError('Unaccounted visual PDF region')
    tag_sources = defaultdict(list)
    for rec in type_objects:
        tag_sources[(rec['document_id'], rec['type_tag'])].append(rec)
    cross_refs = []
    for (doc, tag), recs in sorted(tag_sources.items()):
        if len(recs) < 2:
            continue
        cross_refs.append({
            'document_id': doc, 'type_tag': tag,
            'candidate_ids': [r['candidate_id'] for r in recs],
            'pages': [r['page'] for r in recs],
            'status': 'POSSIBLE_SAME_DOCUMENT_TYPE_REFERENCE_UNVERIFIED',
            'physical_member_count': None,
            'quantity_approved': False, 'financially_payable': False,
        })
    link_ledger = link_pdf_detail_geometry_evidence(
        coverage, objects, vector_group_pages,
    )
    families = Counter(fam for c in objects for fam in c['family_candidates'])
    statuses = Counter(c['status'] for c in objects)
    return {
        'page_count': len(pages), 'source_coverage_index_complete': True,
        'detail_candidates': objects,
        'detail_title_candidate_count': len(objects)-len(type_objects),
        'type_mark_candidate_count': len(type_objects),
        'candidate_status_counts': dict(sorted(statuses.items())),
        'family_candidate_counts': dict(sorted(families.items())),
        'unassigned_visual_regions': unassigned,
        'vector_geometry_groups': vector_groups,
        'geometry_detail_link_ledger': link_ledger,
        'vector_geometry_group_count': len(vector_groups),
        'vector_grouping_blocked_pages': vector_group_blockers,
        'vector_grouping_page_count': len(vector_group_pages),
        'all_vector_paths_grouped': bool(vector_group_pages) and not vector_group_blockers,
        # Empty-looking tiles after failed extraction are NOT proof of a
        # blank drawing; show these separately from visible orphan geometry.
        'blocked_source_region_ids': sorted(z['region_id'] for z in zones if z['status'] == 'BLOCKED'),
        'blocked_source_region_count': sum(z['status'] == 'BLOCKED' for z in zones),
        'visual_region_count': len(visual),
        'visual_regions_accounted_for': len(visual),
        'visual_semantics_unresolved_region_count': len(visual),
        'potential_same_document_type_references': cross_refs,
        'detail_geometry_fully_segmented': False,
        'semantic_details_fully_interpreted': False,
        'physical_member_count': None,
        'quantity_approval_count': 0,
        'complete': False,
        'acceptance': 'PARTIAL_NO_GO',
    }
