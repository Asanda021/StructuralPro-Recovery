"""Synthetic source-of-origin test. SHA is integrity, not signature/payment."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from core.takeoff.bored_pile_joint_crosswalk import (
    SOURCE_BAR_POLICY, OwnershipError, audit_joint_contract,
)
from core.takeoff.bored_pile_starter_source import audit_source, SCHEMA
from test_bored_pile_joint_crosswalk import fixture


def source_schedule(parts):
    data, compiled = parts[:2]
    return {'schema':SCHEMA, 'project_id':data['project_id'],
            'floor_id':data['floor_id'], 'group_id':data['group_id'],
            'input_sha256':compiled['source_sha256'],
            'coordinate_ref':data['datum']['coordinate_ref'],
            'vertical_datum_ref':data['datum']['vertical_datum_ref'],
            'prepared_by':'PileScheduleAuthor', 'reviewer':'PileScheduleReviewer',
            'series':[{'pile_id':'BP1','series_physical_id':'SERIES',
                       'bar_piece_ids':['BAR-1','BAR-2'],
                       'schedule_ref':'pile-rebar-sheet-A',
                       'schedule_sha256':'c'*64}]}


def fixture_v2(tmp_path):
    parts=list(fixture()); schedule=source_schedule(parts)
    path=tmp_path/'pile-source-bar-schedule.json'
    raw=json.dumps(schedule,ensure_ascii=False,sort_keys=True).encode('utf-8')
    path.write_bytes(raw)
    digest=sha256(raw).hexdigest()
    parts[3]['policy']=SOURCE_BAR_POLICY
    parts[3]['starter_source_document']={'path':str(path),'sha256':digest,
                                        'reference':'pile-source-schedule'}
    for a in parts[2]['allocations']:
        if a['operation']=='rebar_starters': a['evidence_sha256']=digest
    for t in parts[3]['bar_transfers']:
        t.update(source_sha256=digest,source_ref='pile-source-schedule')
    return parts,path,schedule


def audit(parts):
    data,compiled,owner,joint,project=parts
    return audit_joint_contract(data,compiled,owner,'b'*64,joint,project)


def test_exact_source_schedule_three_way_matches_without_payment(tmp_path):
    parts,path,document=fixture_v2(tmp_path)
    snapshot=deepcopy(parts)
    result=audit(parts)
    assert result['policy']==SOURCE_BAR_POLICY
    assert result['source_identity_verified'] is True
    assert result['source_identity_document_sha256']==sha256(path.read_bytes()).hexdigest()
    assert result['matched_starter_pieces']==2
    assert not result['ready_for_boq'] and not result['commit_allowed'] and result['rows']==[]
    assert parts==snapshot


def test_explicit_none_with_zero_starters_is_accepted_without_inference(tmp_path):
    parts,path,source=fixture_v2(tmp_path)
    parts[0]['piles'][0]['rebars']['starters']={'status':'not_applicable'}
    parts[1]['rows'].pop()
    parts[2]['allocations'].pop()
    parts[3]['bar_transfers']=[]
    source['series']=[]
    raw=json.dumps(source,ensure_ascii=False).encode('utf-8');path.write_bytes(raw)
    parts[3]['starter_source_document']['sha256']=sha256(raw).hexdigest()
    result=audit(parts)
    assert result['source_identity_verified'] and result['matched_starter_pieces']==0
    assert result['rows']==[]


@pytest.mark.parametrize('fault',[
 'missing_source','missing_source_file','tampered_source','wrong_source_sha',
 'changed_input_sha','changed_datum','changed_group','missing_series',
 'extra_series','missing_bar','extra_bar','duplicate_bar','duplicate_series',
 'unknown_series','different_bar','float_count','inconsistent_count',
 'bad_series_hash','source_author_reviewer','source_reviewer_joint_reviewer',
 'source_author_joint_reviewer','ownership_source_mismatch','transfer_source_mismatch',
 'transfer_source_ref_mismatch','counterpart_bar_missing','counterpart_bar_duplicate',
 'unknown_source_field','float_piece_id',
])
def test_starter_source_v2_blocks_unaudited_origins(tmp_path,fault):
    parts,path,document=fixture_v2(tmp_path)
    data,compiled,owner,joint,project=parts
    if fault=='missing_source': joint.pop('starter_source_document')
    elif fault=='missing_source_file':path.unlink()
    elif fault=='tampered_source':path.write_bytes(path.read_bytes()+b' ')
    elif fault=='wrong_source_sha':joint['starter_source_document']['sha256']='e'*64
    elif fault=='changed_input_sha':document['input_sha256']='e'*64
    elif fault=='changed_datum':document['vertical_datum_ref']='wrong'
    elif fault=='changed_group':document['group_id']='other'
    elif fault=='missing_series':document['series']=[]
    elif fault=='extra_series':document['series'].append({'pile_id':'UNKNOWN','series_physical_id':'EXTRA','bar_piece_ids':['X'],'schedule_ref':'ref','schedule_sha256':'c'*64})
    elif fault=='missing_bar':document['series'][0]['bar_piece_ids'].pop()
    elif fault=='extra_bar':document['series'][0]['bar_piece_ids'].append('BAR-3')
    elif fault=='duplicate_bar':document['series'][0]['bar_piece_ids'][1]='BAR-1'
    elif fault=='duplicate_series':document['series'].append(deepcopy(document['series'][0]))
    elif fault=='unknown_series':document['series'][0]['series_physical_id']='OTHER-SERIES'
    elif fault=='different_bar':document['series'][0]['bar_piece_ids'][1]='BAR-OTHER'
    elif fault=='float_count':data['piles'][0]['rebars']['starters']['series'][0]['count']=2.0
    elif fault=='inconsistent_count':data['piles'][0]['rebars']['starters']['series'][0]['count']='3'
    elif fault=='bad_series_hash':document['series'][0]['schedule_sha256']='bad-hash'
    elif fault=='source_author_reviewer':document['reviewer']=document['prepared_by']
    elif fault=='source_reviewer_joint_reviewer':joint['reviewer']=document['reviewer']
    elif fault=='source_author_joint_reviewer':joint['reviewer']=document['prepared_by']
    elif fault=='ownership_source_mismatch':owner['allocations'][1]['evidence_sha256']='e'*64
    elif fault=='transfer_source_mismatch':joint['bar_transfers'][0]['source_sha256']='e'*64
    elif fault=='transfer_source_ref_mismatch':joint['bar_transfers'][0]['source_ref']='OTHER'
    elif fault=='counterpart_bar_missing':project['reviewed_structural_members']['CAP']['data']['rebars']['starters']['series'][0]['bar_piece_ids'].pop()
    elif fault=='counterpart_bar_duplicate':project['reviewed_structural_members']['CAP']['data']['rebars']['starters']['series'][0]['bar_piece_ids'][1]='BAR-1'
    elif fault=='unknown_source_field':document['unapproved']='TRUE'
    elif fault=='float_piece_id':document['series'][0]['bar_piece_ids'][1]=3.5
    if fault in {'changed_input_sha','changed_datum','changed_group','missing_series','extra_series',
                 'missing_bar','extra_bar','duplicate_bar','duplicate_series','unknown_series',
                 'different_bar','bad_series_hash','source_author_reviewer','source_reviewer_joint_reviewer',
                 'source_author_joint_reviewer','unknown_source_field','float_piece_id'}:
        raw=json.dumps(document,ensure_ascii=False).encode('utf-8');path.write_bytes(raw)
        joint['starter_source_document']['sha256']=sha256(raw).hexdigest()
        # Deliberately repair the ownership & transfer byte references: the
        # *content* must still fail even if all document hashes are updated.
        owner['allocations'][1]['evidence_sha256']=joint['starter_source_document']['sha256']
        for transfer in joint['bar_transfers']:
            transfer['source_sha256']=joint['starter_source_document']['sha256']
    with pytest.raises((OwnershipError,ValueError,KeyError,TypeError)):
        audit(parts)


def test_legacy_v1_does_not_silently_become_identity_verified():
    data,compiled,owner,joint,project=fixture()
    result=audit_joint_contract(data,compiled,owner,'b'*64,joint,project)
    assert not result['source_identity_verified']
    assert result['source_identity_document_sha256'] is None
    assert any('قرارداد قدیمی' in b for b in result['blockers'])
    assert not result['commit_allowed']
