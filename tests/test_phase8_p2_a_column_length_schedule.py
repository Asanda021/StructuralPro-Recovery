"""Synthetic contract for source-bound draft column type length schedule."""
import hashlib
import pytest
import pymupdf
from core.drawings import pdf_column_length_schedule as schedule


def _small_pdf(tmp_path, pages=2):
    doc=pymupdf.open()
    for _ in range(pages):
        page = doc.new_page()
        for x in range(8):
            page.draw_line((x, 10), (x, 20))
    path=tmp_path/'synthetic.pdf';doc.save(path);doc.close()
    return path


def _fake_grid():
    return {'status':'VECTOR_GRID_LOCATION_CANDIDATES', 'nodes':[
        {'candidate_id':f'PDF001:p1:r1:c{i}', 'row':1,'column':i,'x_pt':10*i,'y_pt':12}
        for i in range(1,4)]}


def _mock_columns(monkeypatch):
    monkeypatch.setattr(schedule,'classify_sheet_title',lambda raw:
        {'status':'EXPLICIT_SHEET_TITLE','sheet_kind':'column_type_plan'} if raw == 'plan' else
        {'status':'EXPLICIT_SHEET_TITLE','sheet_kind':'column_detail'} if raw == 'detail' else
        {'status':'UNKNOWN_TITLE','sheet_kind':None})
    monkeypatch.setattr(pymupdf.Page,'get_text',lambda page,*a,**k: 'plan' if page.number==0 else 'detail')
    monkeypatch.setattr(schedule,'detect_vector_grid_positions',lambda *a,**k:_fake_grid())
    monkeypatch.setattr(schedule,'compact_symbol_witness',lambda page,nodes:{'nodes':nodes})
    def labels(page,nodes):
        n=[]
        for i,node in enumerate(nodes):
            x=dict(node);tag=['C1','C1','C2'][i]
            x.update(status='GRID_LOCATION_VECTOR_TYPE_CANDIDATE',suggested_type=tag,
                     vector_type_label_evidence={'tag':tag,'path_indices':(i+5,),'bbox_pt':(i,0,i+1,1)})
            n.append(x)
        return {'nodes':n,'attached':3}
    monkeypatch.setattr(schedule,'vector_column_type_labels',labels)
    monkeypatch.setattr(schedule,'_parse_pdf_lines',lambda page: (
        [{'tag':'C1','bbox':(0,0,1,1)}, {'tag':'C2','bbox':(0,3,1,4)}],
        [{'quantity_kind':'length','quantity_m':'10.5','bbox':(3,0,4,1),'printed':'L=10.5m'},
         {'quantity_kind':'length','quantity_m':'13','bbox':(3,3,4,4),'printed':'L=13m'}]))
    monkeypatch.setattr(schedule,'_score_pair',lambda mark,dim: 1.0 if (
        (mark['tag']=='C1' and dim['quantity_m']=='10.5') or
        (mark['tag']=='C2' and dim['quantity_m']=='13')) else None)


def test_source_bound_grid_to_dimension_draft(monkeypatch,tmp_path):
    path=_small_pdf(tmp_path)
    _mock_columns(monkeypatch)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    out=schedule.draft_column_length_schedule(path,expected_sha256=digest)
    assert out['status']=='DRAFT_COMPLETE_GRID_EVIDENCE'
    assert out['grid_node_count']==out['labeled_node_count']==3
    assert out['draft_extended_length_total_m']=='34.0'
    assert [(r['type_tag'],r['printed_length_m']) for r in out['rows']] == [
        ('C1','10.5'),('C1','10.5'),('C2','13')]
    assert all(not r['approved'] and not r['financially_payable'] for r in out['rows'])
    assert not out['financially_payable']


def test_mismatched_source_hash_never_schedules(tmp_path):
    path=_small_pdf(tmp_path)
    with pytest.raises(ValueError,match='SHA256'):
        schedule.draft_column_length_schedule(path,expected_sha256='0'*64)


def test_duplicate_plan_is_blocked(monkeypatch,tmp_path):
    path=_small_pdf(tmp_path)
    monkeypatch.setattr(schedule,'classify_sheet_title',lambda _: {
        'status':'EXPLICIT_SHEET_TITLE','sheet_kind':'column_type_plan'})
    out=schedule.draft_column_length_schedule(path)
    assert out['status']=='BLOCKED_NON_UNIQUE_COLUMN_TYPE_PLAN' and out['rows']==[]


