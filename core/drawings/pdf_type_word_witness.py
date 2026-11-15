"""Audit-only PDF type-mark word positions with original page coordinates.

Word bounding boxes are NOT individual glyph geometry, physical member
identity, semantic detail limits or accepted BOQ measurements. Title text
mentions stay separate from isolated drawing labels.
"""
from __future__ import annotations

from math import isfinite
import re

TYPE_MARK = re.compile(r'^(SC|SW|C|B|F|T|W|S|P)[-–]?([1-9][0-9]{0,2})$', re.I)


def unrotated_page_bounds(page):
    """Return the extent in the same coordinates as extracted words and paths."""
    extent = page.rect
    if getattr(page, "rotation", 0):
        extent = extent * page.derotation_matrix
    return extent


def _box(value):
    try:
        nums = tuple(float(value[i]) for i in range(4))
    except (TypeError, IndexError, ValueError, KeyError):
        return None
    if len(nums) != 4 or not all(isfinite(x) for x in nums):
        return None
    return nums if nums[0] < nums[2] and nums[1] < nums[3] else None


def _overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def index_pdf_type_words(page, *, document_id: str, page_number: int,
                         title_anchors, max_words: int = 30000):
    """Retain every isolated/title word candidate; block failed extraction.

    A token such as 'C' followed by a separate token '2' is deliberately NOT
    reconstructed without independent layout proof. Every witness has a stable
    1-based source word index within the original PDF extraction order.
    """
    if not isinstance(document_id, str) or not document_id.strip() or type(page_number) is not int or page_number < 1:
        raise ValueError('Stable PDF document and page required')
    if type(max_words) is not int or not 1 <= max_words <= 100000:
        raise ValueError('Bounded PDF word budget required')
    page_box = _box(unrotated_page_bounds(page))
    if page_box is None:
        raise ValueError('Invalid PDF page extent')
    anchors = {}
    for item in title_anchors:
        aid = item.get('anchor_id')
        if (not isinstance(aid, str) or not aid or aid in anchors or
                item.get('document_id') != document_id or item.get('page') != page_number):
            raise ValueError('Invalid or foreign detail-title word witness source')
        box = _box(item.get('bbox_pt'))
        if box is None:
            raise ValueError('Invalid title bounding box')
        anchors[aid] = box

    def blocked(reason, count=None):
        return {'document_id': document_id, 'page': page_number,
                'status': reason, 'source_word_count': count,
                'type_word_witnesses': [], 'type_word_witness_count': 0,
                'all_words_examined': False,
                'financially_payable': False}
    try:
        words = list(page.get_text('words'))
    except (RuntimeError, ValueError, TypeError, MemoryError):
        return blocked('BLOCKED_TYPE_WORD_EXTRACTION')
    if len(words) > max_words:
        return blocked('BLOCKED_EXCESSIVE_TYPE_WORDS', len(words))

    witnesses = []
    for index, word in enumerate(words, 1):
        if not isinstance(word, (tuple, list)) or len(word) < 5:
            return blocked('BLOCKED_INVALID_TYPE_WORD_RECORD', len(words))
        raw = str(word[4]).strip()
        match = TYPE_MARK.fullmatch(raw)
        if match is None:
            continue
        box = _box(word)
        if box is None or any((box[i] < page_box[i] - 1 if i < 2 else
                              box[i] > page_box[i] + 1) for i in range(4)):
            return blocked('BLOCKED_TYPE_WORD_OUTSIDE_PAGE', len(words))
        tag = match.group(1).upper() + str(int(match.group(2)))
        in_titles = sorted(aid for aid, title_box in anchors.items() if _overlap(box, title_box))
        witnesses.append({
            'witness_id': f'{document_id}:p{page_number}:word{index:06d}',
            'document_id': document_id, 'page': page_number,
            'source_word_index': index, 'source_token': raw,
            'type_tag': tag,
            'bbox_pt': [round(n, 3) for n in box],
            'title_anchor_ids': in_titles,
            'status': ('TITLE_TEXT_MENTION_NOT_MEMBER' if in_titles else
                       'ISOLATED_TYPE_WORD_POSITION_CANDIDATE'),
            'localization': 'PDF_WORD_BBOX_NOT_GLYPH_OR_MEMBER',
            'physical_member_verified': False,
            'quantity_approved': False,
            'financially_payable': False,
        })
    return {'document_id': document_id, 'page': page_number,
            'status': 'INDEXED_TYPE_WORD_POSITIONS',
            'source_word_count': len(words),
            'type_word_witnesses': witnesses,
            'type_word_witness_count': len(witnesses),
            'all_words_examined': True, 'financially_payable': False}
