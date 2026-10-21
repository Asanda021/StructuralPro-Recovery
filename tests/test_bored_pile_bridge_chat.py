"""Read-only adapter, financial duplicate gates and no unapproved persistence."""
from copy import deepcopy
from decimal import Decimal, localcontext, Context
import json
from pathlib import Path
import pytest
from core.takeoff.bored_pile_bridge_chat import compile_preview, PileBridgeError
from core.takeoff.bored_pile_specialist_chat import PileInputError
from core.takeoff.commit_guards import rebuild_project_boq

REFERENCE=Path(__file__).resolve().parents[1]/'examples/bored_pile_documented_synthetic.json'

def sample():return json.loads(REFERENCE.read_text(encoding='utf8'))

def preview(data=None, project=None, **kwargs):
    return compile_preview(sample() if data is None else data,
                           {'id':'P','takeoffs':[]} if project is None else project,
                           independent_reviewer='IndependentReviewer',ownership_reference='synthetic owner ledger',**kwargs)


def test_preview_is_not_committable_and_has_only_net_payable_rows():
    d=sample();r=preview(d)
    assert not r['commit_allowed'] and r['status']=='preview_only_not_integrated'
    assert len(r['blockers'])==2
    assert len(r['preview_rows'])==len(r['takeoff_candidates'])==3
    assert all(x['role']=='work' and Decimal(x['quantity'])>0 for x in r['preview_rows'])
    assert set(x['unit'] for x in r['preview_rows'])=={'m3','kg'}
    assert all(x['quantities'][0]['unit_price'] is None for x in r['takeoff_candidates'])


def test_boqunit_rebuild_preview_only_does_not_write():
    d=sample();project={'id':'P','takeoffs':[],'boq':[],'metadata':{'sentinel':'safe'}}
    before=deepcopy(project);out=preview(d,project)
    new,boq=rebuild_project_boq(project,out['takeoff_candidates'])
    assert len(new)==3 and len(boq)==3
    with localcontext(Context(prec=256)):
        for unit in ('m3','kg'):
            assert sum((Decimal(str(x['quantity'])) for x in boq if x['unit']==unit),Decimal(0))==Decimal(out['totals'][unit])
    assert project==before


def test_no_mutation_source_or_project():
    d=sample();p={'id':'P','takeoffs':[]};d0,p0=deepcopy(d),deepcopy(p)
    preview(d,p)
    assert d==d0 and p==p0


@pytest.mark.parametrize('kind',['wrong_project','duplicate_source','already_registered','duplicate_physical','old_takeoff','invalid_registry','invalid_takeoff','no_reviewer','self_review','missing_ownership','duplicate_deduction','ownership_not_clear'])
def test_reject_collisions_and_broken_reviews(kind):
    d=sample();p={'id':'P','takeoffs':[]}
    if kind=='wrong_project':p['id']='OTHER'
    if kind in ('duplicate_source','already_registered','duplicate_physical','invalid_registry'):
        old={'data':{'kind':'bored_pile','floor_id':'FND','member_id':'OLDBP',
                     'source':{'source_id':'OLD'},'geometry':{'physical_pile_id':'other'}}}
        if kind=='duplicate_source':old['data']['source']['source_id']=d['source']['source_id']
        if kind=='already_registered':old['data']['member_id']=d['piles'][0]['id']
        if kind=='duplicate_physical':old['data']['geometry']['physical_pile_id']=d['piles'][0]['physical_id']
        if kind=='invalid_registry':old={'data':'invalid'}
        p['reviewed_structural_members']={'r':old}
    if kind=='old_takeoff':p['takeoffs']=[{'source_id':'ORIG','params':{'physical_pile_id':d['piles'][0]['physical_id']}}]
    if kind=='invalid_takeoff':p['takeoffs']=[{'source_id':'ORIG','params':[] }]
    if kind=='duplicate_deduction':
        cut=dict(id='CUT1',other_physical_id='CAP1',owner='other_member',volume_m3='.01',source_ref='test',approved_by='X')
        d['piles'][0]['deductions']=[cut];d['piles'][0]['interface']['ownership_status']='documented_deductions'
        p['takeoffs']=[{'source_id':'OLD','params':{'intersections':[{'id':'bored-pile:pile-physical-01:CUT1'}]}}]
    if kind=='ownership_not_clear': d['piles'][0]['interface']['ownership_status']='bad'
    if kind=='no_reviewer':
        with pytest.raises(ValueError):
            compile_preview(d,p,independent_reviewer='',ownership_reference='ref')
        return
    if kind=='self_review':
        with pytest.raises(ValueError):
            compile_preview(d,p,independent_reviewer='GeometryAuthor',ownership_reference='ref')
        return
    if kind=='missing_ownership':
        with pytest.raises(ValueError):
            compile_preview(d,p,independent_reviewer='independent',ownership_reference='')
        return
    with pytest.raises(ValueError):preview(d,p)


def test_approved_deduction_is_retained_as_one_nonpayable_intersection():
    d=sample();cut={'id':'C1','other_physical_id':'CAP1','owner':'other_member','volume_m3':'0.000000000000000000000001','source_ref':'cap-paper','approved_by':'CapEng'}
    d['piles'][0]['deductions']=[cut];d['piles'][0]['interface']['ownership_status']='documented_deductions'
    p=preview(d)
    c=[r for r in p['takeoff_candidates'] if r['item']=='bored_pile_concrete'][0]
    assert len(c['params']['intersections'])==1 and c['params']['intersections'][0]['volume_m3']==cut['volume_m3']
    assert Decimal(p['totals']['m3'])<Decimal(preview()['totals']['m3'])


def test_exact_long_decimal_stays_intact_in_boq_with_explicit_precision():
    data=sample();data['piles'][0]['rebars']['longitudinal']['series'][0]['unit_weight_kg_m']='1.580000000000000000001'
    p={'id':'P','takeoffs':[]}
    output=preview(data,p)
    _,rows=rebuild_project_boq(p,output['takeoff_candidates'])
    with localcontext(Context(prec=256)):
        expected=sum((Decimal(x['quantity']) for x in output['preview_rows'] if x['unit']=='kg'),Decimal(0))
        actual=sum((Decimal(str(x['quantity'])) for x in rows if x['unit']=='kg'),Decimal(0))
    assert actual == expected
    assert all(x.get('unit_price') is None for x in rows)