def test_conflicting_detail_never_chooses_length(monkeypatch,tmp_path):
    path=_small_pdf(tmp_path)
    _mock_columns(monkeypatch)
    monkeypatch.setattr(schedule,'_collect_dimensions',lambda doc:{
        'C1':{'status':'BLOCKED_CONFLICTING_OR_MISSING_DETAIL'},
        'C2':{'status':'EXPLICIT_PRINTED_DIMENSION','length_m':'13',
              'evidence':[{'page':2,'dimension_bbox_pt':(0,0,1,1)}]}})
    out=schedule.draft_column_length_schedule(path)
    assert out['status']=='PARTIAL_WITH_BLOCKED_GRID_NODES'
    assert out['blocked_node_count']==2
    assert out['draft_extended_length_total_m']=='13'


def test_exports_retain_provenance_and_no_approval(monkeypatch,tmp_path):
    path=_small_pdf(tmp_path);_mock_columns(monkeypatch)
    out=schedule.draft_column_length_schedule(path)
    j=tmp_path/'schedule.json';c=tmp_path/'schedule.csv'
    schedule.write_schedule(out,json_path=j,csv_path=c)
    assert 'financially_payable' in c.read_text(encoding='utf-8-sig')
    assert 'DRAFT_TYPE_LENGTH_CANDIDATE' in j.read_text()

def test_native_dimension_cannot_support_two_distinct_column_types(tmp_path):
    path = tmp_path / "shared-dimension.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((20, 20), "COLUMN DETAILS")
        page.insert_text((80, 100), "C1")
        page.insert_text((160, 100), "C2")
        page.insert_text((110, 100), "L=10 m")
        doc.save(path)
    with pymupdf.open(path) as doc:
        evidence = schedule._collect_dimensions(doc)
    assert set(evidence) == {"C1", "C2"}
    assert all(row["status"].startswith("BLOCKED") for row in evidence.values())
    assert {observation["dimension_text"] for row in evidence.values()
            for observation in row["evidence"]} == {"L=10 m"}


def test_grid_lengths_are_extracted_from_synthetic_pdf_bytes_without_mocks(tmp_path):
    from core.drawings.pdf_vector_type_labels import _C, _ONE, _TWO

    path = tmp_path / "dynamic-column-schedule.pdf"
    with pymupdf.open() as doc:
        plan = doc.new_page(width=842, height=595)
        plan.insert_text((25, 35), "Column Type Plan")
        xs, ys = (180, 300, 440), (150, 300, 450)
        for x in xs:
            plan.draw_line((x, ys[0]), (x, ys[-1]))
        for y in ys:
            plan.draw_line((xs[0], y), (xs[-1], y))

        def write_glyph(strokes, x, y, width):
            vertices = [(x + a * width, y + b * 9) for a, b in strokes]
            shape = plan.new_shape()
            shape.draw_polyline(vertices)
            shape.finish(width=.15, closePath=False)
            shape.commit()

        for row, y in enumerate(ys):
            for x in xs:
                plan.draw_rect((x - 3, y - 3, x + 3, y + 3))
                write_glyph(_C, x + 8, y + 10, 6)
                write_glyph(_ONE if row < 2 else _TWO, x + 17, y + 10, 1.5 if row < 2 else 5.7)

        detail = doc.new_page(width=842, height=595)
        detail.insert_text((25, 35), "Column Details")
        detail.insert_text((75, 135), "C-1 L=2.50 m")
        detail.insert_text((75, 250), "C-2 L=4.0 m")
        doc.save(path)

    result = schedule.draft_column_length_schedule(path)
    assert result["status"] == "DRAFT_COMPLETE_GRID_EVIDENCE"
    assert result["page_count"] == 2
    assert result["grid_node_count"] == result["draft_node_count"] == 9
    assert [(r["type_tag"], r["grid_location_candidates"], r["draft_extended_length_m"])
            for r in result["groups"]] == [("C1", 6, "15.00"), ("C2", 3, "12.0")]
    assert result["draft_extended_length_total_m"] == "27.00"
    first = result["rows"][0]
    expected_refs = [f"PDF001:p1:d{path_index}:s{number}"
                     for path_index, glyph in ((8, _C), (9, _ONE))
                     for number in range(1, len(glyph))]
    assert first["source_operator_ids"] == expected_refs
    assert first["printed_dimension_text"] == "C-1 L=2.50 m"
    assert first["printed_dimension_evidence"][0]["page"] == 2
    assert len(first["printed_length_bbox_pt"]) == 4
    assert not any(row["approved"] or row["financially_payable"] for row in result["rows"])
