"""Synthetic integration tests for fail-closed documented parallel gap references."""
import copy
import hashlib
import json
import pytest
import fitz
from core.drawings.dwg_takeoff import DWGDocument, DWGEntity, apply_documented_units


def source_doc(tmp_path):
    dwg = tmp_path / 'synthetic.dwg'
    dwg.write_bytes(b'NOT A REAL DWG - SYNTHETIC TEST ONLY')
    pdf = tmp_path / 'synthetic.pdf'
    obj = fitz.open();pg=obj.new_page()
    pg.insert_text((24,35),'PROJECT SYN')
    pg.insert_text((24,55),'REV R1')
    pg.insert_text((24,90),'WALL-1: 0.1 m')
    pg.insert_text((24,115),'WALL-2: 0.2 m')
    obj.save(pdf);obj.close()
    entities = [
        DWGEntity('LINE','wall','101',{'start':(0,0),'end':(0,3),'layer_visible':True,'layer_defined':True}),
        DWGEntity('LINE','wall','102',{'start':(0.1,0),'end':(0.1,3),'layer_visible':True,'layer_defined':True}),
        DWGEntity('LINE','wall','201',{'start':(10,0),'end':(14,0),'layer_visible':True,'layer_defined':True}),
        DWGEntity('LINE','wall','202',{'start':(10,0.2),'end':(14,0.2),'layer_visible':True,'layer_defined':True})]
    doc=DWGDocument(entities=entities,units='unitless',source=str(dwg),source_sha256=hashlib.sha256(dwg.read_bytes()).hexdigest(),format='DWG')
    proof={'policy':'cad_unit_reference_v3','source_sha256':doc.source_sha256,
           'source_pdf_path':str(pdf),'source_pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
           'unit':'m','author':'engineerA','reviewer':'engineerB','reference':'SYNTHETIC TEST - NOT A REAL APPROVAL',
           'project_id':'SYN','pdf_project_id':'SYN',
           'drawing_revision':'R1','pdf_drawing_revision':'R1','absolute_tolerance_m':'0.0001',
           'pdf_identity_evidence':{'page':1,'project_text':'PROJECT SYN','revision_text':'REV R1','bbox':[15,15,220,65]},
           'references':[
               {'reference_kind':'parallel_line_gap','reference_handles':['101','102'],'member_id':'WALL-1','sheet_id':'S1','pdf_page':1,'reviewed_pdf_member_mapping':'synthetic mapping 1','cad_length':'0.1','real_length_m':'0.1', 'pdf_member_label':'WALL-1:', 'pdf_dimension_text':'0.1 m', 'pdf_dimension_value':'0.1','pdf_unit':'m','pdf_evidence_bbox':[16,74,180,99]},
               {'reference_kind':'parallel_line_gap','reference_handles':['201','202'],'member_id':'WALL-2','sheet_id':'S1','pdf_page':1,'reviewed_pdf_member_mapping':'synthetic mapping 2','cad_length':'0.2','real_length_m':'0.2','pdf_member_label':'WALL-2:', 'pdf_dimension_text':'0.2 m', 'pdf_dimension_value':'0.2','pdf_unit':'m','pdf_evidence_bbox':[16,99,180,125]}]}
    return doc,proof


def apply(tmp_path, doc, proof):
    path=tmp_path/'evidence.json'
    path.write_text(json.dumps(proof),encoding='utf-8')
    e={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    return apply_documented_units(doc,e)


def test_v3_apply_accepts_only_synthetic_independent_pairs(tmp_path):
    doc,proof=source_doc(tmp_path)
    result=apply(tmp_path,doc,proof)
    assert result.units=='m'
    assert doc.units=='unitless'
    assert [e.data['start'] for e in result.entities]==[e.data['start'] for e in doc.entities]


@pytest.mark.parametrize('change', ['self_review','wrong_source','wrong_pdf_revision','hidden_line','line_gap_mismatch','no_member_mapping'])
def test_v3_apply_rejects_unsafe_evidence(tmp_path,change):
    doc,proof=source_doc(tmp_path)
    if change=='self_review':proof['reviewer']=proof['author']
    if change=='wrong_source':proof['source_sha256']='f'*64
    if change=='wrong_pdf_revision':proof['pdf_drawing_revision']='R2'
    if change=='hidden_line':doc.entities[0].data['layer_visible']=False
    if change=='line_gap_mismatch':proof['references'][0]['cad_length']='0.11'
    if change=='no_member_mapping':proof['references'][0]['reviewed_pdf_member_mapping']=''
    with pytest.raises(ValueError):apply(tmp_path,doc,proof)


def test_v3_blank_pdf_cannot_authorize_unit_conversion(tmp_path):
    doc,proof=source_doc(tmp_path)
    pdf=tmp_path/'blank.pdf'
    obj=fitz.open();obj.new_page();obj.save(pdf);obj.close()
    proof['source_pdf_path']=str(pdf)
    proof['source_pdf_sha256']=hashlib.sha256(pdf.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='does not actually contain'):
        apply(tmp_path,doc,proof)


def test_v3_forged_identity_fails_even_when_json_fields_agree(tmp_path):
    doc,proof=source_doc(tmp_path)
    proof['drawing_revision']=proof['pdf_drawing_revision']='R2'
    proof['pdf_identity_evidence']['revision_text']='REV R2'
    with pytest.raises(ValueError,match='does not actually contain'):
        apply(tmp_path,doc,proof)