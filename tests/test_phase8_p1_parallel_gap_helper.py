"""Synthetic contract tests only. No private drawing or invented approvals."""
import copy
import hashlib

import fitz
import pytest

from core.drawings.cad_unit_parallel_gap import validate_parallel_gap_references, parallel_line_gap_raw


class E:
    def __init__(self, handle, start, end):
        self.handle = handle
        self.entity_type = 'LINE'
        self.data = {'start':start, 'end':end, 'length':1.0,
                     'layer_visible':True, 'layer_defined':True}


class Doc:
    pass


@pytest.fixture
def evidence(tmp_path):
    dwg = tmp_path / 'synthetic.dwg'
    dwg.write_bytes(b'synthetic DWG identity; not a real AutoCAD file')
    pdf = tmp_path / 'synthetic.pdf'
    d = fitz.open();d.new_page();d.save(pdf);d.close()
    doc = Doc()
    doc.source = str(dwg)
    doc.source_sha256 = hashlib.sha256(dwg.read_bytes()).hexdigest()
    doc.entities = [E('A1',(0,0),(0,3)), E('A2',(0.1,0),(0.1,3)),
                    E('B1',(10,0),(14,0)), E('B2',(10,.2),(14,.2))]
    proof = {'policy':'cad_unit_reference_v3','source_pdf_path':str(pdf),
        'source_pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
        'project_id':'SYNTHETIC_P','pdf_project_id':'SYNTHETIC_P',
        'drawing_revision':'RevA','pdf_drawing_revision':'RevA',
        'absolute_tolerance_m':'0.0001',
        'references':[
            {'reference_kind':'parallel_line_gap','reference_handles':['A1','A2'],
             'member_id':'M1','sheet_id':'S1','pdf_page':1,
             'reviewed_pdf_member_mapping':'synthetic independently inspected wall A',
             'cad_length':'0.1','real_length_m':'0.1'},
            {'reference_kind':'parallel_line_gap','reference_handles':['B1','B2'],
             'member_id':'M2','sheet_id':'S1','pdf_page':1,
             'reviewed_pdf_member_mapping':'synthetic independently inspected wall B',
             'cad_length':'0.2','real_length_m':'0.2'},
        ]}
    return doc,proof


def test_two_independent_pairs(evidence):
    doc,proof = evidence
    assert validate_parallel_gap_references(doc, proof, 1.0)


@pytest.mark.parametrize('mode', [
    'same_handle','same_member','bad_sha','bad_revision','wrong_real_length',
    'wrong_raw_gap','missing_mapping','not_two_refs','invalid_page',
    'hidden','unsupported','nonparallel','nonoverlap','collinear','off_plane',
    'duplicate_handle','tolerance','wrong_unit','missing_pdf'])
def test_fail_closed(evidence,mode):
    doc,proof=evidence
    doc=copy.deepcopy(doc); proof=copy.deepcopy(proof)
    first,second=proof['references']
    if mode=='same_handle': first['reference_handles'][1]='A1'
    if mode=='same_member': second['member_id']='M1'
    if mode=='bad_sha': proof['source_pdf_sha256']='0'*64
    if mode=='bad_revision': proof['pdf_drawing_revision']='RevB'
    if mode=='wrong_real_length': first['real_length_m']='0.11'
    if mode=='wrong_raw_gap': first['cad_length']='0.2'
    if mode=='missing_mapping': first['reviewed_pdf_member_mapping']=''
    if mode=='not_two_refs': proof['references']=[first]
    if mode=='invalid_page': first['pdf_page']=999
    if mode=='hidden': doc.entities[0].data['layer_visible']=False
    if mode=='unsupported': doc.entities[0].data['unsupported_measurement']='CAD_UNVERIFIED'
    if mode=='nonparallel': doc.entities[1].data['end']=(0.2,3)
    if mode=='nonoverlap': doc.entities[1].data['start']=(0.1,6);doc.entities[1].data['end']=(0.1,9)
    if mode=='collinear': doc.entities[1].data['start']=(0,0);doc.entities[1].data['end']=(0,3)
    if mode=='off_plane': doc.entities[1].data['start']=(0.1,0,2)
    if mode=='duplicate_handle': second['reference_handles'][1]='A1'
    if mode=='tolerance': proof['absolute_tolerance_m']='0.001'
    if mode=='wrong_unit': first['real_length_m']='0.1';second['real_length_m']='0.2'
    if mode=='missing_pdf': proof['source_pdf_path']='/does/not/exist.pdf'
    with pytest.raises(ValueError):
        validate_parallel_gap_references(doc,proof,0.001 if mode=='wrong_unit' else 1.0)


def test_perpendicular_and_overlap():
    assert parallel_line_gap_raw({'start':(0,0),'end':(0,4)},
                                 {'start':(0.2,2),'end':(0.2,8)})==pytest.approx(.2)