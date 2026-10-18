"""Isolated controller tests with real SQLite CAS, not the full StructuralProApp."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import ModuleType
import json
import sqlite3
import sys

import pytest

from app.bored_pile_draft_controller import PileDraftController, _checked_document


def _input():
    return {
        'policy': 'bored_pile_specialist_chat_v1',
        'project_id': 'P', 'floor_id': 'FND', 'group_id': 'PG1',
        'source': {'source_id':'S1','source_ref':'synthetic-doc','approved_by':'Author'},
        'datum': {'coordinate_ref':'COORD','vertical_datum_ref':'Z','axis_ref':'A'},
        'piles':[{'id':'BP1', 'physical_id':'PH1',
                  'interface':{'ownership_status':'review_required','approved_by':'JointAuthor'},
                  'rebars':{'longitudinal':{'status':'confirmed','series':[{'physical_id':'REBAR','count':'2'}]},
                            'spiral_ties':{'status':'not_applicable'},'crossties':{'status':'not_applicable'},
                            'starters':{'status':'not_applicable'}}}]
    }


def _compile(e):
    if e['policy']!='bored_pile_specialist_chat_v1': raise ValueError('invalid engine input')
    for p in e['piles']:
        if not p.get('id') or not p.get('physical_id'): raise ValueError('incomplete physical pile')
    blob=json.dumps(e,ensure_ascii=False,sort_keys=True,default=str,separators=(',',':')).encode()
    return {'source_sha256':sha256(blob).hexdigest(),'rows':[
        {'kind':'concrete_net','pile_id':'BP1','physical_id':'PH1:concrete','quantity':'1','unit':'m3'},
        {'kind':'rebar_longitudinal','pile_id':'BP1','physical_id':'REBAR','quantity':'10','unit':'kg'}]}


def _json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True),encoding='utf8')
    return path


@pytest.fixture(autouse=True)
def domain_stubs(monkeypatch):
    engine=ModuleType('core.takeoff.bored_pile_specialist_chat')
    engine.compile_piles=_compile
    detail=ModuleType('core.takeoff.bored_pile_detail')
    def new_detail(floor,group):
        return {'kind':'bored_pile','floor_id':floor,'member_id':group,
                'measurement_policy':'bored_pile_reviewed_draft_v1',
                'source':{},'pile_detail':{'input':{},'input_document':{},'ownership_document':{},'preflight':{}}}
    def preview(data,*,project_id=None,project=None):
        dt=data['pile_detail']; e=dt['input']; a=_compile(e)
        ok=dt['input_document'].get('path') and sha256(Path(dt['input_document']['path']).read_bytes()).hexdigest()==dt['input_document']['sha256']
        if not ok: return {'ready':False,'engineering_ready':False,'rows':[],'commit_allowed':False,'blockers':['bad document']}
        if dt.get('ownership_document',{}).get('path'):
            from core.takeoff.bored_pile_ownership_preflight import read_evidence,audit
            owner=dt['ownership_document']; res=audit(e,a,read_evidence(owner['path'],owner['sha256']))
        else: res=None
        return {'ready':False,'engineering_ready':True,'rows':[],'commit_allowed':False,'blockers':['financial gate pending'], 'ownership_audit':res}
    detail.new_detail=new_detail;detail.preview=preview
    monkeypatch.setitem(sys.modules,'core.takeoff.bored_pile_specialist_chat',engine)
    monkeypatch.setitem(sys.modules,'core.takeoff.bored_pile_detail',detail)


class SqliteService:
    """Real SQLite CAS, deliberately NOT StructuralPro ProjectStore."""
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS members (id TEXT PRIMARY KEY, rev INTEGER NOT NULL, payload TEXT NOT NULL)')
    def open_project(self,pid):return {'id':pid, 'boq':[]} if pid=='P' else None
    def get_structural_member(self,pid,kind,floor,member):
        r=self.db.execute('SELECT rev,payload FROM members WHERE id=?',(floor+'|'+member,)).fetchone()
        return {'revision':r[0],'data':json.loads(r[1])} if r else None
    def save_structural_member_draft(self,pid,data,*,expected_revision):
        key=data['floor_id']+'|'+data['member_id'];rec=self.get_structural_member(pid,'bored_pile',data['floor_id'],data['member_id'])
        if (rec['revision'] if rec else 0)!=expected_revision: raise RuntimeError('CAS conflict')
        with self.db:
            if rec:
                affected=self.db.execute('UPDATE members SET rev=?,payload=? WHERE id=? AND rev=?',(expected_revision+1,json.dumps(data,ensure_ascii=False),key,expected_revision)).rowcount
                if affected!=1: raise RuntimeError('CAS conflict')
            else:self.db.execute('INSERT INTO members VALUES(?,?,?)',(key,1,json.dumps(data,ensure_ascii=False)))
        return self.get_structural_member(pid,'bored_pile',data['floor_id'],data['member_id'])
    def close(self):self.db.close()


def _setup(tmp_path):
    service=SqliteService(tmp_path/'p.db');c=PileDraftController(service,'P');c.new('FND','PG1')
    e=_input();source={'mode':'manual','source_id':'S1','approved_by':'Author','measurement_ref':'synthetic-doc'}
    c.attach_input(_json(tmp_path/'e.json',e),source=source)
    c.set_preflight(reviewer='PreviewReviewer',ownership_reference='synthetic-audit')
    return c,service,e


def _owner(data):
    a=_compile(data)
    alloc=[]
    for row in a['rows']:
        alloc.append({'pile_id':'BP1','operation':row['kind'],'physical_id':row['physical_id'],
                      'scope_id':row['physical_id']+':scope','payer_kind':'pile','payer_id':'PH1',
                      'bar_piece_ids':['BAR-1','BAR-2'] if row['kind'].startswith('rebar_') else [],
                      'evidence_ref':'doc','evidence_sha256':'a'*64})
    return {'schema':'bored_pile_ownership_preflight_v1','project_id':'P','floor_id':'FND',
            'group_id':'PG1','input_sha256':a['source_sha256'],'coordinate_ref':'COORD',
            'prepared_by':'OwnerAuthor','reviewer':'IndependentReviewer','allocations':alloc}


def test_real_sqlite_roundtrip_via_isolated_service(tmp_path):
    c,service,e=_setup(tmp_path)
    assert c.dirty
    before=c.preview();assert before['engineering_ready'] and not before['ready']
    c.save();assert c.revision==1 and not c.dirty
    service.close()
    service2=SqliteService(tmp_path/'p.db')
    restored=PileDraftController(service2,'P');data=restored.load('FND','PG1')
    assert restored.revision==1 and data['pile_detail']['input']==e and not restored.dirty
    restored.set_preflight(reviewer='NewReviewer',ownership_reference='audit')
    restored.save();assert restored.revision==2
    service2.close()


def test_cas_conflict_preserves_dirty_state(tmp_path):
    c,service,e=_setup(tmp_path);c.save()
    second=PileDraftController(service,'P');second.load('FND','PG1')
    c.set_preflight(reviewer='Author2',ownership_reference='v2');c.save()
    second.set_preflight(reviewer='Another',ownership_reference='v2')
    with pytest.raises(RuntimeError):second.save()
    assert second.dirty and second.revision==1
    service.close()


def test_real_ownership_evidence_preview_and_no_boq(tmp_path):
    c,service,e=_setup(tmp_path)
    owner=_owner(e)
    result=c.attach_ownership(_json(tmp_path/'owner.json',owner),reference='explicit')
    assert len(result['candidate_owned_rows'])==2 and not result['ready_for_boq']
    pv=c.preview(); assert pv['ownership_audit'] and not pv['ready'] and not pv['commit_allowed']
    c.save(); assert not service.open_project('P')['boq']
    service.close()


def test_owner_changes_are_invalidated_by_new_input(tmp_path):
    c,service,e=_setup(tmp_path)
    c.attach_ownership(_json(tmp_path/'owner.json',_owner(e)),reference='explicit')
    c.attach_input(tmp_path/'e.json',source={'mode':'manual','source_id':'S1','approved_by':'Author','measurement_ref':'synthetic-doc'})
    assert c.data['pile_detail']['ownership_document']['sha256']==''
    service.close()


@pytest.mark.parametrize('variant', ['other_project','other_floor','other_group','mode_guess','source_mismatch','float','duplicate'])
def test_invalid_or_guessed_input_cannot_enter_controller(tmp_path,variant):
    service=SqliteService(tmp_path/'p.db');c=PileDraftController(service,'P');c.new('FND','PG1');e=_input()
    source={'mode':'manual','source_id':'S1','approved_by':'Author','measurement_ref':'synthetic-doc'}
    if variant=='other_project':e['project_id']='OTHER'
    if variant=='other_floor':e['floor_id']='L2'
    if variant=='other_group':e['group_id']='DIFFERENT'
    if variant=='mode_guess':source.pop('mode')
    if variant=='source_mismatch':source['source_id']='WRONG'
    if variant=='float':e['piles'][0]['diameter_m']=0.8
    path=tmp_path/'bad.json'
    if variant=='duplicate':path.write_text('{"policy":"a","policy":"b"}')
    else:_json(path,e)
    with pytest.raises(ValueError):c.attach_input(path,source=source)
    assert not c.data['pile_detail']['input_document']
    service.close()


def test_forged_owner_cannot_replace_valid_or_unlock_money(tmp_path):
    c,service,e=_setup(tmp_path)
    good=_json(tmp_path/'owner.json',_owner(e));c.attach_ownership(good,reference='source')
    old=deepcopy(c.data['pile_detail']['ownership_document'])
    corrupted=_owner(e);corrupted['reviewer']='Author'
    with pytest.raises(ValueError):c.attach_ownership(_json(tmp_path/'bad.json',corrupted),reference='new')
    assert c.data['pile_detail']['ownership_document']==old
    service.close()


def test_float_json_duplicate_and_nonfinite_are_all_rejected(tmp_path):
    for item in ('{"n":1.1}','{"n":NaN}','{"a":2,"a":3}'):
        path=tmp_path/'bad.json';path.write_text(item)
        with pytest.raises(ValueError):_checked_document(path)
