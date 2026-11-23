"""Synthetic contract for source-bound draft column type length schedule."""
import hashlib
import pytest
import pymupdf
from core.drawings import pdf_column_length_schedule as schedule


def _small_pdf(tmp_path, pages=2):
    doc=pymupdf.open()
    for _ in range(pages):
        doc.new_page()
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