from collections import Counter

import pymupdf

from core.drawings import pdf_structural_plan_review as review
from core.drawings.pdf_detail_topology import scan_detail_topology
from core.drawings.pdf_type_word_witness import index_pdf_type_words


def _record(page, sheet_kind, *, doc_id='EXAMPLE', digest='a' * 64, authority_block=None, linkable=True):
    number = page.number + 1
    topology = scan_detail_topology(page, document_id=doc_id, page_number=number)
    words = index_pdf_type_words(page, document_id=doc_id, page_number=number, title_anchors=[])
    return {'document_id': doc_id, 'page': number, 'source_name': 'example.pdf', 'sha256': digest,
            'source_bbox_pt': topology['page_bbox_pt'], 'sheet_kind': sheet_kind,
            'linkable': linkable, 'authority_block': authority_block,
            'raw': {'detail_topology': topology, 'type_word_index': words}}


def _run(*records):
    return review.build_pdf_structural_plan_reviews({(r['document_id'], r['page']): r for r in records})


def _validate(rows):
    assert len({r['review_id'] for r in rows}) == len(rows)
    assert all(r['status'] in {'REVIEW_REQUIRED', 'BLOCKED'} and r['reason'] and r['missing_evidence'] for r in rows)
    assert all('member_quantity' not in r and 'physical_member_count' not in r and 'amount' not in r for r in rows)
    for row in rows:
        for anchor in row['anchors']:
            assert {'anchor_id', 'document_id', 'source_name', 'source_sha256', 'page', 'kind', 'source_ref'} <= anchor.keys()
            x0, y0, x1, y1 = anchor['bbox_pt']
            assert x0 < x1 and y0 < y1
            assert len(anchor['source_sha256']) == 64


def test_beam_regions_require_a_unique_inside_mark_and_keep_supports_pending():
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=400)
        page.draw_rect((30, 30, 185, 51))
        page.insert_text((92, 45), 'B2', fontsize=8)
        page.draw_rect((30, 80, 185, 101))
        page.insert_text((92, 95), 'B1', fontsize=8)
        page.insert_text((119, 95), 'B3', fontsize=8)
        page.set_rotation(90)
        beam = _record(page, 'beam_layout_plan')
        for scope in ('floor_preparation_plan', 'roof_drainage_plan'):
            page = doc.new_page(width=400, height=400)
            page.draw_rect((30, 30, 185, 51))
            page.insert_text((92, 45), 'B1', fontsize=8)
            assert _run(_record(page, scope)) == []

    rows = _run(beam)
    assert len(rows) == 2
    _validate(rows)
    by_reason = {r['reason_code']: r for r in rows}
    matched = by_reason['BEAM_SPAN_SUPPORTS_UNVERIFIED']
    assert matched['status'] == 'REVIEW_REQUIRED' and matched['type_tag'] == 'B2'
    assert {a['kind'] for a in matched['anchors']} == {'VECTOR_CLOSED_BOUNDARY', 'NATIVE_TYPE_WORD'}
    ambiguous = by_reason['BEAM_LOCAL_TYPE_AMBIGUOUS']
    assert ambiguous['status'] == 'BLOCKED' and ambiguous['type_tag'] is None
    assert {a['type_tag'] for a in ambiguous['anchors'] if a['kind'] == 'NATIVE_TYPE_WORD'} == {'B1', 'B3'}


def test_parallel_and_bent_bounds_stay_localized_without_a_span_assignment():
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=400)
        page.draw_line((37, 52), (218, 52))
        page.draw_line((37, 62), (218, 62))
        for x in (55, 105, 198):
            page.draw_line((x, 43), (x, 70))
        contour = page.new_shape()
        contour.draw_polyline([(37, 110), (218, 110), (37, 143), (37, 110)])
        contour.finish(closePath=False)
        contour.commit()
        page.insert_text((160, 137), 'B4', fontsize=8)
        rows = _run(_record(page, 'beam_layout_plan'))
    _validate(rows)
    lanes = [r for r in rows if r['reason_code'] == 'BEAM_SPAN_BOUNDARY_UNRESOLVED']
    assert len(lanes) == 1
    assert lanes[0]['status'] == 'BLOCKED' and lanes[0]['type_tag'] is None
    assert Counter(a['kind'] for a in lanes[0]['anchors']) == {
        'VECTOR_PARALLEL_REVIEW_REGION': 1, 'VECTOR_STROKE_OPERATOR': 2}
    assert all(r['reason_code'] != 'BEAM_SPAN_SUPPORTS_UNVERIFIED' for r in rows)
    assert any(r['reason_code'] == 'BEAM_TYPE_MARK_WITHOUT_BOUNDARY' and r['type_tag'] == 'B4' for r in rows)


