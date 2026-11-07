"""Synthetic-only regression of historic LibreDWG unknown-class receipt.

Never use synthetic evidence to approve a real DWG or quantities.
"""
from __future__ import annotations
import copy
import hashlib

import pytest

from core.drawings.dwg_unknown_object_audit import audit_unknown_objects


def _ref(n):
    return [0, 1, n]


def _obj(n, name, owner, *, type_code=42):
    return {'handle': _ref(n), 'ownerhandle': [4, 1, owner, owner],
            'object': name, 'type': type_code}


@pytest.fixture
def evidence(tmp_path):
    dwg = tmp_path / 'demo.dwg'
    dwg.write_bytes(b'AC1018 synthetic test bytes - NOT a valid real DWG')
    objects = [
        {**_obj(26, 'DICTIONARY', 0), 'items': {'Autodesk_MAP': _ref(16), 'AEC_VARS': _ref(32)}},
        {**_obj(16, 'DICTIONARY', 26), 'items': {'MAP_DISPLAY_MANAGEMENT_DICTIONARY': _ref(48),
                                              'MAP_DISPLAY_STYLELIBRARY_DICTIONARY': _ref(49)}},
        {**_obj(32, 'DICTIONARY', 26), 'items': {'AEC_VARS_DWG_SETUP': _ref(50)}},
        _obj(48, 'UNKNOWN_OBJ', 16, type_code=514),
        _obj(49, 'UNKNOWN_OBJ', 16, type_code=515),
        _obj(50, 'UNKNOWN_OBJ', 32, type_code=521),
    ]
    cls = [
        {'number':514, 'dxfname':'DMMAPMANAGER', 'appname':'AcMapDisplayManagement'},
        {'number':515, 'dxfname':'DMSTYLELIBRARY', 'appname':'AcMapDisplayManagement'},
        {'number':521, 'dxfname':'AEC_VARS_DWG_SETUP', 'appname':'Autodesk Architectural'},
    ]
    snapshot = {'created_by': 'LibreDWG SYNTHETIC', 'OBJECTS': objects, 'CLASSES': cls}
    receipt = {'source_sha256': hashlib.sha256(dwg.read_bytes()).hexdigest(),
               'unknown_objects': [
                   {'handle':'30', 'type_code':514, 'class':'DMMAPMANAGER'},
                   {'handle':'31', 'type_code':515, 'class':'DMSTYLELIBRARY'},
                   {'handle':'32', 'type_code':521, 'class':'AEC_VARS_DWG_SETUP'},
               ], 'objects':len(objects),'libredwg_api_status':68,
               'libredwg_api_status_flags': ['DWG_ERR_UNHANDLEDCLASS','DWG_ERR_VALUEOUTOFBOUNDS'],
               'cli_exit':0, 'cli_stderr':'SUCCESS'}
    return dwg, snapshot, receipt


def test_historic_success_message_still_financial_no_go(evidence):
    result = audit_unknown_objects(*evidence)
    assert result['verdict'] == 'PARTIAL_NO_GO'
    assert result['quantity_approved'] is False
    assert result['financial_takeoff_allowed'] is False
    assert result['full_decoder_object_graph_verified'] is False
    assert result['opaque_payloads_decoded'] is False
    assert result['opaque_object_count'] == 3
    assert result['opaque_by_named_dictionary'] == {'Autodesk_MAP':2,'AEC_VARS':1}
    assert result['decoder_status_from_prior_c_api_receipt'] == 68
    assert result['cli_message_from_prior_receipt'] == 'SUCCESS'
    assert all(r['geometry_authorized'] is False for r in result['objects'])
    assert all('unknown_bits' not in r for r in result['objects'])


@pytest.mark.parametrize('fault', [
    'changed_source', 'duplicate_handle', 'missing_object', 'extra_opaque',
    'wrong_class_code', 'wrong_class_name', 'bad_owner', 'cyclic_owner',
    'missing_root', 'wrong_dictionary_ref', 'wrong_count', 'false_status_flags',
    'unknown_entity', 'missing_manifest', 'repeated_manifest_handle',
    'missing_registry', 'invalid_receipt_status', 'source_ext', 'wrong_origin',
    'wrong_ancestor_owner', 'dangling_owner'
])
def test_fails_closed_on_inconsistent_evidence(evidence, fault, tmp_path):
    dwg, snap, receipt = evidence
    snap = copy.deepcopy(snap)
    receipt = copy.deepcopy(receipt)
    src = dwg
    if fault == 'changed_source':
        src.write_bytes(src.read_bytes() + b' changed')
    elif fault == 'duplicate_handle':
        snap['OBJECTS'].append(copy.deepcopy(snap['OBJECTS'][-1]))
    elif fault == 'missing_object':
        snap['OBJECTS'].pop()
    elif fault == 'extra_opaque':
        snap['OBJECTS'].append(_obj(51,'UNKNOWN_OBJ',32,type_code=521))
    elif fault == 'wrong_class_code':
        snap['OBJECTS'][-1]['type'] = 514
    elif fault == 'wrong_class_name':
        snap['CLASSES'][-1]['dxfname']='FORGED'
    elif fault == 'bad_owner':
        snap['OBJECTS'][-1]['ownerhandle']=[4,1,16,16]
    elif fault == 'cyclic_owner':
        snap['OBJECTS'][-1]['ownerhandle']=[4,1,50,50]
    elif fault == 'missing_root':
        snap['OBJECTS'][0]['object']='LINE'
    elif fault == 'wrong_dictionary_ref':
        snap['OBJECTS'][0]['items']['AEC_VARS']=_ref(48)
    elif fault == 'wrong_count':
        receipt['objects'] += 1
    elif fault == 'false_status_flags':
        receipt['libredwg_api_status_flags']=[]
    elif fault == 'unknown_entity':
        snap['OBJECTS'][-1]['object']='UNKNOWN_ENT'
    elif fault == 'missing_manifest':
        receipt['unknown_objects']=[]
    elif fault == 'repeated_manifest_handle':
        receipt['unknown_objects'][-1]['handle']='31'
    elif fault == 'missing_registry':
        snap.pop('CLASSES')
    elif fault == 'invalid_receipt_status':
        receipt['libredwg_api_status']='68'
    elif fault == 'source_ext':
        src = tmp_path / 'not-dwg.txt'
        src.write_bytes(dwg.read_bytes())
    elif fault == 'wrong_origin':
        snap['created_by'] = 'Invented Reader 0.1'
    elif fault == 'wrong_ancestor_owner':
        snap['OBJECTS'][1]['ownerhandle']=_ref(0)
    elif fault == 'dangling_owner':
        snap['OBJECTS'][-1]['ownerhandle']=_ref(9999)
    with pytest.raises(ValueError):
        audit_unknown_objects(src, snap, receipt)