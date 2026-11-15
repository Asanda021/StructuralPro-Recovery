"""Synthetic PDF automatic-intake checks. Never contain private project drawings."""
from pathlib import Path

import pytest

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set


def _pdf(tmp_path, name='a.pdf', *, members=(('C-1', 'L= 10.70 m'),), count=1,
         vector_only=False, rotate=0):
    import pymupdf
    d = pymupdf.open()
    for page_no in range(count):
        page = d.new_page(width=600, height=500)
        if vector_only:
            page.draw_rect(pymupdf.Rect(10, 10, 80, 40))
        else:
            for j, (tag, dim) in enumerate(members):
                y = 50 + j * 75
                page.insert_text((100, y), tag, fontsize=13, rotate=rotate)
                page.insert_text((115, y), dim, fontsize=9, rotate=rotate)
    path = tmp_path / name
    d.save(path)
    d.close()
    return path


def test_single_explicit_member_type_is_not_counted_or_payable(tmp_path):
    result = inspect_pdf_sheet_set([_pdf(tmp_path)])
    assert len(result['member_type_candidates']) == 1
    c = result['member_type_candidates'][0]
    assert c['tag'] == 'C1' and c['dimension_m'] == '10.70'
    assert c['dimension_kind'] == 'length' and c['status'] == 'TYPE_DIMENSION_CANDIDATE'
    assert not c['financially_payable'] and not c['physical_instances_verified']
    assert result['physical_member_count'] is None and result['complete'] is False


def test_three_distinct_type_dimensions_extracted_without_grid_count(tmp_path):
    p = _pdf(tmp_path, members=(('C-1', 'L=10.70 m'), ('C-2', 'L=14.00 m'), ('C-3', 'L=12.00 m')))
    result = inspect_pdf_sheet_set([p])
    assert [(x['tag'], x['dimension_m']) for x in result['member_type_candidates']] == [
        ('C1', '10.70'), ('C2', '14.00'), ('C3', '12.00')]
    assert result['quantity_approval_count'] == 0


def test_rotated_member_and_dimension_match(tmp_path):
    p = _pdf(tmp_path, rotate=90)
    result = inspect_pdf_sheet_set([p])
    assert result['member_type_candidates'][0]['dimension_m'] == '10.70'


def test_cross_sheet_conflict_creates_user_question_with_unapproved_suggestion(tmp_path):
    a = _pdf(tmp_path, 'one.pdf', members=(('C-1', 'L=10.70 m'),))
    b = _pdf(tmp_path, 'two.pdf', members=(('C-1', 'L=14.00 m'),))
    report = inspect_pdf_sheet_set([a, b])
    assert len(report['questions']) == 1
    assert report['questions'][0]['tag'] == 'C1'
    assert report['questions'][0]['suggestion']['status'] == 'PROPOSED_UNVERIFIED'
    assert all(v['status'] == 'BLOCKED_CROSS_SHEET_CONFLICT' for v in report['member_type_candidates'])


def test_two_identical_type_marks_not_double_counted(tmp_path):
    a = _pdf(tmp_path, 'one.pdf', members=(('C-1', 'L=10.70 m'),))
    b = _pdf(tmp_path, 'two.pdf', members=(('C-1', 'L=10.70 m'),))
    result = inspect_pdf_sheet_set([a, b])
    assert len(result['member_type_candidates']) == 2
    assert not result['questions'] and result['physical_member_count'] is None


def test_vector_only_page_reports_unknown_semantic_coverage(tmp_path):
    report = inspect_pdf_sheet_set([_pdf(tmp_path, vector_only=True)])
    assert len(report['unresolved_pages']) == 1
    assert report['unresolved_pages'][0]['status'] == 'BLOCKED_SEMANTIC_COVERAGE_UNKNOWN'
    assert report['member_type_candidates'] == []


def test_missing_length_cannot_be_invented(tmp_path):
    result = inspect_pdf_sheet_set([_pdf(tmp_path, members=(('C-9', 'typical section'),))])
    assert result['member_type_candidates'][0]['status'] == 'BLOCKED_MISSING_DIMENSION'
    assert result['member_type_candidates'][0]['dimension_m'] is None


def test_non_member_label_not_a_member(tmp_path):
    report = inspect_pdf_sheet_set([_pdf(tmp_path, members=(('NOTE-7', 'L=10 m'),))])
    assert not report['member_type_candidates']


def test_invalid_path_and_duplicate_source_blocked(tmp_path):
    p = _pdf(tmp_path)
    with pytest.raises(ValueError, match='Duplicate'):
        inspect_pdf_sheet_set([p, p])
    with pytest.raises(ValueError, match='PDF'):
        inspect_pdf_sheet_set([tmp_path / 'missing.pdf'])


