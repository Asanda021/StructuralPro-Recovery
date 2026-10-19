"""Explicit adversarial inputs; no engineering or financial certification."""
from copy import deepcopy
from decimal import Decimal, localcontext
import pytest
from core.takeoff.reviewed_components import positive
from core.takeoff.reviewed_detail_calculators import calculate_reviewed_detail
from core.takeoff.steel_stair_preflight import preview
from test_phase1_steel_stair_preflight_chat import schedule
from test_phase1_steel_stair_support_crosswalk_chat import example,run

@pytest.mark.parametrize('value',['9007199254740993','0.12345678901234567890123456789',Decimal('1.00000000000000001')])
def test_shared_positive_cannot_silently_truncate_exact_noninteger_input(value):
    with pytest.raises(ValueError):positive(value,'ورودی دقیق')

@pytest.mark.parametrize('kind,fields',[
 ('rectangle_volume',dict(count='1',length_m='1.000000000000001',width_m='1.000000000000001',thickness_m='1')),
 ('steel_profile_schedule',dict(count='1',length_m='1.000000000000001',unit_weight_kg_m='1.000000000000001',unit_weight_source='SYNTHETIC')),
 ('net_surface',dict(count='1',length_m='1e16',width_m='1',openings_m2='1.1')),
 ('concrete_regions',dict(length_m='1e16',width_m='1',thickness_m='1',voids=[dict(id='V',volume_m3='1.1',source_ref='SYN',approved_by='B')]))])
def test_detail_partial_subtraction_or_product_rounding_rejected(kind,fields):
    row=dict(id='PART',source_ref='SYNTHETIC',approved_by='REVIEWER',**fields)
    with pytest.raises(ValueError):calculate_reviewed_detail(kind,{'entries':[row]})

@pytest.mark.parametrize('module',['column_joint_beam_panel','phase1_multi_member_overlap'])
def test_supported_prism_endpoint_range_requires_more_than_256_digits(module):
    from importlib import import_module
    box=(Decimal('-1e-60'),)*3+(Decimal('1e60'),)*3
    with localcontext() as ctx:
        ctx.prec=1024;expected=(Decimal('1e60')+Decimal('1e-60'))**3
    assert import_module('core.takeoff.'+module)._volume(box)==expected

@pytest.mark.parametrize('alias',['ST-STR-۰۱','ST-STR-٠١','ＳＴ-ＳＴＲ-０１'])
def test_steel_stair_duplicate_unicode_physical_id_fails_closed(alias):
    d=schedule();d['groups']['treads']['entries'][0]['id']=alias;d['ownership']['claims'][1]['physical_id']=alias
    r=preview(d);assert not r['engineering_ready'] and r['candidates']==[] and r['payable_rows']==[]

@pytest.mark.parametrize('revision',[True,1.0])
def test_support_link_revision_requires_exact_integer(revision):
    d,s,p,f=example();d['links'][0]['record']['record_revision']=revision
    r=run(d,s,p,f);assert not r['support_evidence_checked'] and r['bound_supports']==[]

@pytest.mark.parametrize('register',['reviewed_structural_members','beam_detail_register','reviewed_aec_systems'])
def test_stair_part_cannot_already_exist_as_a_nested_member_piece(register):
    d,s,p,f=example()
    p.setdefault(register,{})['extra']={'status':'draft','revision':1,'data':{'parts':[{'physical_component_id':'ST-STR-۰۱'}]}}
    r=run(d,s,p,f);assert not r['support_evidence_checked'] and r['bound_supports']==[]

@pytest.mark.parametrize('value',['NaN','Infinity','-1','0','1e999','1e-999',True])
def test_invalid_shared_input_remains_blocked(value):
    with pytest.raises(ValueError):positive(value,'قیمت یا مقدار')


def test_steel_source_cannot_reuse_existing_member_source():
    from core.takeoff.bored_pile_joint_crosswalk import _digest
    d,s,p,f=example();p['reviewed_structural_members']['c']['data']['source']['source_id']=s['source']['source_id']
    d['links'][0]['record']['record_sha256']=_digest(p['reviewed_structural_members']['c'])
    assert not run(d,s,p,f)['support_evidence_checked']


def test_nested_plain_physical_id_also_identifies_an_existing_steel_piece():
    d,s,p,f=example();p['reviewed_aec_systems']={'roof':{'data':{'pieces':[{'physical_id':'ST-STR-01'}]}}}
    assert not run(d,s,p,f)['support_evidence_checked']


@pytest.mark.parametrize('mode',['void','surface','concrete'])
def test_unicode_alias_deduction_or_face_cannot_be_consumed_twice(mode):
    from core.takeoff.reviewed_components import net_concrete,net_formwork
    if mode=='void':
        row=dict(id='BOX',source_ref='SYN',approved_by='B',length_m='4',width_m='3',thickness_m='1',voids=[dict(id=i,volume_m3='1',source_ref='SYN',approved_by='B') for i in ('V-1','V-۱')])
        with pytest.raises(ValueError):calculate_reviewed_detail('concrete_regions',{'entries':[row]})
    elif mode=='concrete':
        with pytest.raises(ValueError):net_concrete(12.,[dict(id=i,volume_m3='1',source_ref='SYN',approved_by='B') for i in ('V-1','V-۱')])
    else:
        with pytest.raises(ValueError):net_formwork({'approved_by':'B','surfaces':[dict(id=i,net_area_m2='2',source_ref='SYN') for i in ('FACE-1','FACE-۱')]})


def test_measured_piece_component_rejects_fractional_count():
    from core.takeoff.reviewed_aec import _preview_component
    from core.takeoff.engine import TakeoffEngine
    item=dict(line_id='ROW',source_ref='SYN',description='قطعه',domain='building',item_code='SYN',mode='measured',quantity='1.5',unit='عدد',formula='شمارش صریح',measurement_ref='SYN')
    with pytest.raises(ValueError):_preview_component({'status':'confirmed','approved_by':'B','items':[item]},'joists',TakeoffEngine(),system_kind='kromit_roof')


def test_generic_void_deduction_must_not_partially_round_or_disappear():
    from core.takeoff.reviewed_aec import empty_system,preview_system
    from core.takeoff.engine import TakeoffEngine
    d=empty_system('uboot','L1','SYN');d['source']={'mode':'manual','source_id':'SYNTHETIC:UBOOT'}
    for name in d['components']:
        d['components'][name]={'status':'not_applicable','reason':'SYNTHETIC explicit exclusion','source_ref':'SYN','approved_by':'B'}
    for name,value in [('gross_concrete','1e16'),('verified_voids','1.1')]:
        d['components'][name]={'status':'confirmed','approved_by':'B','items':[dict(line_id=name,source_ref='SYN',description='حجم مصنوعی',domain='building',item_code='SYN',mode='measured',quantity=value,unit='m3',formula='حجم صریح مصنوعی',measurement_ref='SYN:'+name)]}
    r=preview_system(d,TakeoffEngine());assert not r['ready'] and r['rows']==[]
