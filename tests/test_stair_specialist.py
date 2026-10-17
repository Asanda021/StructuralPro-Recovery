"""Independent geometric benchmarks for the unintegrated stair engine."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
from hashlib import sha256
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.takeoff.stair_specialist import preview, StairValidationError, UNITS, SCHEMA

D=Decimal


def stair_example(two_flights: bool = False, landing_void: bool = False) -> dict:
    def flight(id_,start_x,y,zlow,zhigh):
        return dict(id=id_,source_ref=f'جزئیات تاییدشده/{id_}',direction='x_positive',
                    start_x_m=start_x,start_y_m=y,start_top_z_m=zlow,end_top_z_m=zhigh,
                    horizontal_run_m='3',width_m='1.2',tread_count='10',riser_count='10',
                    tread_m='.3',riser_m='.15',normal_waist_thickness_m='.15',
                    exclusion_ref='قرارداد جداسازی کامل حجم دال از کف‌پله')
    flights=[flight('F1','0','0','0','1.5')]
    landings=[]
    connections=[]
    if two_flights:
        flights.append(flight('F2','4.2','1.2','1.5','3'))
        landings=[dict(id='L1',source_ref='دیتایل تاییدشده پاگرد',x_m='3',y_m='0',
                       length_m='1.2',width_m='2.4',top_z_m='1.5',thickness_m='.2',
                       exclusion_ref='پلان مستقل بتن پاگرد، بدون ورود به بازوها')]
        connections=[dict(id='C1',flight_id='F1',landing_id='L1',flight_end='high',
                          landing_edge='left',source_ref='دیتایل اتصال بالای بازوی اول',
                          interface_kind='shared_boundary_no_extra_volume'),
                     dict(id='C2',flight_id='F2',landing_id='L1',flight_end='low',
                          landing_edge='right',source_ref='دیتایل اتصال پایین بازوی دوم',
                          interface_kind='shared_boundary_no_extra_volume')]
    steps=[]
    form_faces=[]
    for f in flights:
        for i in range(10):
            sid=f"{f['id']}-S{i+1}"
            x=D(f['start_x_m'])+D(i)*D('.3')
            steps.append(dict(id=sid,flight_id=f['id'],source_ref='دیتایل مرحله‌ای واقعی/آموزشی',
                              separation_detail_ref='برش تاییدکننده گوه جدا از حجم شمشیری',
                              physical_scope='triangular_wedge_above_waist_exclusive',
                              x_m=str(x),y_m=f['start_y_m'],run_m='.3',rise_m='.15',width_m='1.2'))
            for face,mode in [('tread_top','no_form'),('riser','form'),('side_near','no_form'),
                              ('side_far','no_form'),('waist_contact','contact')]:
                form_faces.append(dict(key=f'{sid}:{face}',physical_id=f'FORM:{sid}:{face}',
                                       source_ref='صورتجلسه وجوه قالب گوه',treatment=mode,
                                       reviewed_by='بازبین مستقل',reason='نتیجه بازبینی محل تماس و اجرای قالب'))
        for face,mode in [('underside','form'),('side_near','form'),('side_far','form'),
                          ('end_low','contact'),('end_high','contact')]:
            form_faces.append(dict(key=f"{f['id']}:{face}",physical_id=f"FORM:{f['id']}:{face}",
                                   source_ref='دیتایل و سطح قالب شمشیری',treatment=mode,
                                   reviewed_by='بازبین مستقل',reason='سطح تماس یا سطح قالب صریح'))
    for landing in landings:
        for face,mode in [('underside','form'),('side_left','contact'),('side_right','contact'),
                          ('side_near','form'),('side_far','form')]:
            form_faces.append(dict(key=f"{landing['id']}:{face}",
                                   physical_id=f"FORM:{landing['id']}:{face}",
                                   source_ref='دیتایل قالب پاگرد',treatment=mode,
                                   reviewed_by='بازبین مستقل',reason='دیتایل اجرایی تاییدشده'))
    voids=[]
    if landing_void:
        voids=[dict(id='V1',owner_id='L1',source_ref='بازشوی سرتاسری تاییدشده',
                    x_m='3.4',y_m='.8',length_m='.2',width_m='.3',
                    penetration='full_waist_or_landing',
                    reveal_form_area_m2='.2',reveal_ref='مساحت قالب بازشو جداگانه اندازه‌گیری و تایید شده')]
        form_faces.append(dict(key='L1:reveal:V1',physical_id='FORM:L1:reveal:V1',
                               source_ref='متره مستند سطح قالب لبه بازشو',treatment='form',
                               reviewed_by='بازبین مستقل',reason='نیاز به قالب لبه طبق دیتایل'))
    rebars=[]
    for o in flights+landings:
        groups=['flight_main','flight_distribution'] if o in flights else ['landing']
        for group in groups:
            id_=f"{o['id']}:{group}"
            rebars.append(dict(id=id_,physical_id='BAR:'+id_,owner_id=o['id'],group=group,
                               source_ref='جدول متره مستند',detail_ref='دیتایل مصوب آرماتور',
                               shape_ref='شکل خم تاییدشده',mass_ref='جدول وزن واحد مصوب',
                               diameter_mm='12',count='6',unit_mass_kg_m='.888',
                               straight_m='3',bend_m='.2',hook_m='.1',anchorage_m='.4',lap_m='0'))
    return dict(schema=SCHEMA,metadata={'project_id':'P1','floor_id':'L1','stair_id':'ST01',
                                       'source_ref':'نقشه و دیتایل مصنوعی جهت آزمون',
                                       'approved_by':'بازبین مستقل مصنوعی',
                                       'story_start_z_m':'0',
                                       'story_end_z_m':'3' if two_flights else '1.5',
                                       'story_height_m':'3' if two_flights else '1.5',
                                       'story_ref':'پلان و برش ارتفاع طبقه مصنوعی'},units=UNITS.copy(),
                flights=flights,landings=landings,steps=steps,voids=voids,
                connections=connections,form_faces=form_faces,rebars=rebars,
                scope={k:'fully_documented' for k in ('steps','landings','connections','reinforcement','formwork')}
                      |{'scope_ref':'مدارک کامل اجرای همین نمونه مصنوعی'})


def q(rows,group):
    with localcontext() as context:
        context.prec=65
        return sum((D(r['quantity_exact']) for r in rows if r['operation']==group),D(0))


def test_one_flight_waist_uses_sloped_not_horizontal_length():
    o=preview(stair_example());r=o['rows']
    with localcontext() as context:
        context.prec=65
        expected=D('11.25').sqrt()*D('1.2')*D('.15')
    assert q(r,'waist_concrete')==expected
    assert q(r,'step_concrete')==D('.27')
    assert q(r,'formwork')>D('0')
    assert o['ready_for_boq'] is False


def test_one_flight_face_area_documented():
    o=preview(stair_example())
    a={r['key']:r for r in o['form_faces']}
    with localcontext() as context:
        context.prec=65
        assert D(a['F1:underside']['geometry_area_m2'])==D('11.25').sqrt()*D('1.2')
    assert D(a['F1:end_high']['payment_area_m2'])==0
    assert D(a['F1-S1:riser']['payment_area_m2'])==D('.18')
    assert D(a['F1-S1:waist_contact']['payment_area_m2'])==0


def test_two_flights_landing_and_connection_do_not_create_extra_volume():
    o=preview(stair_example(two_flights=True))
    assert q(o['rows'],'step_concrete')==D('.54')
    assert q(o['rows'],'landing_concrete')==D('.576')
    assert len(o['component_calculations'])==3
    assert all(not r['operation'].startswith('joint_') for r in o['rows'])


def test_independent_landing_void_and_reveal():
    o=preview(stair_example(two_flights=True,landing_void=True))
    assert q(o['rows'],'landing_concrete')==D('.564')
    f={r['key']:r for r in o['form_faces']}
    assert D(f['L1:underside']['geometry_area_m2'])==D('2.82')
    assert D(f['L1:reveal:V1']['payment_area_m2'])==D('.2')


def test_independently_calculated_rebar_mass():
    o=preview(stair_example()); expected=Fraction(6)*Fraction(37,10)*Fraction(888,1000)
    assert q(o['rows'],'rebar_flight_main')==D(expected.numerator)/D(expected.denominator)
    assert q(o['rows'],'rebar_flight_distribution')==D(expected.numerator)/D(expected.denominator)


def test_deterministic_report_source_hash():
    a=stair_example(two_flights=True)
    o1=preview(a);o2=preview(deepcopy(a))
    assert o1==o2
    assert len(o1['input_sha256'])==64
    b=deepcopy(a);b['flights'][0]['normal_waist_thickness_m']='.2'
    assert preview(b)['input_sha256'] != o1['input_sha256']


def test_long_decimal_recomputed_from_exact_reference():
    a=stair_example()
    a['flights'][0]['normal_waist_thickness_m']='.123456789012345678901234567890'
    o=preview(a)
    with localcontext() as c:
        c.prec=65
        expected=D('11.25').sqrt()*D('1.2')*D('.123456789012345678901234567890')
        assert abs(q(o['rows'],'waist_concrete')-expected) < D('1e-62')


@pytest.mark.parametrize('fault',[
    'schema','units','missing_source','missing_approval','float','nan','infinite','boolean',
    'zero_thickness','negative_thickness','zero_run','inconsistent_riser','inconsistent_tread',
    'inconsistent_top_z','no_flight','duplicate_flight','overlapping_landing','missing_connection',
    'bad_connection_z','bad_connection_edge','duplicate_connection','extra_joint_volume',
    'duplicate_step_id','step_overlap','step_not_on_lattice','step_bad_separation',
    'missing_steps','missing_waist_ref','step_overlaps_void','void_outside','void_touches_edge',
    'duplicate_void','overlapping_voids','non_full_void','unknown_void_owner',
    'missing_form_face','duplicate_form_face','unknown_face','missing_face_reason',
    'unknown_treatment','duplicate_form_physical_id','missing_rebar','bad_rebar_count',
    'bad_rebar_mass','missing_rebar_detail','duplicate_bar','bar_missing_main',
    'bar_owner_bad','bar_group_bad','missing_scope','scope_unknown',
    'unsupported_direction','non_unit_number','extra_field','collision_rebar_id','story_height_mismatch','story_start_mismatch'
])
def test_malformed_documented_stair_fail_closed(fault):
    a=stair_example(two_flights=True,landing_void=True)
    f=a['flights'][0];s=a['steps'][0];v=a['voids'][0];c=a['connections'][0];b=a['rebars'][0]
    if fault=='schema':a['schema']='unsupported'
    elif fault=='units':a['units']['length']='cm'
    elif fault=='missing_source':a['metadata']['source_ref']=''
    elif fault=='missing_approval':a['metadata']['approved_by']=''
    elif fault=='float':f['width_m']=1.2
    elif fault=='nan':f['width_m']='NaN'
    elif fault=='infinite':f['width_m']='Infinity'
    elif fault=='boolean':f['width_m']=True
    elif fault=='zero_thickness':f['normal_waist_thickness_m']='0'
    elif fault=='negative_thickness':f['normal_waist_thickness_m']='-0.1'
    elif fault=='zero_run':f['horizontal_run_m']='0'
    elif fault=='inconsistent_riser':f['riser_m']='.16'
    elif fault=='inconsistent_tread':f['tread_m']='.35'
    elif fault=='inconsistent_top_z':f['end_top_z_m']='1.6'
    elif fault=='no_flight':a['flights']=[]
    elif fault=='duplicate_flight':a['flights'].append(deepcopy(f))
    elif fault=='overlapping_landing':a['landings'][0]['x_m']='2.9'
    elif fault=='missing_connection':a['connections'].pop()
    elif fault=='bad_connection_z':a['landings'][0]['top_z_m']='1.51'
    elif fault=='bad_connection_edge':c['landing_edge']='right'
    elif fault=='duplicate_connection':a['connections'].append(deepcopy(c))
    elif fault=='extra_joint_volume':c['interface_kind']='extra_joint_volume'
    elif fault=='duplicate_step_id':a['steps'].append(deepcopy(s))
    elif fault=='step_overlap':a['steps'][1]['x_m']='.1'
    elif fault=='step_not_on_lattice':a['steps'][0]['x_m']='.05'
    elif fault=='step_bad_separation':s['separation_detail_ref']=''
    elif fault=='missing_steps':a['steps'].pop()
    elif fault=='missing_waist_ref':f['exclusion_ref']=''
    elif fault=='step_overlaps_void':v['owner_id']='F1';v['x_m']='.2';v['y_m']='.2'
    elif fault=='void_outside':v['x_m']='2'
    elif fault=='void_touches_edge':v['x_m']='3'
    elif fault=='duplicate_void':a['voids'].append(deepcopy(v))
    elif fault=='overlapping_voids':
        w=deepcopy(v);w['id']='V2';w['x_m']='3.5';a['voids'].append(w)
    elif fault=='non_full_void':v['penetration']='partial'
    elif fault=='unknown_void_owner':v['owner_id']='missing'
    elif fault=='missing_form_face':a['form_faces'].pop()
    elif fault=='duplicate_form_face':a['form_faces'].append(deepcopy(a['form_faces'][0]))
    elif fault=='unknown_face':a['form_faces'][0]['key']='unknown'
    elif fault=='missing_face_reason':a['form_faces'][0]['reason']=''
    elif fault=='unknown_treatment':a['form_faces'][0]['treatment']='automatic'
    elif fault=='duplicate_form_physical_id':a['form_faces'][1]['physical_id']=a['form_faces'][0]['physical_id']
    elif fault=='missing_rebar':a['rebars']=[]
    elif fault=='bad_rebar_count':b['count']='2.5'
    elif fault=='bad_rebar_mass':b['unit_mass_kg_m']='0'
    elif fault=='missing_rebar_detail':b['detail_ref']=''
    elif fault=='duplicate_bar':a['rebars'].append(deepcopy(b))
    elif fault=='bar_missing_main':a['rebars']=[x for x in a['rebars'] if x['id']!='F1:flight_main']
    elif fault=='bar_owner_bad':b['owner_id']='nobody'
    elif fault=='bar_group_bad':b['group']='random'
    elif fault=='missing_scope':a['scope'].pop('formwork')
    elif fault=='scope_unknown':a['scope']['landings']='not_reviewed'
    elif fault=='unsupported_direction':f['direction']='y_positive'
    elif fault=='non_unit_number':b['straight_m']='abc'
    elif fault=='extra_field':a['steps'][0]['magic_default']=1
    elif fault=='collision_rebar_id':b['physical_id']='F1'
    elif fault=='story_height_mismatch':a['metadata']['story_height_m']='4'
    elif fault=='story_start_mismatch':a['metadata']['story_start_z_m']='.1'
    else:raise AssertionError(fault)
    with pytest.raises(StairValidationError):preview(a)


@pytest.mark.parametrize('face', ['underside','side_near','side_far','end_low','end_high'])
def test_every_flight_face_has_structural_identity(face):
    o=preview(stair_example())
    assert len([x for x in o['form_faces'] if x['key']==f'F1:{face}'])==1


@pytest.mark.parametrize('i',list(range(10)))
def test_all_steps_explicit_exact_lattice(i):
    a=stair_example();x=a['steps'][i]
    assert D(x['x_m'])==D(i)*D('.3')
    assert q(preview(a)['rows'],'step_concrete')==D('0.27')


def test_json_round_trip_all_exact_strings():
    data=stair_example(two_flights=True,landing_void=True)
    encoded=json.dumps(data,sort_keys=True,ensure_ascii=False)
    assert preview(json.loads(encoded))==preview(data)


@pytest.mark.parametrize('n', ('0','-1','1.001','NaN','Inf'))
def test_bad_rebar_quantity(n):
    a=stair_example();a['rebars'][0]['count']=n
    with pytest.raises(StairValidationError):preview(a)


def test_angle_derived_from_explicit_slope_decimal_without_float():
    o=preview(stair_example())
    f=o['component_calculations'][0]
    assert f['component']=='F1'
    assert f['slope_direction']=='x_positive'
    assert D('26.565')<D(f['slope_angle_deg'])<D('26.566')
    assert not isinstance(f['slope_angle_deg'],float)


def test_landing_and_flight_separate_payable_areas_and_units():
    o=preview(stair_example(two_flights=True,landing_void=True))
    assert {'m2','m3','kg'} == {r['unit'] for r in o['rows']}
    for item in o['rows']:
        assert item['source_id'] and item['source_ref'] and item['formula']
        assert D(item['quantity_exact'])>0


def test_reversed_x_flight_placement_still_uses_low_to_high_z():
    a=stair_example()
    a['flights'][0]['direction']='x_negative'
    a['flights'][0]['start_x_m']='3'
    out=preview(a)
    f=out['component_calculations'][0]
    assert f['slope_direction']=='x_negative'
    assert q(out['rows'],'step_concrete')==D('.27')


def test_steep_rise_uses_decimal_arctan_reciprocal_branch():
    a=stair_example()
    a['flights'][0]['end_top_z_m']='6'
    a['metadata']['story_end_z_m']='6'
    a['metadata']['story_height_m']='6'
    a['flights'][0]['riser_m']='.6'
    for step in a['steps']:
        step['rise_m']='.6'
    out=preview(a)
    angle=D(out['component_calculations'][0]['slope_angle_deg'])
    assert D('63.434')<angle<D('63.435')