def test_foundation_marks_keep_multiplicity_and_cross_phase_comparison_is_document_local():
    with pymupdf.open() as doc:
        page = doc.new_page(width=360, height=360)
        page.draw_rect((24, 21, 68, 62))
        page.insert_text((33, 42), 'F-4', fontsize=8)
        page.insert_text((140, 42), 'T-2', fontsize=8)
        excavation = _record(page, 'excavation_plan')
        page = doc.new_page(width=360, height=360)
        page.draw_rect((24, 21, 68, 62))
        page.draw_rect((27, 25, 64, 58))
        page.insert_text((33, 42), 'F-4', fontsize=8)
        page.insert_text((75, 42), 'F-4', fontsize=8)
        page.insert_text((140, 42), 'T-2', fontsize=8)
        foundation = _record(page, 'foundation_plan')
        page = doc.new_page(width=360, height=360)
        unmarked = _record(page, 'excavation_plan')
    with pymupdf.open() as another:
        page = another.new_page(width=360, height=360)
        page.insert_text((33, 42), 'F-4', fontsize=8)
        unrelated = _record(page, 'excavation_plan', doc_id='OTHER', digest='b' * 64)
    rows = _run(foundation, unrelated, unmarked, excavation)
    _validate(rows)
    marks = [r for r in rows if r['role'] == 'FOUNDATION_TYPE_MARK_REVIEW']
    assert Counter((r['anchors'][0]['document_id'], r['type_tag']) for r in marks) == {
        ('EXAMPLE', 'F4'): 3, ('EXAMPLE', 'T2'): 2, ('OTHER', 'F4'): 1}
    assert Counter(r['reason_code'] for r in marks) == {
        'FOUNDATION_LOCAL_CONTOUR_UNVERIFIED': 1,
        'FOUNDATION_BOUNDARY_NOT_ISOLATED': 4,
        'FOUNDATION_BOUNDARY_AMBIGUOUS': 1}
    differences = [r for r in rows if r['role'] == 'FOUNDATION_MARK_COUNT_DISCREPANCY']
    difference, = differences
    assert difference['status'] == 'BLOCKED' and difference['type_tag'] == 'F4'
    assert [(r['page'], r['count']) for r in difference['sheet_mark_counts']] == [(1, 1), (2, 2)]
    assert [a['page'] for a in difference['anchors']] == [1, 2, 2]
    assert difference['occurrence_equivalence_verified'] is False
    assert rows == _run(excavation, foundation, unrelated, unmarked)


def test_authority_block_keeps_native_witness_and_disables_cross_phase_counts():
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((37, 52), 'F-7', fontsize=8)
        blocked = _record(page, 'excavation_plan', authority_block='REVISION_CONFLICT')
        page = doc.new_page()
        page.insert_text((37, 52), 'F-7', fontsize=8)
        ocr_only = _record(page, 'foundation_plan')
        index = ocr_only['raw']['type_word_index']
        mark, = index['type_word_witnesses']
        ocr_only['raw']['rendered_type_word_index'] = {'type_word_witnesses': [{
            **mark, 'status': 'OCR_TYPE_MARK_UNVERIFIED'}]}
        index['type_word_witnesses'] = []
    rows = _run(blocked, ocr_only)
    _validate(rows)
    row, = rows
    assert row['role'] == 'FOUNDATION_TYPE_MARK_REVIEW'
    assert row['status'] == 'BLOCKED' and row['reason_code'] == 'STRUCTURAL_PLAN_AUTHORITY_BLOCKED'
    assert row['type_tag'] == 'F7' and row['anchors'][0]['kind'] == 'NATIVE_TYPE_WORD'


def test_coincident_cad_beam_strokes_are_one_nonpayable_review_envelope():
    # Two pairs with identical PDF-point extents produce four alternatives,
    # but there is only one spatial review envelope, not four beam members.
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=400)
        for y in (52, 52, 62, 62):
            page.draw_line((37, y), (218, y))
        rows = _run(_record(page, 'beam_layout_plan'))
    _validate(rows)
    lanes = [r for r in rows if r['reason_code'] == 'BEAM_SPAN_BOUNDARY_UNRESOLVED']
    assert len(lanes) == 1
    one, = lanes
    assert one['parallel_pair_alternatives'] == 4
    assert one['status'] == 'BLOCKED' and one['financially_payable'] is False
    assert one['type_tag'] is None
    witness, *strokes = one['anchors']
    assert witness['parallel_pair_alternatives'] == 4
    assert witness['geometry_status'] == 'COINCIDENT_VECTOR_PAIRS_UNRESOLVED'
    assert len(strokes) == len(set(a['source_ref'] for a in strokes)) == 4


def test_noncoincident_beam_lanes_must_not_be_merged():
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=400)
        for y in (52, 62, 72):
            page.draw_line((37, y), (218, y))
        rows = _run(_record(page, 'beam_layout_plan'))
    lanes = [r for r in rows if r['reason_code'] == 'BEAM_SPAN_BOUNDARY_UNRESOLVED']
    assert len(lanes) == 2
    assert all(r['status'] == 'BLOCKED' and r['parallel_pair_alternatives'] == 1 for r in lanes)
    assert all(r['financially_payable'] is False for r in lanes)
