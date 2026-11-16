"""Read-only spatial pairing of visual beam profile labels and CAD stroke envelopes.

Never infer beam members, installed lengths, units, BOQ or payment from such a
pair. The input is a locally reviewed JSON array, not a trusted drawing.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import re
from core.drawings.pdf_type_word_witness import _box


def load_pdf_beam_profile_witnesses(path):
    records = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(records, list):
        raise ValueError('Expected JSON array of beam-profile visual observations')
    return records


def _uid(*items):
    source = json.dumps(items, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return 'BEAM_PROFILE_REVIEW:' + sha256(source.encode('utf-8')).hexdigest()[:32]


def _inside(outer, inner):
    return all(outer[k] <= inner[k] and inner[k+2] <= outer[k+2] for k in (0, 1))


def correlate_pdf_beam_profile_witnesses(pages, plan_reviews, observations):
    """Correlate labeled crops and parallel envelopes only by bounded proximity."""
    if observations is None:
        return []
    if not isinstance(observations, (list, tuple)) or len(observations) > 256:
        raise ValueError('Beam-profile observations exceed the permitted scope')
    lanes = {}
    for row in plan_reviews:
        anchors = row.get('anchors') or ()
        if row.get('role') != 'BEAM_LAYOUT_REGION_REVIEW' or not anchors:
            continue
        first = anchors[0]
        if first.get('kind') != 'VECTOR_PARALLEL_REVIEW_REGION':
            continue
        key = (first.get('document_id'), first.get('page'))
        page = pages.get(key)
        if not page or first.get('source_sha256') != page['sha256'] or not _box(first.get('bbox_pt')):
            raise ValueError('Foreign vector source in beam-profile review')
        lanes.setdefault(key, []).append(row)
    seen, results = set(), []
    for index, item in enumerate(observations, 1):
        if not isinstance(item, dict):
            raise ValueError('Invalid manual beam-profile record')
        digest, number, name = item.get('source_sha256'), item.get('page'), item.get('document')
        if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                or type(number) is not int or number < 1 or not isinstance(name, str)):
            raise ValueError('Unbound beam profile source')
        matching = [p for p in pages.values() if (p['sha256'], p['page'], p['source_name']) == (digest, number, name)]
        if len(matching) != 1:
            raise ValueError('Missing or ambiguous original PDF for beam-profile observation')
        page = matching[0]
        box = _box(item.get('bbox_pt'))
        if (page['sheet_kind'] != 'beam_layout_plan' or page['authority_block']
                or not page['linkable'] or not box or not _inside(page['source_bbox_pt'], box)):
            raise ValueError('Invalid source page, authority or visual crop')
        raw, label = item.get('profile_text_raw'), item.get('profile_text_normalized')
        if (not isinstance(raw, str) or not isinstance(label, str)
                or re.sub(r'\s+', '', raw.upper()) != label
                or not re.fullmatch(r'[1-4]C?IPE[0-9]{1,3}', label)
                or item.get('financially_payable') is not False
                or item.get('source_method') != 'VISUAL_CAD_STROKES_PRIVATE_RENDER'
                or item.get('source_visual_confidence') not in ('VISIBLE', 'REVIEW_REQUIRED')
                or not isinstance(item.get('span_axes'), str)
                or not re.fullmatch('[A-Z]-[A-Z]', item['span_axes'])
                or not isinstance(item.get('printed_axis_row'), str)
                or not re.fullmatch('[1-9][0-9]{0,2}', item['printed_axis_row'])
                or not isinstance(item.get('circled_mark_raw'), str)
                or not re.fullmatch('[1-9][0-9]{0,2}', item['circled_mark_raw'])
                or any(item.get(k) is not None for k in (
                    'incident_profile_member_id', 'governing_detail_id', 'verified_level',
                    'verified_length_m', 'verified_cut_quantity'))):
            raise ValueError('Untrusted or promoted visual beam-profile observation')
        identity = (digest, number, tuple(round(v, 3) for v in box),
                    item['printed_axis_row'], item['span_axes'])
        if identity in seen:
            raise ValueError('Duplicate visual beam-profile observation')
        seen.add(identity)
        center_x = (box[0] + box[2]) / 2
        source_bounds = page['source_bbox_pt']
        short = min(source_bounds[2]-source_bounds[0], source_bounds[3]-source_bounds[1])
        candidates = []
        for row in lanes.get((page['document_id'], number), ()):
            b = row['anchors'][0]['bbox_pt']
            gap = max(0, b[1] - box[3], box[1] - b[3])
            if b[2]-b[0] >= 4*(b[3]-b[1]) and b[0]-1 <= center_x <= b[2]+1 and gap <= .09*short:
                candidates.append(row)
        candidates.sort(key=lambda x: x['review_id'])
        uncertain = len(candidates) != 1 or item['source_visual_confidence'] != 'VISIBLE'
        code = ('BEAM_PROFILE_NO_ENVELOPE' if not candidates else
                'BEAM_PROFILE_AMBIGUOUS_ENVELOPE' if uncertain else 'BEAM_PROFILE_PROXIMITY_ONLY')
        anchor = {
            'anchor_id': _uid(digest, identity), 'kind': 'VISUALLY_READ_BEAM_PROFILE',
            'document_id': page['document_id'], 'page': number, 'source_name': name,
            'source_sha256': digest, 'bbox_pt': list(box),
            'coordinate_space': 'unrotated_pdf_points',
            'source_ref': f'{name}:p{number}:private_visual_{index:04d}',
            'source_method': item['source_method'], 'raw_token': raw,
        }
        candidate_ids = [row['review_id'] for row in candidates]
        results.append({
            'review_id': _uid(anchor['anchor_id'], candidate_ids),
            'role': 'BEAM_PROFILE_SPATIAL_REVIEW', 'family': 'beam',
            'status': 'BLOCKED' if uncertain else 'REVIEW_REQUIRED',
            'reason_code': code, 'profile_text': label, 'type_tag': None,
            'printed_axis_row': item['printed_axis_row'], 'span_axes': item['span_axes'],
            'circled_mark_raw': item['circled_mark_raw'],
            'candidate_region_count': len(candidates), 'candidate_review_ids': candidate_ids,
            'anchors': [anchor, *(row['anchors'][0] for row in candidates)],
            'missing_evidence': ['نسخهٔ حاکم و ارجاع قطعی به دهانه', 'آکس و تکیه‌گاه‌های دو سر دهانه',
                                 'تراز نصب، مشخصات پروفیل و اتصالات', 'طول برش با واحد و کسورات و تکرار طبقه'],
            'physical_member_verified': False, 'member_quantity': None,
            'quantity_approved': False, 'financially_payable': False,
        })
    uses = {}
    for row in results:
        for candidate in row['candidate_review_ids']:
            uses[candidate] = uses.get(candidate, 0) + 1
    for row in results:
        if any(uses[candidate] > 1 for candidate in row['candidate_review_ids']):
            row['status'] = 'BLOCKED'
            row['reason_code'] = 'BEAM_PROFILE_SHARED_ENVELOPE'
    return results