def test_page_and_file_limits(tmp_path):
    a = _pdf(tmp_path, 'a.pdf', count=2)
    b = _pdf(tmp_path, 'b.pdf')
    with pytest.raises(ValueError, match='page-count'):
        inspect_pdf_sheet_set([a,b], max_pages=2)
    with pytest.raises(ValueError, match='bounded'):
        inspect_pdf_sheet_set([a,b], max_documents=1)


def test_source_sha_matches_bytes_but_not_published_as_quantity(tmp_path):
    from hashlib import sha256
    p = _pdf(tmp_path)
    report = inspect_pdf_sheet_set([p])
    assert report['documents'][0]['sha256'] == sha256(p.read_bytes()).hexdigest()
    assert report['quantity_approval_count'] == 0


def test_cross_view_type_reference_without_physical_instance_inference(tmp_path):
    detail = _pdf(tmp_path, 'detail.pdf', members=(('C-1', 'L=10.70 m'),))
    plan = _pdf(tmp_path, 'plan.pdf', members=(('C-1', 'grid position'),))
    result = inspect_pdf_sheet_set([detail, plan])
    linked = [v for v in result['member_type_candidates'] if v['document_id'] == 'PDF002'][0]
    assert linked['status'] == 'CROSS_VIEW_TYPE_REFERENCE_CANDIDATE'
    assert linked['type_reference']['dimension_m'] == '10.70'
    assert linked['type_reference']['status'] == 'PROPOSED_UNVERIFIED'
    assert linked['physical_instances_verified'] is False
    assert result['physical_member_count'] is None and result['quantity_approval_count'] == 0


def test_batch_pdf_intake_preserves_grid_evidence_without_member_count(tmp_path):
    import pymupdf
    doc=pymupdf.open()
    page=doc.new_page(width=842,height=595)
    xs=[180,253,358,452,531];ys=[156,297,439]
    for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
    # One explicit tag, otherwise geometry cannot infer member type/count.
    page.insert_text((187,171),'C1',fontsize=9)
    f=tmp_path/'gridded_plan.pdf';doc.save(f);doc.close()
    report=inspect_pdf_sheet_set([f])
    assert len(report['grid_location_candidates'])==15
    assert report['physical_member_count'] is None
    assert report['quantity_approval_count']==0
    assert report['complete'] is False
    assert len(report['vector_grid_summaries'])==1
    assert sum(x['suggested_type']=='C1' for x in report['grid_location_candidates'])==1
    assert all(not x['financially_payable'] for x in report['grid_location_candidates'])


def test_auto_intake_compact_symbols_stay_provisional(tmp_path):
    import pymupdf
    d=pymupdf.open(); page=d.new_page(width=842,height=595)
    page.insert_text((30,30),'Column Plan',fontsize=10)
    xs=(180,300,450); ys=(150,300,450)
    for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
    for x,y in ((180,150),(300,300)):
        page.draw_rect(pymupdf.Rect(x-2,y-2,x+2,y+2))
    path=tmp_path/'column-layout.pdf';d.save(path);d.close()
    report=inspect_pdf_sheet_set([path])
    assert len(report['grid_location_candidates'])==9
    assert report['compact_symbol_candidate_count']==2
    assert report['column_layout_symbol_candidate_count']==2
    assert report['physical_member_count'] is None
    assert report['quantity_approval_count']==0 and report['complete'] is False
    assert sum(x['column_context_candidate'] for x in report['grid_location_candidates'])==2


def test_auto_intake_unlabeled_grid_has_zero_column_context(tmp_path):
    import pymupdf
    d=pymupdf.open(); page=d.new_page(width=842,height=595)
    xs=(180,300,450); ys=(150,300,450)
    for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
    page.draw_rect(pymupdf.Rect(178,148,182,152))
    path=tmp_path/'table-like-grid.pdf';d.save(path);d.close()
    report=inspect_pdf_sheet_set([path])
    assert report['compact_symbol_candidate_count']==1
    assert report['column_layout_symbol_candidate_count']==0
    assert all(not x['financially_payable'] for x in report['grid_location_candidates'])


