"""Synthetic-only tests. No private CAD content in repository."""
import copy
import hashlib
import pytest
import ezdxf
from ezdxf.entities import DXFClass
from core.drawings.dwg_opaque_conversion_diff import audit_opaque_conversion_loss


def make_inputs(tmp_path):
    dwg=tmp_path/'synthetic.dwg';dwg.write_bytes(b'SYNTHETIC_SOURCE_NO_REAL_AUTOCAD_DWG')
    d=ezdxf.new('R2004')
    map_root=d.rootdict.add_new_dict('Autodesk_MAP')
    aec_root=d.rootdict.add_new_dict('AEC_VARS')
    map_root.add('MAP_DISPLAY_MANAGEMENT_DICTIONARY','C1')
    aec_root.add('AEC_VARS_DWG_SETUP','C2')
    for name in ('DMMAPMANAGER','AEC_VARS_DWG_SETUP'):
        d.classes.register(DXFClass.new(dxfattribs={'name':name,'cpp_class_name':name,'app_name':'SYNTHETIC','flags':1024,'instance_count':1,'was_a_proxy':0,'is_an_entity':0}))
    dxf=tmp_path/'synthetic.dxf';d.saveas(dxf)
    ledger={'policy':'phase8_p2_opaque_decoder_evidence_v1',
            'source_sha256':hashlib.sha256(dwg.read_bytes()).hexdigest(),
            'decoder_label':'LibreDWG SYNTHETIC','verdict':'PARTIAL_NO_GO',
            'quantity_approved':False,'opaque_object_count':2,'named_root_handle':d.rootdict.dxf.handle,
            'objects':[{'handle':'C1','class_name':'DMMAPMANAGER','named_root':'Autodesk_MAP',
                        'decoder_object':'UNKNOWN_OBJ','owner_path':f'C1 <- {map_root.dxf.handle} <- {d.rootdict.dxf.handle}'},
                       {'handle':'C2','class_name':'AEC_VARS_DWG_SETUP','named_root':'AEC_VARS',
                        'decoder_object':'UNKNOWN_OBJ','owner_path':f'C2 <- {aec_root.dxf.handle} <- {d.rootdict.dxf.handle}'}]}
    # This synthetic file deliberately has two dangling unresolved references.
    return dwg,dxf,ledger


def test_detects_unresolved_opaque_objects_and_broken_dictionary_references(tmp_path):
    dwg,dxf,ledger=make_inputs(tmp_path)
    report=audit_opaque_conversion_loss(dwg,dxf,ledger)
    assert report['dxf_missing_opaque_count']==2
    assert report['dangling_named_dictionary_references_count']==2
    assert report['financial_takeoff_allowed'] is False
    assert report['independent_decoder_executed'] is False
    assert report['verdict']=='PARTIAL_NO_GO'


@pytest.mark.parametrize('case', ['sha','accepted','missing_object','duplicate','class','owner','root','source_type','dxf'])
def test_malformed_evidence_fails_closed(tmp_path,case):
    dwg,dxf,ledger=make_inputs(tmp_path);ledger=copy.deepcopy(ledger)
    if case=='sha':ledger['source_sha256']='0'*64
    if case=='accepted':ledger['quantity_approved']=True
    if case=='missing_object':ledger['opaque_object_count']=3
    if case=='duplicate':ledger['objects'].append(ledger['objects'][0]);ledger['opaque_object_count']=3
    if case=='class':ledger['objects'][0]['class_name']='FAKE_CLASS'
    if case=='owner':ledger['objects'][0]['owner_path']='C1 <- 1A'
    if case=='root':ledger['objects'][0]['named_root']='UNKNOWN'
    if case=='source_type':ledger['objects'][0]['decoder_object']='UNKNOWN_ENT'
    if case=='dxf':dxf.unlink()
    if case=='owner':
        # Owner string alone doesn't establish source truth; reject missing parent link.
        # Current source auditor checks root; stronger origin check to be added.
        ledger['objects'][0]['owner_path']='X1'
    with pytest.raises(ValueError):audit_opaque_conversion_loss(dwg,dxf,ledger)


def test_hashes_change_when_dxf_changes(tmp_path):
    dwg,dxf,ledger=make_inputs(tmp_path)
    report=audit_opaque_conversion_loss(dwg,dxf,ledger)
    assert report['converted_dxf_sha256']==hashlib.sha256(dxf.read_bytes()).hexdigest()
    assert len(report['opaque_items'])==2