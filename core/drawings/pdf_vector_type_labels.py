"""Template-matched CAD type marks and provisional column grid attachments."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import floor, hypot, isfinite
from typing import Any, Iterable, Mapping

from .pdf_type_word_witness import unrotated_page_bounds

_MAX_PATHS = 25_000
_MAX_LABELS = 600
_MAX_ATTACH_PT = 55.0
_MAX_STROKE_OPERATORS = 200_000
_MAX_LOCAL_STROKES = 128
_MAX_LOCAL_COMPARISONS = 400_000
_MIN_GLYPH_HEIGHT = 3.5
_MAX_GLYPH_HEIGHT = 38.0
_CELL_PT = 12.0

# Generic dimensionless stroke-lettering patterns, NOT source-drawing geometry.
# Shape matching is required; two path objects merely being close is insufficient.
_C = ((1, .833), (.75, 1), (.25, 1), (0, .833), (0, .167),
      (.25, 0), (.75, 0), (1, .167))
_ONE = ((0, .167), (1, 0), (1, 1))
_TWO = ((0, .167), (.25, 0), (.75, 0), (1, .167), (1, .34),
        (.75, .5), (.25, .5), (0, .667), (0, 1), (1, 1))
_THREE_TOP = ((0, .167), (.25, 0), (.75, 0), (1, .167),
              (1, .333), (.75, .5), (.5, .5))
_THREE_BOTTOM = ((.75, .5), (1, .667), (1, .833),
                 (.75, 1), (.25, 1), (0, .833))
_B_TOP = ((0, .5), (0, 0), (.75, 0), (1, .125), (1, .375), (.75, .5), (0, .5))
_B_BOTTOM = ((0, .5), (.75, .5), (1, .625), (1, .875), (.75, 1), (0, 1), (0, .5))
_B_OUTLINE = ((0, 1), (0, 0), *_B_TOP[2:], (.75, .5), *_B_BOTTOM[2:-1])
_F_MAIN = ((0, 1), (0, 0), (1, 0))
_F_BAR = ((0, .47), (.8, .47))
_T_STEM = ((.5, 0), (.5, 1))
_T_BAR = ((0, 0), (1, 0))
_ONE_FLAG_AND_STEM = ((0, .167), (.5, 0), (.5, 1))
_ONE_FOOT = ((0, 1), (1, 1))

_SINGLE_GLYPHS = (
    ('C', .46, .92, _C),
    ('B', .46, .92, _B_TOP + _B_BOTTOM[1:]),
    ('B', .46, .92, _B_OUTLINE),
    ('1', .12, .36, _ONE),
    ('2', .45, .87, _TWO),
    ('3', .45, .88, _THREE_TOP + _THREE_BOTTOM),
)


@dataclass(frozen=True)
class _Stroke:
    path: int
    operators: tuple[int, ...]
    points: tuple[tuple[float, float], ...]
    box: tuple[float, float, float, float]

    @property
    def width(self):
        return self.box[2] - self.box[0]

    @property
    def height(self):
        return self.box[3] - self.box[1]


@dataclass(frozen=True)
class _Glyph:
    char: str
    strokes: tuple[_Stroke, ...]
    box: tuple[float, float, float, float]


class _StrokeWorkLimit(Exception):
    pass


def _point_box(points):
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _union_box(boxes):
    return _point_box(tuple(point for box in boxes for point in (box[:2], box[2:])))


def _glyph(char, *strokes):
    return _Glyph(char, strokes, _union_box(s.box for s in strokes))


class _Neighborhood:
    """Index by source box origin and count every examined neighbor."""

    def __init__(self):
        self.cells = defaultdict(list)
        self.axes = (defaultdict(list), defaultdict(list))
        self.comparisons = 0

    def check(self, bucket):
        self.comparisons += len(bucket)
        if self.comparisons > _MAX_LOCAL_COMPARISONS:
            raise _StrokeWorkLimit

    def add(self, obj):
        x, y = obj.box[:2]
        self.cells[floor(x / _CELL_PT), floor(y / _CELL_PT)].append(obj)

    def nearby(self, x0, y0, x1, y1):
        found = []
        for ix in range(floor(x0 / _CELL_PT), floor(x1 / _CELL_PT) + 1):
            for iy in range(floor(y0 / _CELL_PT), floor(y1 / _CELL_PT) + 1):
                bucket = self.cells.get((ix, iy), ())
                self.check(bucket)
                found.extend(obj for obj in bucket
                             if x0 <= obj.box[0] <= x1 and y0 <= obj.box[1] <= y1)
                if len(found) > _MAX_LOCAL_STROKES:
                    raise _StrokeWorkLimit
        return found

    def add_axis(self, a, b, ref):
        for fixed in (0, 1):
            if abs(a[fixed] - b[fixed]) > .03 or abs(a[1-fixed] - b[1-fixed]) < .18:
                continue
            at = (a[fixed] + b[fixed]) / 2
            limits = sorted((a[1-fixed], b[1-fixed]))
            self.axes[fixed][floor(at / _CELL_PT)].append((at, *limits, ref))

    def foreign_axes(self, glyph, owned):
        box = glyph.box
        tolerance = .045 * (box[3] - box[1])
        for fixed in (0, 1):
            low, high = box[fixed] - tolerance, box[fixed + 2] + tolerance
            for cell in range(floor(low / _CELL_PT), floor(high / _CELL_PT) + 1):
                bucket = self.axes[fixed].get(cell, ())
                self.check(bucket)
                for at, start, end, ref in bucket:
                    if ref in owned or not low <= at <= high:
                        continue
                    if any(_intersects_axis(a, b, fixed, at, start, end, tolerance)
                           for stroke in glyph.strokes
                           for a, b in zip(stroke.points, stroke.points[1:])):
                        yield ref


def _intersects_axis(a, b, fixed, at, start, end, tolerance):
    lo, hi = sorted((a[fixed], b[fixed]))
    if at < lo - tolerance or at > hi + tolerance:
        return False
    varying = 1 - fixed
    if hi - lo <= tolerance:
        return max(a[varying], b[varying]) >= start - tolerance and min(a[varying], b[varying]) <= end + tolerance
    fraction = max(0.0, min(1.0, (at - a[fixed]) / (b[fixed] - a[fixed])))
    crossing = a[varying] + fraction * (b[varying] - a[varying])
    return start - tolerance <= crossing <= end + tolerance


def _extract_strokes(paths, bounds, neighborhood):
    strokes = []
    for pi, path in enumerate(paths, 1):
        if path.get('type') not in ('s', 'fs') or path.get('stroke_opacity') == 0:
            continue
        items = path['items']
        eligible = (path.get('type') == 's' and path.get('dashes') in (None, '[] 0')
                    and all(item[0] == 'l' for item in items))
        run = []
        for oi, item in enumerate(items, 1):
            if item[0] == 're':
                x0, y0, x1, y1 = tuple(item[1])
                corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))
                for a, b in zip(corners, corners[1:]):
                    neighborhood.add_axis(a, b, (pi, oi))
            if item[0] != 'l':
                continue
            a, b = ((float(p.x), float(p.y)) for p in item[1:3])
            if not all(isfinite(v) for v in (*a, *b)):
                raise ValueError('Invalid source stroke coordinates')
            neighborhood.add_axis(a, b, (pi, oi))
            if not eligible:
                continue
            if run and hypot(run[-1][2][0] - a[0], run[-1][2][1] - a[1]) > .08:
                _add_stroke(strokes, pi, run, bounds, path.get('closePath'))
                run = []
            run.append((oi, a, b))
        if run:
            _add_stroke(strokes, pi, run, bounds, path.get('closePath'))
    return strokes


def _add_stroke(strokes, path, run, bounds, closed):
    if len(run) > 16:
        return
    points = (run[0][1], *(part[2] for part in run))
    if closed and hypot(points[0][0] - points[-1][0], points[0][1] - points[-1][1]) > .08:
        return
    box = _point_box(points)
    if (box[2] - box[0] > _MAX_GLYPH_HEIGHT or box[3] - box[1] > _MAX_GLYPH_HEIGHT
            or any(box[i] < bounds[i] - .12 for i in (0, 1))
            or any(box[i] > bounds[i] + .12 for i in (2, 3))):
        return
    strokes.append(_Stroke(path, tuple(part[0] for part in run), points, box))


def _matches_template(points, expected, box, *, tolerance=.105):
    if len(points) != len(expected):
        return False
    x, y, right, bottom = box
    w, h = right - x, bottom - y
    if w <= .01 or h <= .01:
        return False
    points = tuple(((px - x) / w, (py - y) / h) for px, py in points)
    return any(all(hypot(px - ex, py - ey) < tolerance for (px, py), (ex, ey) in zip(pts, expected))
               for pts in (points, points[::-1]))


def _parts_glyphs(stroke, neighborhood):
    x, y, right, bottom = stroke.box
    h, w = stroke.height, stroke.width
    if h <= 0:
        return
    if .9 <= w / h <= 1.85:
        for char, upper, lower in (('B', _B_TOP, _B_BOTTOM), ('3', _THREE_TOP, _THREE_BOTTOM)):
            estimated = (x, y, right, y + 2 * h)
            if not _matches_template(stroke.points, upper, estimated):
                continue
            for part in neighborhood.nearby(x - .16 * w, bottom - .12 * h, x + .85 * w, bottom + .12 * h):
                box = _union_box((stroke.box, part.box))
                total_height = box[3] - box[1]
                if (_MIN_GLYPH_HEIGHT <= total_height <= _MAX_GLYPH_HEIGHT
                        and .45 <= (box[2] - box[0]) / total_height <= .92
                        and _matches_template(stroke.points, upper, box)
                        and _matches_template(part.points, lower, box)):
                    yield _glyph(char, stroke, part)
    if not _MIN_GLYPH_HEIGHT <= h <= _MAX_GLYPH_HEIGHT:
        return
    if .45 <= w / h <= .94 and _matches_template(stroke.points, _F_MAIN, stroke.box):
        for bar in neighborhood.nearby(x - .04 * h, y + .39 * h, x + .04 * h, y + .55 * h):
            if _matches_template(bar.points, _F_BAR, stroke.box):
                yield _glyph('F', stroke, bar)
    if len(stroke.points) == 2 and w <= .055 * h:
        for bar in neighborhood.nearby(x - .54 * h, y - .038 * h, x - .17 * h, y + .038 * h):
            frame = _union_box((stroke.box, bar.box))
            if (.44 <= bar.width / h <= .92 and bar.height <= .035 * h
                    and _matches_template(stroke.points, _T_STEM, frame)
                    and _matches_template(bar.points, _T_BAR, frame)):
                yield _glyph('T', stroke, bar)


def _ones(stroke, neighborhood):
    x, _, _, bottom = stroke.box
    w, h = stroke.width, stroke.height
    feet = [bar for bar in neighborhood.nearby(x - .34 * w, bottom - .04 * h,
                                               x + .34 * w, bottom + .04 * h)
            if 1.5 * w <= bar.width <= 2.5 * w and bar.height <= .035 * h]
    alternate = []
    for bar in feet:
        box = _union_box((stroke.box, bar.box))
        if (_matches_template(stroke.points, _ONE_FLAG_AND_STEM, box)
                and _matches_template(bar.points, _ONE_FOOT, box)):
            alternate.append(_glyph('1', stroke, bar))
    return alternate or [_glyph('1', stroke)]


def _classify_glyphs(strokes, neighborhood):
    found = []
    for stroke in strokes:
        h, w = stroke.height, stroke.width
        if _MIN_GLYPH_HEIGHT <= h <= _MAX_GLYPH_HEIGHT:
            for char, lo, hi, template in _SINGLE_GLYPHS:
                if lo <= w / h <= hi and _matches_template(stroke.points, template, stroke.box):
                    found.extend(_ones(stroke, neighborhood) if char == '1' else [_glyph(char, stroke)])
            if len(stroke.points) == 2 and w <= .075 * h:
                found.append(_glyph('upright', stroke))
        if len(stroke.points) == 2 and .55 <= w <= .66 * _MAX_GLYPH_HEIGHT and h <= w * .075:
            found.append(_glyph('-', stroke))
        found.extend(_parts_glyphs(stroke, neighborhood))
    return found


def _refs(glyphs):
    return {(s.path, op) for g in glyphs for s in g.strokes for op in s.operators}


def _glyph_anchor(glyph):
    primary = glyph.strokes[0]
    return primary.path, primary.operators[0]


def _mark_options(letter, glyph_index):
    x, y, right, bottom = letter.box
    h = bottom - y
    pad = max(.36, .092 * h)
    aligned = glyph_index.nearby(right + .055 * h, y - pad, right + 1.65 * h, y + pad)
    digits = [g for g in aligned if g.char in ('1', '2', '3', 'upright')
              and abs(g.box[3] - bottom) <= pad]
    options = []
    if letter.char in ('B', 'C'):
        options.extend((letter, g) for g in digits if g.box[0] - right <= .66 * h)
    for dash in glyph_index.nearby(right + .055 * h, y + .32 * h, right + .60 * h, y + .62 * h):
        if dash.char != '-' or not .14 * h <= dash.box[2] - dash.box[0] <= .62 * h:
            continue
        glyph_index.check(digits)
        options.extend((letter, dash, g) for g in digits
                       if .055 * h <= g.box[0] - dash.box[2] <= .60 * h)
        if len(options) > _MAX_LOCAL_STROKES:
            raise _StrokeWorkLimit
    return options


def _adjacent_stroke(reading, stroke_index):
    """Conservatively withhold a substring of longer or unsupported lettering."""
    x, y, right, bottom = _union_box(glyph.box for glyph in reading)
    h = bottom - y
    pad, gap = .10 * h, .43 * h
    preceding = [stroke for stroke in stroke_index.nearby(x - 1.4 * h, y - pad, x - .035 * h, y + pad)
                 if .035 * h <= x - stroke.box[2] <= gap]
    following = stroke_index.nearby(right + .035 * h, y - pad, right + gap, y + pad)
    for stroke in (*preceding, *following):
        if (abs(stroke.box[3] - bottom) <= pad
                and (stroke.width <= .07 * h or .12 * h <= stroke.width <= .94 * h)):
            return {(stroke.path, op) for op in stroke.operators}
    return set()


def _record_stroke_mark(glyphs, *, document_id, page_number, reason=None, extra=()):
    bounds = _union_box(g.box for g in glyphs)
    refs = sorted(_refs(glyphs) | set(extra))
    pi, oi = _glyph_anchor(glyphs[0])
    ref = f'{document_id}:p{page_number}'
    token = ''.join(g.char for g in glyphs) if reason is None else None
    return {'witness_id': f'{ref}:stroke{pi}.{oi}', 'document_id': document_id, 'page': page_number,
            'type_tag': token.replace('-', '') if token is not None else None,
            'text': token, 'source_token': token,
            'status': ('ISOLATED_TYPE_WORD_POSITION_CANDIDATE' if reason is None else
                       'UNRESOLVED_VECTOR_STROKE_MARK'),
            'reason': reason, 'title_anchor_ids': [],
            'bbox_pt': [round(v, 3) for v in bounds],
            'source_class': 'VECTOR_STROKE_LABEL', 'localization': 'TEMPLATE_MATCHED_PDF_STROKE_BBOX',
            'source_path_indices': sorted({p for p, _ in refs}),
            'source_operator_ids': [f'{ref}:d{p}:s{o}' for p, o in refs],
            'physical_member_verified': False, 'quantity_approved': False, 'financially_payable': False}


def recover_page_vector_type_words(page, *, document_id, page_number, paths=None):
    """Index isolated horizontal CAD stroke-font marks in native PDF points.

    The page rotation metadata leaves extracted path coordinates unchanged.
    Unsupported or competing numeral geometry remains unresolved with its source
    operators. The result is position evidence for the supported alphabet.
    """
    if not isinstance(document_id, str) or not document_id.strip() or type(page_number) is not int or page_number < 1:
        raise ValueError('Stable PDF document and page required')
    result = {'document_id': document_id, 'page': page_number, 'coordinate_space': 'UNROTATED_PDF_PAGE_POINTS',
              'supported_type_prefixes': ['B', 'C', 'F', 'T'], 'supported_single_digit_suffixes': ['1', '2', '3'],
              'status': 'VECTOR_STROKE_WORDS_INDEXED', 'source_path_count': None, 'source_operator_count': None,
              'all_vector_strokes_examined': False, 'type_word_witnesses': [], 'rejections': [],
              'type_word_witness_count': 0, 'physical_member_count': None, 'quantity_approval_count': 0,
              'financially_payable': False}
    try:
        drawings = page.get_drawings() if paths is None else paths
        result['source_path_count'] = len(drawings)
        if len(drawings) > _MAX_PATHS:
            return {**result, 'status': 'BLOCKED_VECTOR_STROKE_PATH_BUDGET'}
        result['source_operator_count'] = sum(len(path['items']) for path in drawings)
        if result['source_operator_count'] > _MAX_STROKE_OPERATORS:
            return {**result, 'status': 'BLOCKED_VECTOR_STROKE_OPERATOR_BUDGET'}
        bounds = tuple(unrotated_page_bounds(page))
        if len(bounds) != 4 or not all(isfinite(v) for v in bounds) or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
            raise ValueError('Invalid PDF page extent')
        stroke_index = _Neighborhood()
        strokes = _extract_strokes(drawings, bounds, stroke_index)
        for stroke in strokes:
            stroke_index.add(stroke)
        glyphs = _classify_glyphs(strokes, stroke_index)
        glyph_index = _Neighborhood()
        for glyph in glyphs:
            glyph_index.add(glyph)
        prefixes = defaultdict(list)
        for glyph in glyphs:
            if glyph.char in ('C', 'B', 'F', 'T'):
                prefixes[_glyph_anchor(glyph)].append(glyph)
        if sum(map(len, prefixes.values())) > _MAX_LABELS:
            return {**result, 'status': 'BLOCKED_VECTOR_STROKE_LABEL_BUDGET'}
        options = [[word for glyph in variants for word in _mark_options(glyph, glyph_index)]
                   for variants in prefixes.values()]
        owners = Counter(ref for readings in options for ref in _refs(g for word in readings for g in word))
        witnesses, rejections = [], []
        for variants, readings in zip(prefixes.values(), options):
            letter = variants[0]
            if not readings:
                if letter.char in ('B', 'C'):
                    rejections.append(_record_stroke_mark((letter,), document_id=document_id,
                                                          page_number=page_number, reason='NO_SUPPORTED_NUMERAL',
                                                          extra=_refs(variants)))
                continue
            reading = readings[0]
            refs = _refs(g for word in readings for g in word) | _refs(variants)
            reason = None
            if len(variants) > 1:
                reason = 'MULTIPLE_GLYPH_INTERPRETATIONS'
            elif len(readings) > 1:
                reason = 'MULTIPLE_NUMERAL_INTERPRETATIONS'
            elif any(owners[ref] > 1 for ref in refs):
                reason = 'AMBIGUOUS_GLYPH_OWNERSHIP'
            elif reading[-1].char == 'upright':
                reason = 'AMBIGUOUS_UPRIGHT'
                axes = set(stroke_index.foreign_axes(reading[-1], refs))
                if len(axes) > _MAX_LOCAL_STROKES:
                    raise _StrokeWorkLimit
                refs.update(axes)
            else:
                for glyph in reading:
                    extra = next(stroke_index.foreign_axes(glyph, refs), None)
                    if extra is not None:
                        reason = 'UNEXPECTED_GLYPH_STROKE'
                        refs.add(extra)
                        break
                if reason is None and (adjacent := _adjacent_stroke(reading, stroke_index)):
                    reason = 'POSSIBLE_ADJACENT_GLYPH'
                    refs.update(adjacent)
            record = _record_stroke_mark(reading, document_id=document_id, page_number=page_number,
                                         reason=reason, extra=refs)
            (witnesses if reason is None else rejections).append(record)
    except _StrokeWorkLimit:
        return {**result, 'status': 'BLOCKED_VECTOR_STROKE_LOCAL_BUDGET'}
    except (AttributeError, IndexError, KeyError, MemoryError, OverflowError, RuntimeError, TypeError, ValueError):
        return {**result, 'status': 'BLOCKED_VECTOR_STROKE_EXTRACTION'}
    return {**result, 'all_vector_strokes_examined': True, 'type_word_witnesses': witnesses,
            'rejections': rejections, 'type_word_witness_count': len(witnesses)}


def _points(path: Mapping) -> tuple[tuple[float, float], ...]:
    items = path.get('items') or ()
    if not items or path.get('type') != 's' or any(i[0] != 'l' for i in items):
        return ()
    points = [(float(items[0][1].x), float(items[0][1].y))]
    for item in items:
        start, end = item[1:3]
        if not all(isfinite(float(v)) for v in (start.x, start.y, end.x, end.y)):
            return ()
        if hypot(points[-1][0] - start.x, points[-1][1] - start.y) > .3:
            return ()
        points.append((float(end.x), float(end.y)))
    return tuple(points)


def _shape(path: Mapping, expected: tuple[tuple[float, float], ...],
           *, tolerance: float = .105) -> bool:
    points = _points(path)
    if len(points) != len(expected):
        return False
    r = path['rect']
    w, h = float(r.width), float(r.height)
    if not (w > .7 and h >= 3.5 and all(isfinite(v) for v in (w, h))):
        return False
    return _matches_template(points, expected, (r.x0, r.y0, r.x1, r.y1), tolerance=tolerance)


def _same_line_bbox(a, b, *, horizontal=0.50, vertical=0.55) -> bool:
    return (abs(a.x0-b.x0) < horizontal and abs(a.x1-b.x1) < horizontal and
            abs(a.y1-b.y0) < vertical)


def _looks_like_c(path) -> bool:
    r=path['rect']
    return (5.0 <= r.width <= 10.8 and 7.0 <= r.height <= 16.0 and
            .50 <= r.width / r.height <= .86 and _shape(path, _C))


def _digit_for_c(cpath, drawn: list[Mapping]) -> tuple[str, tuple[int, ...]] | None:
    cr = cpath['rect']
    neighboring=[]
    for idx, path in enumerate(drawn):
        r=path['rect']
        if (1.0 <= r.x0-cr.x1 <= 6.2 and abs(r.y0-cr.y0) < .75 and
                0.5 <= r.width <= 10 and 3.5 <= r.height <= 16 and
                abs(r.y1-cr.y1) < .75):
            if _shape(path, _ONE) and r.width/r.height < .35:
                neighboring.append(('1', (idx,)))
            if _shape(path, _TWO) and .45 <= r.width/r.height <= .83:
                neighboring.append(('2', (idx,)))
    # A CAD stroke '3' consists of two distinct vertical half-characters.
    for top_idx, top in enumerate(drawn):
        r=top['rect']
        if not (1.0 <= r.x0-cr.x1 <= 6.2 and abs(r.y0-cr.y0)<.75 and
                0.35*cr.height < r.height < 0.7*cr.height):
            continue
        for lower_idx, bottom in enumerate(drawn):
            rb=bottom['rect']
            if (lower_idx != top_idx and
                    abs(rb.y1-cr.y1) < .75 and _same_line_bbox(r, rb) and
                    _paired_three_shapes(top, bottom, cr)):
                neighboring.append(('3', (top_idx,lower_idx)))
    # Uniqueness is a hard gate. Ambiguous patterns are never resolved by guess.
    return neighboring[0] if len(neighboring) == 1 else None


def _paired_three_shapes(top, bottom, c_rect) -> bool:
    """Test a two-path glyph as one normalized '3' of the C glyph height."""
    a,b=_points(top),_points(bottom)
    if len(a)!=len(_THREE_TOP) or len(b)!=len(_THREE_BOTTOM):
        return False
    ra=top['rect'];rb=bottom['rect']
    w=ra.width; h=c_rect.height
    if not (.48 <= w/h <= .82 and 7.0 <= h <= 16.0):
        return False
    box = (ra.x0, ra.y0, ra.x1, ra.y0 + h)
    return _matches_template(a, _THREE_TOP, box) and _matches_template(b, _THREE_BOTTOM, box)


def vector_column_type_labels(page, nodes: Iterable[Mapping[str, Any]], *,
                              max_attach_pt: float=_MAX_ATTACH_PT) -> dict:
    """Read glyph shape, then attach only uniquely nearest labeled grid node.

    All node coordinates are PDF page points. Candidate attachments do not
    approve a member, and no output is a payable takeoff quantity.
    """
    nodes=list(nodes)
    if not (0 < max_attach_pt <= _MAX_ATTACH_PT):
        raise ValueError('attachment radius exceeds validated bound')
    if not nodes:
        return {'nodes': [], 'labels': [], 'attached': 0,
                'physical_member_count': None, 'complete': False}
    if len(nodes) > 2000:
        raise ValueError('unbounded grid node list')
    if not any(n.get('column_context_candidate') for n in nodes):
        return {'nodes': [dict(n) for n in nodes], 'labels': [], 'attached': 0,
                'physical_member_count': None, 'complete': False}
    drawn=page.get_drawings()
    if len(drawn)>_MAX_PATHS:
        raise ValueError('vector path budget exceeded')
    labels=[]
    for idx,path in enumerate(drawn):
        if not _looks_like_c(path):
            continue
        recognized=_digit_for_c(path,drawn)
        if recognized is None:
            continue
        digit, indices=recognized
        cr=path['rect']; final=drawn[indices[0]]['rect']
        tag='C'+digit
        labels.append({'tag':tag,'bbox_pt':tuple(round(float(x),3) for x in
                        (cr.x0,cr.y0,drawn[indices[-1]]['rect'].x1,
                         max(cr.y1,drawn[indices[-1]]['rect'].y1))),
                       'path_indices':(idx,)+indices,
                       'source_class':'VECTOR_STROKE_LABEL',
                       'status':'PROPOSED_UNVERIFIED'})
        if len(labels)>_MAX_LABELS:
            raise ValueError('vector label budget exceeded')
    # Exclusivity: one glyph label cannot be the evidence for several nodes.
    assignments={}
    for li,label in enumerate(labels):
        x0,y0,x1,y1=label['bbox_pt']; lx=(x0+x1)/2; ly=(y0+y1)/2
        distances=[]
        for ni,node in enumerate(nodes):
            if not node.get('column_context_candidate'):
                continue
            dx=lx-float(node['x_pt']);dy=ly-float(node['y_pt'])
            if all(isfinite(v) for v in (dx,dy)):
                distances.append((hypot(dx,dy),ni))
        distances.sort()
        if not distances or distances[0][0]>max_attach_pt:
            continue
        if len(distances)>1 and distances[1][0]-distances[0][0]<12.0:
            continue
        ni=distances[0][1]
        assignments.setdefault(ni,[]).append((li,distances[0][0]))
    result=[]; valid=0
    for ni,node in enumerate(nodes):
        copy=dict(node)
        selected=assignments.get(ni,[])
        tags={labels[li]['tag'] for li,_ in selected}
        if len(selected)==1:
            li,distance=selected[0]
            copy.update({'suggested_type':labels[li]['tag'],
                         'status':'GRID_LOCATION_VECTOR_TYPE_CANDIDATE',
                         'vector_type_label_evidence':{**labels[li],
                                                      'distance_pt':round(distance,3)}})
            valid+=1
        elif selected:
            copy.update({'suggested_type':None,
                         'status':'BLOCKED_MULTIPLE_VECTOR_TYPE_LABELS',
                         'vector_type_label_evidence':[labels[li] for li,_ in selected]})
        copy.update({'type_verified':False,'physical_member_verified':False,
                     'quantity_approved':False,'financially_payable':False})
        result.append(copy)
    return {'nodes':result, 'labels':labels,'attached':valid,
            'physical_member_count':None, 'complete':False}
