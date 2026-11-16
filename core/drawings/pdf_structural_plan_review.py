"""Source-bound review of beam layouts and native foundation plan marks."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from itertools import pairwise
import json
from math import isfinite
import re

from core.drawings.pdf_detail_topology import _cross
from core.drawings.pdf_type_word_witness import TYPE_MARK, _box


_BEAM = 'beam_layout_plan'
_FOUNDATION = ('excavation_plan', 'foundation_plan')
_BEAM_ROLE = 'BEAM_LAYOUT_REGION_REVIEW'
_FOUNDATION_ROLE = 'FOUNDATION_TYPE_MARK_REVIEW'
_COUNT_ROLE = 'FOUNDATION_MARK_COUNT_DISCREPANCY'
_MAX_LOCAL_COMPARISONS = 200_000
_MAX_BEAM_REGIONS = 256
_WORD_PREFIX = {'beam': re.compile(r'B[1-9][0-9]{0,2}'), 'foundation': re.compile(r'[FT][1-9][0-9]{0,2}')}
_SPAN = 'ابتدا و انتهای دهانه، تکیه‌گاه‌ها و آکس و تراز همان محدوده'
_BEAM_TYPE = 'علامت خوانای تیپ تیر و ارجاع یکتای آن به دهانه'
_FOUNDATION_BOUNDARY = 'حد اجرایی مستقل همان علامت در شیت و انتساب یکتا به تیپ'
_MESSAGES = {
    'STRUCTURAL_PLAN_AUTHORITY_BLOCKED': ('نسخه یا اعتبار شیت برای این بررسی تعیین تکلیف نشده است.',
                                          ('نسخهٔ حاکم و مدرک اعتبار همان شیت',)),
    'STRUCTURAL_PLAN_EVIDENCE_INCOMPLETE': ('خوانش منبع یا جست‌وجوی محدوده در این شیت کامل نشده است.',
                                            ('صفحهٔ خوانا و بازبینی کامل هندسه و نوشته‌ها',)),
    'BEAM_SPAN_SUPPORTS_UNVERIFIED': ('یک تیپ بومی PDF داخل مرز برداری قرار دارد و تکیه‌گاه‌ها و تراز دهانه هنوز مستند نیستند.',
                                      (_SPAN, 'ارجاع به دیتیل اجرایی همان دهانه')),
    'BEAM_LOCAL_TYPE_AMBIGUOUS': ('این محدوده چند خوانش تیپ یا چند مرز محتمل دارد و انتساب یکتا حل نشده است.',
                                 (_BEAM_TYPE, _SPAN)),
    'BEAM_SPAN_BOUNDARY_UNRESOLVED': ('دو لبهٔ موازی در این محدوده دیده می‌شود و مرز و دو سر دهانه هنوز از خطوط مجاور جدا نشده‌اند.',
                                       (_SPAN, _BEAM_TYPE)),
    'BEAM_CONTOUR_WITHOUT_TYPE': ('مرز برداری بسته در این محدوده دیده می‌شود و علامت یکتای تیر داخل آن خوانده نشده است.',
                                  (_BEAM_TYPE, _SPAN)),
    'BEAM_TYPE_MARK_WITHOUT_BOUNDARY': ('علامت تیر در متن اصلی شیت دیده می‌شود و مرز مناسب برای این علامت پیدا نشده است.',
                                        (_SPAN, 'انتساب علامت به مرز مستقل در همین شیت')),
    'BEAM_NO_LOCALIZED_SPAN': ('برای پلان تیرریزی، محدودهٔ دهانه با هندسهٔ محلی قابل استناد پیدا نشده است.',
                                (_SPAN, _BEAM_TYPE)),
    'FOUNDATION_LOCAL_CONTOUR_UNVERIFIED': ('علامت بومی PDF داخل یک پیرامون برداری قرار دارد و کارکرد و محدودهٔ اجرایی آن نیاز به تطبیق دارد.',
                                            (_FOUNDATION_BOUNDARY, 'ارجاع به دیتیل و نسخهٔ اجرایی پی یا پی‌کنی')),
    'FOUNDATION_BOUNDARY_AMBIGUOUS': ('چند پیرامون برای این علامت یا چند علامت در همان پیرامون دیده می‌شود.',
                                      (_FOUNDATION_BOUNDARY,)),
    'FOUNDATION_BOUNDARY_NOT_ISOLATED': ('برای این علامت، پیرامون برداری مستقل و بسته در همان شیت جدا نشده است.',
                                         (_FOUNDATION_BOUNDARY,)),
    'FOUNDATION_PHASE_MARK_COUNT_MISMATCH': ('فراوانی این علامت در شیت‌های پی‌کنی و فونداسیون دارای برچسب بومی در همین فایل متفاوت است.',
                                             ('مقابلهٔ رخدادها با آکس و محدودهٔ اجرایی در دو شیت', 'نسخهٔ حاکم و تعیین تکلیف اختلاف خوانش')),
}


class _LocalSearchLimit(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _Region:
    anchor: dict
    polygon: tuple
    operators: tuple = ()


def _id(kind, *values):
    packed = json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return f'{kind}:{sha256(packed).hexdigest()[:32]}'


def _anchor(page, kind, local_ref, source_ref, bounds, **extra):
    return {'anchor_id': _id('STRUCTURAL_PLAN_SOURCE', page['sha256'], page['page'], kind, local_ref),
            'document_id': page['document_id'], 'page': page['page'],
            'source_name': page['source_name'], 'source_sha256': page['sha256'],
            'kind': kind, 'source_ref': source_ref, 'bbox_pt': list(bounds),
            'coordinate_space': 'unrotated_pdf_points', **extra}


def _sheet_anchor(page):
    return _anchor(page, 'SHEET_EXTENT', 'extent', f"{page['document_id']}:p{page['page']}", page['source_bbox_pt'])


def _review(role, family, code, anchors, *, type_tag=None, blocked=False, **details):
    reason, missing = _MESSAGES[code]
    return {'review_id': _id('STRUCTURAL_PLAN_REVIEW', role, code, sorted(a['anchor_id'] for a in anchors)),
            'role': role, 'family': family, 'status': 'BLOCKED' if blocked else 'REVIEW_REQUIRED',
            'reason_code': code, 'reason': reason, 'missing_evidence': list(missing),
            'type_tag': type_tag, 'anchors': list(anchors), 'financially_payable': False, **details}


def _inside(outer, inner, tolerance=0.0):
    return all(outer[i] - tolerance <= inner[i] and inner[i+2] <= outer[i+2] + tolerance for i in (0, 1))


def _page_problem(page):
    if page['authority_block']:
        return 'STRUCTURAL_PLAN_AUTHORITY_BLOCKED'
    raw = page['raw']
    if (not page['linkable'] or raw['detail_topology'].get('status') == 'BLOCKED'
            or raw['type_word_index'].get('all_words_examined') is not True):
        return 'STRUCTURAL_PLAN_EVIDENCE_INCOMPLETE'
    return None


def _native_words(page):
    index = page['raw']['type_word_index']
    prefix = f"{page['document_id']}:p{page['page']}"
    if (index.get('document_id'), index.get('page')) != (page['document_id'], page['page']):
        raise ValueError('Foreign structural plan word index')
    seen = set()
    words = []
    for word in index['type_word_witnesses']:
        if (word.get('status') != 'ISOLATED_TYPE_WORD_POSITION_CANDIDATE' or word.get('title_anchor_ids')
                or word.get('source_quality') == 'RENDERED_OCR_NOT_VERIFIED'):
            continue
        token = word.get('source_token')
        match = TYPE_MARK.fullmatch(token) if isinstance(token, str) else None
        tag, ordinal = word.get('type_tag'), word.get('source_word_index')
        box = _box(word.get('bbox_pt'))
        if (match is None or tag != match[1].upper() + match[2] or type(ordinal) is not int or ordinal < 1
                or word.get('witness_id') != f'{prefix}:word{ordinal:06d}' or ordinal in seen
                or (word.get('document_id'), word.get('page')) != (page['document_id'], page['page'])
                or not box or not _inside(page['source_bbox_pt'], box, tolerance=1)
                or word.get('financially_payable') is not False):
            raise ValueError('Invalid structural plan native word witness')
        seen.add(ordinal)
        words.append((ordinal, _anchor(page, 'NATIVE_TYPE_WORD', ordinal, word['witness_id'], box,
                                       source_token=token, type_tag=tag)))
    return [word for _, word in sorted(words)]


def _points(operator, count):
    coords = operator.get('points_pt', ())
    if len(coords) != count or any(len(p) != 2 or not all(isfinite(v) for v in p) for p in coords):
        return ()
    return tuple(map(tuple, coords))


def _polygon(operators):
    if len(operators) == 1 and operators[0]['operator'] in {'re', 'qu'}:
        return _points(operators[0], 4)
    if not 3 <= len(operators) <= 16 or any(op['operator'] != 'l' for op in operators):
        return ()
    neighbors = defaultdict(set)
    for op in operators:
        ends = _points(op, 2)
        if not ends or ends[0] == ends[1]:
            return ()
        a, b = ends
        neighbors[a].add(b)
        neighbors[b].add(a)
    if len(neighbors) != len(operators) or any(len(n) != 2 for n in neighbors.values()):
        return ()
    start = min(neighbors)
    loop, previous, current = [start], start, min(neighbors[start])
    while current not in loop:
        loop.append(current)
        previous, current = current, next(iter(neighbors[current] - {previous}))
    return tuple(loop) if current == start and len(loop) == len(neighbors) else ()


def _closed_regions(page, groups):
    for group in groups:
        if group['role'] != 'CLOSED_CONTOUR' or group['status'] == 'BLOCKED':
            continue
        box = _box(group.get('bbox_pt'))
        if not box or not _inside(page['source_bbox_pt'], box, tolerance=.02):
            continue
        polygon = _polygon(group['source_operators'])
        if not polygon:
            continue
        turns = [_cross(polygon[i-2], polygon[i-1], p) for i, p in enumerate(polygon)]
        if not (min(turns) >= 0 < max(turns) or min(turns) < 0 >= max(turns)):
            continue
        ref = group['candidate_id']
        marker = _anchor(page, 'VECTOR_CLOSED_BOUNDARY', ref.rsplit(':', 1)[-1], ref, box,
                         source_operator_ids=[op['source_id'] for op in group['source_operators']])
        yield _Region(marker, polygon)


def _contains_word(region, box):
    if not _inside(region.anchor['bbox_pt'], box):
        return False
    corners = ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))
    signs = [_cross(a, b, p) for a, b in pairwise((*region.polygon, region.polygon[0])) for p in corners]
    return min(signs) > 0 or max(signs) < 0


def _associations(regions, words):
    if len(regions) * len(words) > _MAX_LOCAL_COMPARISONS:
        raise _LocalSearchLimit
    by_region, by_word = defaultdict(list), defaultdict(list)
    for rid, region in enumerate(regions):
        for wid, word in enumerate(words):
            if _contains_word(region, word['bbox_pt']):
                by_region[rid].append(wid)
                by_word[wid].append(rid)
    return by_region, by_word


def _span_lanes(page, groups):
    extent = page['source_bbox_pt']
    short = min(extent[2] - extent[0], extent[3] - extent[1])
    by_axis = ([], [])
    for group in groups:
        if group['role'] not in {'OPEN_CHAIN', 'BRANCHED_STROKES', 'TABLE_OR_PLAN_GRID'}:
            continue
        for op in group['source_operators']:
            if op['operator'] != 'l' or op.get('paint') not in {'s', 'fs', 'sf'}:
                continue
            points = _points(op, 2)
            if not points or not all(_inside(extent, (*p, *p), tolerance=.02) for p in points):
                continue
            a, b = points
            for k in (0, 1):
                if abs(a[1-k] - b[1-k]) <= .15 and .065 * short <= abs(a[k] - b[k]) <= .70 * short:
                    start, end = sorted((a[k], b[k]))
                    by_axis[k].append(((a[1-k] + b[1-k]) / 2, start, end, op['source_id'], points))
    checks = 0
    for k, lanes in enumerate(by_axis):
        lanes.sort()
        for i, left in enumerate(lanes):
            for j in range(i+1, len(lanes)):
                right = lanes[j]
                gap = right[0] - left[0]
                if gap > .025 * short:
                    break
                checks += 1
                if checks > _MAX_LOCAL_COMPARISONS:
                    raise _LocalSearchLimit
                start, end = max(left[1], right[1]), min(left[2], right[2])
                if gap >= .0025 * short and end-start >= .82 * max(left[2]-left[1], right[2]-right[1]):
                    yield k, (start, left[0], end, right[0]), left, right


def _lane_regions(page, groups):
    extent = page['source_bbox_pt']
    for axis, components, *lanes in _span_lanes(page, groups):
        x, y, right, bottom = components if axis == 0 else (components[1], components[0], components[3], components[2])
        box = (x, y, right, bottom)
        operators = []
        for _, _, _, source_ref, points in lanes:
            a, b = points
            envelope = (max(extent[0], min(a[0], b[0]) - .25), max(extent[1], min(a[1], b[1]) - .25),
                        min(extent[2], max(a[0], b[0]) + .25), min(extent[3], max(a[1], b[1]) + .25))
            operators.append(_anchor(page, 'VECTOR_STROKE_OPERATOR', source_ref.rsplit(':d', 1)[-1], source_ref,
                                     envelope, source_points_pt=[list(p) for p in points]))
        refs = [op['source_ref'] for op in operators]
        region = _anchor(page, 'VECTOR_PARALLEL_REVIEW_REGION', sorted(op['anchor_id'] for op in operators),
                         '+'.join(refs), box, source_operator_ids=refs)
        yield _Region(region, ((x, y), (right, y), (right, bottom), (x, bottom)), tuple(operators))


def _coalesce_parallel_region_envelopes(page, regions):
    """Retain every vector operator, but review one identical envelope once.

    Repeated coincident CAD strokes can produce a Cartesian product of
    candidate lane pairs.  Such pairs are *alternatives*, not new spans.
    Only the same normalized local PDF-point envelope is coalesced;
    near/misaligned envelopes remain separate and require review.
    """
    groups = {}
    for region in regions:
        if not region.operators:
            key = ('CLOSED', region.anchor['anchor_id'])
        else:
            key = ('PARALLEL', tuple(round(v, 3) for v in region.anchor['bbox_pt']))
        groups.setdefault(key, []).append(region)
    for key, alternatives in groups.items():
        if key[0] != 'PARALLEL':
            yield alternatives[0]
            continue
        if len(alternatives) == 1:
            region = alternatives[0]
            region.anchor['parallel_pair_alternatives'] = 1
            yield region
            continue
        operators = {op['source_ref']: op for alt in alternatives for op in alt.operators}
        refs = sorted(operators)
        first = alternatives[0]
        anchor = _anchor(
            page, 'VECTOR_PARALLEL_REVIEW_REGION', ('COINCIDENT_ALTERNATIVES', key[1], refs),
            '+'.join(refs), first.anchor['bbox_pt'], source_operator_ids=refs,
            parallel_pair_alternatives=len(alternatives),
            distinct_source_operator_count=len(refs),
            geometry_status='COINCIDENT_VECTOR_PAIRS_UNRESOLVED',
        )
        yield _Region(anchor, first.polygon, tuple(operators[ref] for ref in refs))


def _beam_regions(page, words, groups, closed):
    bounds = page['source_bbox_pt']
    short = min(bounds[2] - bounds[0], bounds[3] - bounds[1])
    regions = []
    for region in closed:
        x, y, right, bottom = region.anchor['bbox_pt']
        length, width = sorted((right-x, bottom-y), reverse=True)
        if .05 * short <= length <= .80 * short and .0025 * short <= width <= .28 * length:
            regions.append(region)
    for region in _lane_regions(page, groups):
        regions.append(region)
        if len(regions) > _MAX_BEAM_REGIONS:
            raise _LocalSearchLimit
    if len(regions) > _MAX_BEAM_REGIONS:
        raise _LocalSearchLimit
    regions = list(_coalesce_parallel_region_envelopes(page, regions))
    by_region, by_word = _associations(regions, words)
    for rid, region in enumerate(regions):
        options = by_region[rid]
        tag = None
        blocked = True
        if region.operators:
            code = 'BEAM_SPAN_BOUNDARY_UNRESOLVED'
        elif not options:
            code = 'BEAM_CONTOUR_WITHOUT_TYPE'
            blocked = False
        elif len(options) == 1 and len(by_word[options[0]]) == 1 and _WORD_PREFIX['beam'].fullmatch(words[options[0]]['type_tag']):
            code = 'BEAM_SPAN_SUPPORTS_UNVERIFIED'
            tag = words[options[0]]['type_tag']
            blocked = False
        else:
            code = 'BEAM_LOCAL_TYPE_AMBIGUOUS'
        yield _review(_BEAM_ROLE, 'beam', code, (region.anchor, *region.operators, *(words[i] for i in options)),
                      type_tag=tag, blocked=blocked,
                      parallel_pair_alternatives=region.anchor.get('parallel_pair_alternatives', 1))
    for i, word in enumerate(words):
        if not by_word[i] and _WORD_PREFIX['beam'].fullmatch(word['type_tag']):
            yield _review(_BEAM_ROLE, 'beam', 'BEAM_TYPE_MARK_WITHOUT_BOUNDARY', (word,), type_tag=word['type_tag'])


def _foundation_marks(words, regions, problem):
    if problem is None:
        try:
            by_region, by_word = _associations(regions, words)
        except _LocalSearchLimit:
            problem = 'STRUCTURAL_PLAN_EVIDENCE_INCOMPLETE'
    for wid, word in enumerate(words):
        if problem:
            yield _review(_FOUNDATION_ROLE, 'foundation', problem, (word,), type_tag=word['type_tag'], blocked=True)
            continue
        candidates = by_word[wid]
        ambiguous = len(candidates) > 1 or any(len(by_region[rid]) > 1 for rid in candidates)
        code = ('FOUNDATION_BOUNDARY_AMBIGUOUS' if ambiguous else 'FOUNDATION_LOCAL_CONTOUR_UNVERIFIED'
                if candidates else 'FOUNDATION_BOUNDARY_NOT_ISOLATED')
        yield _review(_FOUNDATION_ROLE, 'foundation', code, (word, *(regions[i].anchor for i in candidates)),
                      type_tag=word['type_tag'], blocked=ambiguous)


def _phase_discrepancies(samples):
    if any(_page_problem(page) for page, _ in samples) or {p['sheet_kind'] for p, _ in samples} != set(_FOUNDATION):
        return
    observed, counts = [], {kind: Counter() for kind in _FOUNDATION}
    for page, words in samples:
        marks = defaultdict(list)
        for word in words:
            marks[word['type_tag']].append(word)
        counts[page['sheet_kind']].update({tag: len(entries) for tag, entries in marks.items()})
        observed.append((page, marks))
    excavation, foundation = (counts[kind] for kind in _FOUNDATION)
    different = sorted(tag for tag in excavation.keys() | foundation.keys() if excavation[tag] != foundation[tag])
    if len(different) * len(observed) > _MAX_LOCAL_COMPARISONS:
        yield _review(_COUNT_ROLE, 'foundation', 'STRUCTURAL_PLAN_EVIDENCE_INCOMPLETE',
                      [_sheet_anchor(page) for page, _ in observed], blocked=True, occurrence_equivalence_verified=False)
        return
    for tag in different:
        phase_counts = {kind: counts[kind][tag] for kind in _FOUNDATION}
        anchors, sheet_counts = [], []
        for page, marks in observed:
            witnesses = marks.get(tag, ())
            anchors.extend(witnesses or [_sheet_anchor(page)])
            sheet_counts.append({'document_id': page['document_id'], 'source_name': page['source_name'],
                                 'source_sha256': page['sha256'], 'page': page['page'], 'sheet_kind': page['sheet_kind'],
                                 'count': len(witnesses)})
        yield _review(_COUNT_ROLE, 'foundation', 'FOUNDATION_PHASE_MARK_COUNT_MISMATCH', anchors,
                      type_tag=tag, blocked=True, sheet_mark_counts=sheet_counts, phase_mark_counts=phase_counts,
                      count_basis='ISOLATED_NATIVE_MARKS_ON_MARKED_PHASE_SHEETS', occurrence_equivalence_verified=False)


def build_pdf_structural_plan_reviews(pages):
    """Review source geometry and native words in explicitly scoped structural plans."""
    result = []
    phase_samples = defaultdict(list)
    for key, page in sorted(pages.items()):
        kind = page['sheet_kind']
        if kind != _BEAM and kind not in _FOUNDATION:
            continue
        if (key != (page['document_id'], page['page']) or not _box(page['source_bbox_pt'])
                or not re.fullmatch('[0-9a-f]{64}', page['sha256']) or not page['source_name']):
            raise ValueError('Invalid structural plan source identity or bounds')
        topology = page['raw']['detail_topology']
        if (topology.get('document_id'), topology.get('page')) != key:
            raise ValueError('Foreign structural plan topology')
        problem = _page_problem(page)
        words = _native_words(page)
        groups = [] if problem else topology['groups']
        if any((g.get('document_id'), g.get('page')) != key for g in groups):
            raise ValueError('Foreign structural plan geometry')
        regions = list(_closed_regions(page, groups))
        if kind in _FOUNDATION:
            marks = [word for word in words if _WORD_PREFIX['foundation'].fullmatch(word['type_tag'])]
            if marks:
                phase_samples[(page['document_id'], page['sha256'])].append((page, marks))
            result.extend(_foundation_marks(marks, regions, problem))
            continue
        if not problem:
            try:
                rows = list(_beam_regions(page, words, groups, regions))
            except _LocalSearchLimit:
                problem = 'STRUCTURAL_PLAN_EVIDENCE_INCOMPLETE'
            else:
                if rows:
                    result.extend(rows)
                    continue
        result.append(_review(_BEAM_ROLE, 'beam', problem or 'BEAM_NO_LOCALIZED_SPAN', [_sheet_anchor(page)],
                              blocked=bool(problem)))
    for samples in phase_samples.values():
        result.extend(_phase_discrepancies(samples))
    return result
