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
    d = fitz.open(); pg=d.new_page()
    pg.insert_text((24,35), 'PROJECT SYNTHETIC_P')
    pg.insert_text((24,55), 'REV RevA')
    pg.insert_text((24,90), 'M1: 0.1 m')
    pg.insert_text((24,115), 'M2: 0.2 m')
    d.save(pdf);d.close()
    doc = Doc()
    doc.source = str(dwg)
    doc.source_sha256 = hashlib.sha256(dwg.read_bytes()).hexdigest()
    doc.entities = [E('A1',(0,0),(0,3)), E('A2',(0.1,0),(0.1,3)),
                    E('B1',(10,0),(14,0)), E('B2',(10,.2),(14,.2))]
    proof = {'policy':'cad_unit_reference_v3','source_pdf_path':str(pdf),
        'source_pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
        'project_id':'SYNTHETIC_P','pdf_project_id':'SYNTHETIC_P',
        'drawing_revision':'RevA','pdf_drawing_revision':'RevA',
        'pdf_identity_evidence':{'page':1,'project_text':'PROJECT SYNTHETIC_P','revision_text':'REV RevA','bbox':[15,15,220,65]},
        'absolute_tolerance_m':'0.0001',
        'references':[
            {'reference_kind':'parallel_line_gap','reference_handles':['A1','A2'],
             'member_id':'M1','sheet_id':'S1','pdf_page':1,
             'reviewed_pdf_member_mapping':'synthetic independently inspected wall A',
             'cad_length':'0.1','real_length_m':'0.1',
             'pdf_member_label':'M1:','pdf_dimension_text':'0.1 m','pdf_dimension_value':'0.1','pdf_unit':'m','pdf_evidence_bbox':[16,74,140,99]},
            {'reference_kind':'parallel_line_gap','reference_handles':['B1','B2'],
             'member_id':'M2','sheet_id':'S1','pdf_page':1,
             'reviewed_pdf_member_mapping':'synthetic independently inspected wall B',
             'cad_length':'0.2','real_length_m':'0.2',
             'pdf_member_label':'M2:','pdf_dimension_text':'0.2 m','pdf_dimension_value':'0.2','pdf_unit':'m','pdf_evidence_bbox':[16,99,140,125]},
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


def test_blank_pdf_rejected_even_with_matching_hash_and_json_identity(evidence, tmp_path):
    doc, proof = evidence
    blank = tmp_path / 'blank.pdf'
    d = fitz.open(); d.new_page(); d.save(blank); d.close()
    proof['source_pdf_path'] = str(blank)
    proof['source_pdf_sha256'] = hashlib.sha256(blank.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='does not actually contain'):
        validate_parallel_gap_references(doc, proof, 1.0)


def test_forged_pdf_revision_not_found_on_actual_sheet(evidence):
    doc, proof = evidence
    proof['drawing_revision'] = proof['pdf_drawing_revision'] = 'FAKE_REVA'
    proof['pdf_identity_evidence']['revision_text'] = 'REV FAKE_REVA'
    with pytest.raises(ValueError, match='does not actually contain'):
        validate_parallel_gap_references(doc, proof, 1.0)


def test_wrong_claimed_printed_dimension_is_not_treated_as_pdf_proof(evidence):
    doc, proof = evidence
    proof['references'][0]['pdf_dimension_value'] = '0.1'
    proof['references'][0]['pdf_dimension_text'] = '0.1 cm'
    proof['references'][0]['pdf_unit'] = 'cm'
    with pytest.raises(ValueError, match='must be visible'):
        validate_parallel_gap_references(doc, proof, 1.0)


def test_missing_pdf_member_fails_closed(evidence):
    doc, proof = evidence
    proof['references'][0]['pdf_member_label'] = 'NONEXISTENT'
    with pytest.raises(ValueError, match='must be visible'):
        validate_parallel_gap_references(doc, proof, 1.0)


def test_pdf_member_region_cannot_be_whole_page(evidence):
    doc, proof = evidence
    proof['references'][0]['pdf_evidence_bbox'] = [0,0,595,842]
    with pytest.raises(ValueError, match='Oversized'):
        validate_parallel_gap_references(doc, proof, 1.0)


def test_pdf_reference_must_be_co_located(evidence):
    doc, proof = evidence
    proof['references'][0]['pdf_evidence_bbox'] = [16,99,140,125]  # M2, not M1
    with pytest.raises(ValueError, match='inside exact source region'):
        validate_parallel_gap_references(doc, proof, 1.0)


def test_project_and_revision_must_share_title_area(evidence):
    doc, proof = evidence
    proof['pdf_identity_evidence']['bbox'] = [15,15,220,42]  # project only
    with pytest.raises(ValueError, match='claimed project/revision'):
        validate_parallel_gap_references(doc, proof, 1.0)


def test_reference_boxes_cannot_overlap(evidence):
    doc, proof = evidence
    proof['references'][0]['pdf_evidence_bbox'] = [16,74,140,110]
    with pytest.raises(ValueError, match='regions must not overlap'):
        validate_parallel_gap_references(doc, proof, 1.0)


def test_distinct_handles_cannot_duplicate_physical_pair(evidence):
    doc, proof = evidence
    doc.entities.extend([E('C1',(0,0),(0,3)), E('C2',(0.1,0),(0.1,3))])
    ref = proof['references'][1]
    ref.update({'reference_handles':['C1','C2'], 'cad_length':'0.1','real_length_m':'0.1',
                'pdf_dimension_text':'0.1 m','pdf_dimension_value':'0.1','pdf_member_label':'M1:',
                'pdf_evidence_bbox':[16,74,140,99]})
    # Test duplicate CAD geometry, despite artificially different member references.
    ref['member_id'] = 'DIFFERENT'
    with pytest.raises(ValueError):
        validate_parallel_gap_references(doc,proof,1.0)