def test_untyped_column_vector_nodes_generate_one_nonpayable_sheet_question(tmp_path):
    import pymupdf
    from core.drawings.pdf_auto_questions import PDFQuestionDecisionLedger
    d=pymupdf.open(); page=d.new_page(width=842,height=595)
    page.insert_text((30,30),'Column Plan',fontsize=10)
    xs=(180,300,450);ys=(150,300,450)
    for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
    for x,y in ((180,150),(300,300)):
        page.draw_rect(pymupdf.Rect(x-2,y-2,x+2,y+2))
    path=tmp_path/'column-type-outline.pdf'; d.save(path); d.close()
    report=inspect_pdf_sheet_set([path]); questions=report['questions']
    assert len(questions)==1
    q=questions[0]
    assert q['tag']=='GRID_TYPE:PDF001:p1'
    assert len(q['evidence'])==2
    assert q['suggestion']['value'] is None
    assert q['suggestion']['candidate_types_from_details']==[]
    assert q['financially_payable'] is False
    ledger=PDFQuestionDecisionLedger(report)
    with pytest.raises(ValueError):ledger.answer(q['tag'],'confirm_suggestion')
    assert ledger.answer(q['tag'],'request_document')['financially_payable'] is False


def test_non_column_symbol_grid_does_not_trigger_type_assignment_question(tmp_path):
    import pymupdf
    d=pymupdf.open();page=d.new_page(width=842,height=595)
    xs=(180,300,450);ys=(150,300,450)
    for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
    page.draw_rect(pymupdf.Rect(178,148,182,152))
    path=tmp_path/'unknown-grid.pdf';d.save(path);d.close()
    report=inspect_pdf_sheet_set([path])
    assert report['column_layout_symbol_candidate_count']==0
    assert report['questions']==[]


def test_auto_intake_vector_stroke_column_labels_and_grouped_review(tmp_path):
    """Synthetic complete PDF roundtrip: 3 distinct type shapes, no BOQ write."""
    import pymupdf
    from core.drawings.pdf_vector_type_labels import (
        _C, _ONE, _TWO, _THREE_TOP, _THREE_BOTTOM,
    )
    d=pymupdf.open();p=d.new_page(width=842,height=595)
    p.insert_text((25,35),'Column Plan',fontsize=12)
    xs=(180,300,440);ys=(150,300,450)
    for x in xs:p.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys:p.draw_line((xs[0],y),(xs[-1],y))
    for x,y in ((180,150),(300,300),(440,450)):
        p.draw_rect(pymupdf.Rect(x-3,y-3,x+3,y+3))
    def vector_glyph(template,x,y,w,h):
        pts=[(x+u*w,y+v*h) for u,v in template]
        shape=p.new_shape()
        for a,b in zip(pts,pts[1:]):
            shape.draw_line(a,b)
        shape.finish(color=(0,0,0),width=.15,closePath=False)
        shape.commit()
    def text_strokes(digit,x,y):
        vector_glyph(_C,x,y,6,9)
        if digit=='1':vector_glyph(_ONE,x+9,y,1.5,9)
        elif digit=='2':vector_glyph(_TWO,x+9,y,5.7,9)
        else:
            vector_glyph(_THREE_TOP,x+9,y,5.7,9)
            vector_glyph(_THREE_BOTTOM,x+9,y,5.7,9)
    text_strokes('1',188,160)
    text_strokes('2',308,308)
    text_strokes('3',420,425)
    detail=d.new_page(width=842,height=595)
    for j,(name,length) in enumerate((('C-1','10.70'),('C-2','14.00'),('C-3','12.00'))):
        detail.insert_text((60,80+35*j),f'{name} L= {length} m',fontsize=10)
    file=tmp_path/'vector-labels.pdf';d.save(file);d.close()
    report=inspect_pdf_sheet_set([file])
    assert report['page_count']==2
    assert report['vector_type_label_candidate_count']==3
    types={n['candidate_id']:n['suggested_type'] for n in report['grid_location_candidates']
           if n.get('vector_type_label_evidence')}
    assert types=={'PDF001:p1:r1:c1':'C1',
                   'PDF001:p1:r2:c2':'C2',
                   'PDF001:p1:r3:c3':'C3'}
    assert len(report['questions'])==1
    q=report['questions'][0]
    assert q['tag']=='GRID_TYPE:PDF001:p1'
    assert len(q['suggestion']['per_location_type_candidates'])==3
    assert report['vector_type_detail_link_count']==3
    references={n['suggested_type']: n['cross_sheet_type_reference']['details'][0]['dimension_m']
                for n in report['grid_location_candidates'] if n.get('cross_sheet_type_reference')}
    assert references=={'C1':'10.70','C2':'14.00','C3':'12.00'}
    assert all(n['cross_sheet_type_reference']['status']=='PROPOSED_UNVERIFIED'
               for n in report['grid_location_candidates'] if n.get('cross_sheet_type_reference'))
    assert all(row['status']=='PROPOSED_UNVERIFIED' for row in
               q['suggestion']['per_location_type_candidates'])
    assert all(e['financially_payable'] is False for e in report['grid_location_candidates'])
    assert report['physical_member_count'] is None
    assert report['quantity_approval_count']==0
    assert report['complete'] is False