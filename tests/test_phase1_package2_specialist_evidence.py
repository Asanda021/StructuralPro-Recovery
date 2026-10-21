"""Component-level synthetic evidence, explicitly not complete family acceptance."""
from copy import deepcopy
from decimal import Decimal
import pytest
from core.takeoff.steel_stair_preflight import GROUP_UNITS,preview
from core.takeoff.reviewed_aec import _preview_component
from core.takeoff.engine import TakeoffEngine
from test_phase1_steel_stair_preflight_chat import schedule


def all_groups():
    d=schedule()
    for name,unit in GROUP_UNITS.items():
        if name in ('stringers','treads'):continue
        mode='steel_profile_schedule' if unit=='kg' else 'piece_schedule' if unit=='عدد' else 'measured'
        details=dict(count='2',length_m='3',unit_weight_kg_m='4.5',unit_weight_source='SYNTHETIC-CATALOG') if unit=='kg' else dict(count='2') if unit=='عدد' else dict(quantity='2',unit=unit,measurement_ref='SYNTHETIC-MEASUREMENT',basis='explicit synthetic measured surface or length')
        entry=dict(id='ST-'+name,source_ref='SYN:'+name,approved_by='Reviewer',spec_ref='SYN-SPEC:'+name,scope_ref='SYN-SCOPE:'+name,mode=mode,details=details)
        d['groups'][name]=dict(status='confirmed',approved_by='Reviewer',source_ref='SYN:'+name,reason='',entries=[entry])
        d['ownership']['claims'].append(dict(physical_id=entry['id'],building_id=d['building_id'],owner_system=d['system_id'],payer_system=d['system_id'],scope_ref=entry['scope_ref'],source_ref=entry['source_ref'],approved_by='OwnershipReviewer'))
    return d


def test_all_eleven_steel_stair_groups_have_independent_expected_quantities():
    d=all_groups();r=preview(d);assert r['engineering_ready'],r['blockers']
    assert len(r['candidates'])==11
    assert {u:Decimal(v) for u,v in r['totals_exact'].items()}=={'kg':Decimal('229.2'),'عدد':Decimal('4'),'m':Decimal('2'),'m2':Decimal('4')}
    assert not r['ready'] and not r['commit_allowed'] and r['payable_rows']==[]


@pytest.mark.parametrize('group',tuple(GROUP_UNITS))
def test_any_invalid_group_clears_whole_candidate_schedule(group):
    d=all_groups();d['groups'][group]['approved_by']='';r=preview(d)
    assert not r['engineering_ready'] and r['candidates']==[] and r['totals_exact']=={} and r['payable_rows']==[]


@pytest.mark.parametrize('group',[g for g in GROUP_UNITS if g not in ('stringers','treads')])
def test_non_applicability_requires_explicit_reason_and_review(group):
    d=schedule();d['groups'][group]['reason']=''
    assert not preview(d)['engineering_ready']

# Existing specialized component calculators, not a whole-roof design engine.
CASES=[
 ('kromit_roof','joists','piece_schedule',dict(count='3',spec_ref='SYN-CATALOG'),'3','عدد'),
 ('composite_roof','steel_members','steel_profile_schedule',dict(count='2',length_m='3',unit_weight_kg_m='4.5',unit_weight_source='SYN-CATALOG'),'27','kg'),
 ('sandwich_roof','panels','piece_schedule',dict(count='3',spec_ref='SYN-CATALOG'),'3','عدد'),
 ('timber_roof','joists','timber_volume_schedule',dict(count='2',length_m='3',width_m='0.2',depth_m='0.1'),'0.12','m3'),
 ('precast_roof','precast_units','piece_schedule',dict(count='3',spec_ref='SYN-CATALOG'),'3','عدد'),
 ('handrails_metalwork','profiles','steel_profile_schedule',dict(count='2',length_m='3',unit_weight_kg_m='4.5',unit_weight_source='SYN-CATALOG'),'27','kg'),
]

@pytest.mark.parametrize('family,component,mode,fields,expected,unit',CASES)
def test_existing_family_component_positive_formula_and_negative_evidence(tmp_path,family,component,mode,fields,expected,unit):
    entry=dict(id='SYN-PART',source_ref='SYN-DRAWING',approved_by='IndependentSyntheticReviewer',**fields)
    item=dict(line_id='ROW-1',source_ref='SYN-DRAWING',description='جزء مصنوعی بدون پذیرش طراحی',domain='building',item_code='SYNTHETIC',mode='detail',detail_type=mode,details={'entries':[entry]})
    data={'status':'confirmed','approved_by':'IndependentSyntheticReviewer','items':[item]}
    result=_preview_component(data,component,TakeoffEngine(),system_kind=family)
    assert len(result)==1 and Decimal(str(result[0]['quantity']))==Decimal(expected) and result[0]['unit']==unit
    invalid=deepcopy(data);invalid['items'][0]['details']['entries'][0]['source_ref']=''
    with pytest.raises(ValueError):_preview_component(invalid,component,TakeoffEngine(),system_kind=family)

    from core.platform.application import StructuralProApp
    a=StructuralProApp(tmp_path/'db');a.create_project('جزء مصنوعی؛ خانواده هنوز ناتمام','P')
    draft=a.new_aec_system(family,'L1','MEMBER')
    draft['source']={'mode':'manual','source_id':'SYNTHETIC:'+family}
    draft['components'][component]=data
    a.save_aec_system_draft('P',draft,expected_revision=0);a.store.close()
    b=StructuralProApp(tmp_path/'db')
    try:
        assert b.get_aec_system('P',family,'L1','MEMBER')['data']==draft
        preview=b.preview_aec_system('P',family,'L1','MEMBER')
        assert not preview['ready'] and preview['rows']==[]
        before='\n'.join(b.store.db.iterdump())
        with pytest.raises(ValueError):b.commit_aec_system('P',family,'L1','MEMBER',expected_revision=1)
        assert '\n'.join(b.store.db.iterdump())==before and b.open_project('P')['boq']==[]
    finally:b.store.close()


def test_new_timber_volume_mode_cannot_acquire_financial_permission():
    from core.takeoff.reviewed_aec import empty_system,preview_system
    d=empty_system('timber_roof','L1','WOOD');d['source']={'mode':'manual','source_id':'SYN:WOOD'}
    for name in d['components']:
        d['components'][name]={'status':'not_applicable','reason':'explicit synthetic exclusion','source_ref':'SYN','approved_by':'B'}
    entry=dict(id='WOOD-1',source_ref='SYN',approved_by='B',count='2',length_m='3',width_m='.2',depth_m='.1')
    d['components']['joists']={'status':'confirmed','approved_by':'B','items':[dict(line_id='WOOD',source_ref='SYN',description='چوب مصنوعی',domain='building',item_code='SYN',mode='detail',detail_type='timber_volume_schedule',details={'entries':[entry]})]}
    r=preview_system(d,TakeoffEngine());assert not r['ready'] and r['rows']==[]
