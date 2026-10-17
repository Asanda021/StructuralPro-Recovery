"""Actual store snapshot integration, explicitly synthetic and never payable."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from core.platform.application import StructuralProApp

ROOT=Path(__file__).resolve().parents[1]

def request():
 def read(name):return json.loads((ROOT/'examples'/name).read_text())
 stair=read('stair_chat_example.json');stair['metadata']['project_id']='P'
 return {'schema':'structural_handoff_audit_work_v1',
 'inputs':{'shear_wall':read('shear_wall_chat_reference.json'),'stair':stair,'bored_pile':read('bored_pile_documented_synthetic.json')},
 'source_ids':{'shear_wall':'DW-SW-01','stair':'STAI-R1','bored_pile':read('bored_pile_documented_synthetic.json')['source']['source_id']},
 'rebar_ownership':read('rebar_shared_synthetic.json'),
 'reviewer':'Independent Audit','review_reference':'EXPLICIT SYNTHETIC pending signed ownership'}

def evidence(tmp_path,data):
 p=tmp_path/'synthetic-input.json';p.write_text(json.dumps(data,ensure_ascii=False));return p,hashlib.sha256(p.read_bytes()).hexdigest()

def test_actual_sqlite_snapshot_preview_never_commits(tmp_path):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');before=deepcopy(a.open_project('P'));d=request();original=deepcopy(d);p,h=evidence(tmp_path,d)
 result=a.preview_structural_handoff('P',d,source_path=p,source_sha256=h)
 assert result['status']=='BLOCKED_FOR_COMMIT' and result['commit_allowed'] is False
 assert result['combined']['candidate_count']==66
 assert result['concrete_formwork_requests']['requests'] and len(result['concrete_formwork_requests']['requests'])==57
 assert result['rebar_crosswalk_requests']['unverified_candidate_count']==9
 assert len(result['rows'])==66 and result['source_sha256']==h
 assert result['snapshot_digest']==a.store.current_digest('P')
 assert d==original and a.open_project('P')==before
 a.store.close();b=StructuralProApp(tmp_path/'db');assert b.open_project('P')==before;b.store.close()

@pytest.mark.parametrize('bad',['hash','changed_document','float','duplicate_source','wrong_project','schema','unknown_field','missing_review'])
def test_fail_closed_input_and_evidence(tmp_path,bad):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=request()
 if bad=='float':d['inputs']['shear_wall']['segments'][0]['length_m']=5.0
 if bad=='duplicate_source':d['source_ids']['stair']=d['source_ids']['shear_wall']
 if bad=='wrong_project':d['inputs']['shear_wall']['project_id']='OTHER'
 if bad=='schema':d['schema']='legacy'
 if bad=='unknown_field':d['commit_allowed']=True
 if bad=='missing_review':d['reviewer']=''
 p,h=evidence(tmp_path,d)
 if bad=='hash':h='0'*64
 if bad=='changed_document':d['review_reference']='changed after evidence'
 with pytest.raises((ValueError,KeyError)):a.preview_structural_handoff('P',d,source_path=p,source_sha256=h)
 assert not a.open_project('P')['takeoffs'];a.store.close()

def test_current_snapshot_rejects_source_added_by_second_connection(tmp_path):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');a.open_project('P')
 b=StructuralProApp(tmp_path/'db');d=request();old=b.new_aec_system('shear_wall','L1','SW01');old['source']={'mode':'manual','source_id':'DW-SW-01','approved_by':'Author','measurement_ref':'synthetic'}
 b.save_aec_system_draft('P',old);p,h=evidence(tmp_path,d)
 with pytest.raises(ValueError):a.preview_structural_handoff('P',d,source_path=p,source_sha256=h)
 assert a.get_aec_system('P','shear_wall','L1','SW01');b.store.close();a.store.close()

@pytest.mark.parametrize('text',['{"schema":"a","schema":"b"}','{"n":NaN}','{"n":Infinity}'])
def test_json_rejects_duplicate_keys_and_nonfinite(text):
 from core.takeoff.structural_handoff_work import parse_request
 with pytest.raises(ValueError):parse_request(text)

def test_json_decimal_tokens_are_exact_strings():
 from core.takeoff.structural_handoff_work import parse_request
 assert parse_request('{"n":0.123456789012345678901234567890123456789}')['n']=='0.123456789012345678901234567890123456789'

@pytest.mark.parametrize('change',['project','evidence'])
def test_mid_audit_changes_invalidate_result(tmp_path,monkeypatch,change):
 from core.takeoff import shear_wall_bridge_chat
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');b=StructuralProApp(tmp_path/'db');d=request();p,h=evidence(tmp_path,d)
 real=shear_wall_bridge_chat.compile_preview
 def concurrent(*args,**kwargs):
  result=real(*args,**kwargs)
  if change=='project':
   project=b.open_project('P');project['metadata']['concurrent_note']='actual second connection';b.store.save('P',project)
  else:p.write_text('changed document during calculation')
  return result
 monkeypatch.setattr(shear_wall_bridge_chat,'compile_preview',concurrent)
 with pytest.raises(RuntimeError):a.preview_structural_handoff('P',d,source_path=p,source_sha256=h)
 assert not b.open_project('P')['boq'];b.store.close();a.store.close()
