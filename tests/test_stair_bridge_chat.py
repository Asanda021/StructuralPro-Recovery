"""Additive preflight bridge: it must not commit, invent, or duplicate."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import json
import pytest

from core.takeoff.stair_bridge_chat import compile_preview, StairBridgeError

SAMPLE = Path(__file__).parents[1] / 'examples' / 'stair_chat_example.json'

def fixture():
    return json.loads(SAMPLE.read_text(encoding='utf-8'))

def project():
    return {"id": "P1", "takeoffs": [], "boq": [], "reviewed_aec_systems": {},
            "reviewed_structural_members": {}, "beam_detail_register": {}}

def call(data=None, p=None, **kw):
    return compile_preview(data if data is not None else fixture(), p if p is not None else project(),
                           source_id=kw.get('source_id','STAI-R1'),
                           reviewer=kw.get('reviewer','بازبین جدید'),
                           ownership_reference=kw.get('ownership_reference','صورتجلسه مصنوعی مالکیت حجمی'))

def test_compatible_bridge_preview_and_existing_boq():
    d,p=fixture(),project();d0=deepcopy(d);p0=deepcopy(p)
    out=call(d,p)
    assert d==d0 and p==p0
    assert out['commit_allowed'] is False and out['engine_ready_for_boq'] is False
    assert out['status']=='preview_only_not_integrated'
    assert len(out['takeoff_candidates'])>0 and len(out['boq_dry_run'])>0
    assert {r['quantities'][0]['unit'] for r in out['takeoff_candidates']}=={'m3','m2','kg'}
    assert all(r['quantities'][0]['role']=='work' and r['quantities'][0]['unit_price'] is None for r in out['takeoff_candidates'])
    assert all('source_input_sha256' in r['params'] for r in out['takeoff_candidates'])

def test_totals_consistent_with_engine():
    from core.takeoff.stair_specialist import preview
    d=fixture();original=preview(d);out=call(d)
    actual={}
    for r in out['takeoff_candidates']:
        q=r['quantities'][0];actual[q['code']]=actual.get(q['code'],Decimal(0))+Decimal(q['amount'])
    for operation in ('waist_concrete','step_concrete','landing_concrete','formwork'):
        expected=sum((Decimal(r['quantity_exact']) for r in original['rows'] if r['operation']==operation),Decimal(0))
        assert actual['stair_'+operation] == expected
    masses=sum((Decimal(q['amount']) for row in out['takeoff_candidates']
                if (q:=row['quantities'][0])['code'].startswith('stair_rebar_')),Decimal(0))
    assert masses == Decimal(out['totals_exact']['reinforcement'])
    assert all(Decimal(x['quantity'])>0 for x in out['boq_dry_run'])

def test_deterministic_and_read_only():
    assert call()==call()
    p=project();p['metadata']={'anything':['immutable']};before=deepcopy(p)
    call(p=p);assert p==before

@pytest.mark.parametrize('changes',[{'source_id':' '},{'reviewer':'بازبین مستقل مصنوعی'},
                                      {'reviewer':'بازبین جدید','ownership_reference':' '},
                                      {'reviewer':' بازبین جدید'}, {'source_id':'STAI-R1 '}])
def test_explicit_review_and_source_required(changes):
    with pytest.raises((StairBridgeError,ValueError)):
        call(**changes)

def test_reviewer_cannot_be_formwork_detail_approver():
    d=fixture();reviewer=d['form_faces'][0]['reviewed_by']
    with pytest.raises(StairBridgeError,match='بازبین مستقل'):
        call(d,reviewer=reviewer)

@pytest.mark.parametrize('fault',['different_project','reused_source_registry','duplicate_record',
                                  'duplicate_takeoff','physical_dup','legacy_stair','invalid_registry',
                                  'invalid_takeoff','same_approver'])
def test_preflight_blocks_conflict(fault):
    d=fixture();p=project();s='STAI-R1';floor=d['metadata']['floor_id'];sid=d['metadata']['stair_id']
    if fault=='different_project':p['id']='P2'
    elif fault=='reused_source_registry':p['reviewed_aec_systems']['x']={'data':{'source':{'source_id':s}}}
    elif fault=='duplicate_record':p['reviewed_aec_systems']['x']={'data':{'kind':'stair','floor_id':floor,'system_id':sid}}
    elif fault=='duplicate_takeoff':p['takeoffs']=[{'source_id':s,'params':{},'provenance':{}}]
    elif fault=='physical_dup':p['takeoffs']=[{'source_id':'different','params':{'physical_stair_id':sid,'floor_id':floor}}]
    elif fault=='legacy_stair':p['takeoffs']=[{'source_id':'old','params':{},'member_code':sid,'system':floor,'item':'stair'}]
    elif fault=='invalid_registry':p['reviewed_structural_members']=['bad']
    elif fault=='invalid_takeoff':p['takeoffs']=[{'source_id':'wrong','params':[]}]
    elif fault=='same_approver':d['metadata']['approved_by']='بازبین جدید'
    with pytest.raises((ValueError,StairBridgeError)):
        call(d,p)

@pytest.mark.parametrize('changed', [('flights',0,'width_m','-1'),('flights',0,'tread_count','3'),
                                     ('rebars',0,'unit_mass_kg_m','NaN'),('steps',0,'run_m',.3),
                                     ('landings',0,'top_z_m','20')])
def test_original_fail_closed_engine_is_authoritative(changed):
    d=fixture();group,i,key,value=changed;d[group][i][key]=value
    with pytest.raises(ValueError):call(d)

def test_no_implicit_price_or_second_gross_concrete_payment():
    d=fixture();o=call(d)
    ops={r['quantities'][0]['code'] for r in o['takeoff_candidates']}
    assert not any('gross' in x or 'deduction' in x or 'purchase' in x for x in ops)
    assert not any(r['quantities'][0]['unit_price'] is not None for r in o['takeoff_candidates'])

def test_existing_project_data_is_not_modified_even_with_boq_dry_run():
    p=project();a=call();r=deepcopy(a['takeoff_candidates'][0]);r['source_id']='existing-source';r['id']='existing-source'
    r['provenance']['source_id']='another-source'
    p['takeoffs']=[r];before=deepcopy(p)
    with pytest.raises(ValueError):call(p=p)
    assert p==before


def test_extended_decimal_mass_totals_do_not_round():
    d=fixture()
    d['rebars'][0]['unit_mass_kg_m']='0.88800000000000000000000000000001'
    b=call(d)
    actual=sum((Decimal(r['quantities'][0]['amount']) for r in b['takeoff_candidates']
                if r['quantities'][0]['code'].startswith('stair_rebar_')), Decimal(0))
    from decimal import localcontext,Inexact,Rounded
    with localcontext() as ctx:
        ctx.prec=512
        ctx.traps[Inexact]=True
        ctx.traps[Rounded]=True
        expected=sum((Decimal(r['quantities'][0]['amount']) for r in b['takeoff_candidates']
                      if r['quantities'][0]['code'].startswith('stair_rebar_')),Decimal(0))
    assert Decimal(b['totals_exact']['reinforcement']) == expected
    assert str(expected) == b['totals_exact']['reinforcement']

def test_in_memory_boq_aggregated_quantities_equal_candidates():
    b=call()
    from collections import defaultdict
    expected=defaultdict(Decimal)
    observed=defaultdict(Decimal)
    for r in b['takeoff_candidates']:
        q=r['quantities'][0];expected[(q['code'],q['unit'])]+=Decimal(q['amount'])
    for r in b['boq_dry_run']:
        observed[(r['item_code'],r['unit'])]+=Decimal(str(r['quantity']))
    assert observed==expected

def test_replay_guard_rejects_duplicate_existing_stair_takeoff_from_same_source():
    p=project();r=call()['takeoff_candidates'][0]
    p['takeoffs']=[r]
    with pytest.raises((ValueError,StairBridgeError)):
        call(p=p)
