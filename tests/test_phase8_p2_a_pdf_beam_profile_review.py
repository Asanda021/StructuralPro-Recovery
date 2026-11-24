import copy
import pytest
from core.drawings.pdf_beam_profile_review import correlate_pdf_beam_profile_witnesses


def sample():
    digest = 'a' * 64
    page = {'document_id': 'PDF001', 'page': 15, 'source_name': 'naghshe.pdf',
            'sha256': digest, 'sheet_kind': 'beam_layout_plan', 'linkable': True,
            'authority_block': None, 'source_bbox_pt': [0, 0, 700, 600]}
    row = {'review_id': 'BEAM1', 'role': 'BEAM_LAYOUT_REGION_REVIEW',
           'financially_payable': False, 'anchors': [
               {'document_id': 'PDF001', 'page': 15, 'source_sha256': digest,
                'kind': 'VECTOR_PARALLEL_REVIEW_REGION',
                'anchor_id': 'R1', 'bbox_pt': [185, 151, 255, 154]}]}
    observation = {'document': 'naghshe.pdf', 'page': 15, 'source_sha256': digest,
                   'bbox_pt': [200, 155, 252, 195],
                   'source_method': 'VISUAL_CAD_STROKES_PRIVATE_RENDER',
                   'printed_axis_row': '3', 'span_axes': 'A-B', 'circled_mark_raw': '1',
                   'profile_text_raw': '2IPE16', 'profile_text_normalized': '2IPE16',
                   'source_visual_confidence': 'VISIBLE', 'financially_payable': False}
    return {('PDF001', 15): page}, [row], observation


def test_one_near_beam_span_is_still_nonpayable_and_unverified():
    pages, lanes, seen = sample()
    row, = correlate_pdf_beam_profile_witnesses(pages, lanes, [seen])
    assert row['candidate_region_count'] == 1 and row['candidate_review_ids'] == ['BEAM1']
    assert row['reason_code'] == 'BEAM_PROFILE_PROXIMITY_ONLY'
    assert row['status'] == 'REVIEW_REQUIRED'
    assert row['member_quantity'] is None and row['financially_payable'] is False
    assert row['physical_member_verified'] is False


def test_multiple_near_lanes_and_ambiguous_visual_cannot_select_a_member():
    pages, lanes, seen = sample()
    neighbor = copy.deepcopy(lanes[0])
    neighbor['review_id'] = 'BEAM2'
    neighbor['anchors'][0]['anchor_id'] = 'R2'
    neighbor['anchors'][0]['bbox_pt'] = [185, 151, 255, 157]
    result, = correlate_pdf_beam_profile_witnesses(pages, lanes + [neighbor], [seen])
    assert result['candidate_region_count'] == 2 and result['status'] == 'BLOCKED'
    assert result['reason_code'] == 'BEAM_PROFILE_AMBIGUOUS_ENVELOPE'
    seen['source_visual_confidence'] = 'REVIEW_REQUIRED'
    result, = correlate_pdf_beam_profile_witnesses(pages, lanes, [seen])
    assert result['status'] == 'BLOCKED'


@pytest.mark.parametrize('field,value', [
    ('source_sha256', 'b'*64), ('page', 14),
    ('profile_text_normalized', 'IPE16'), ('profile_text_raw', '2CIPE 16'),
    ('verified_length_m', 3.5), ('financially_payable', True),
    ('bbox_pt', [-10, 150, 250, 200]), ('source_method', 'OCR_HALLUCINATION'),
])
def test_reject_unsafe_visual_evidence(field, value):
    pages, lanes, seen = sample()
    seen[field] = value
    with pytest.raises(ValueError):
        correlate_pdf_beam_profile_witnesses(pages, lanes, [seen])


def test_reject_duplicate_and_shared_spatial_beam_envelope():
    pages, lanes, seen = sample()
    with pytest.raises(ValueError, match='Duplicate'):
        correlate_pdf_beam_profile_witnesses(pages, lanes, [seen, copy.deepcopy(seen)])
    other = copy.deepcopy(seen)
    other['bbox_pt'] = [201, 156, 250, 194]
    rows = correlate_pdf_beam_profile_witnesses(pages, lanes, [seen, other])
    assert len(rows) == 2
    assert all(row['status'] == 'BLOCKED' and row['reason_code'] == 'BEAM_PROFILE_SHARED_ENVELOPE'
               for row in rows)


def test_missing_or_vertical_region_not_promoted():
    pages, lanes, seen = sample()
    lanes[0]['anchors'][0]['bbox_pt'] = [185, 151, 190, 290]
    result, = correlate_pdf_beam_profile_witnesses(pages, lanes, [seen])
    assert result['candidate_region_count'] == 0
    assert result['reason_code'] == 'BEAM_PROFILE_NO_ENVELOPE'
    pages[('PDF001', 15)]['authority_block'] = 'CONFLICT'
    with pytest.raises(ValueError):
        correlate_pdf_beam_profile_witnesses(pages, lanes, [seen])
