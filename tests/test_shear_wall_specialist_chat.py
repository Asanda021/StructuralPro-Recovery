"""Synthetic reference & adversarial checks for isolated shear-wall takeoff."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import importlib.util
from pathlib import Path
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'core/takeoff/shear_wall_specialist_chat.py'
spec = importlib.util.spec_from_file_location('shear_wall_specialist_chat', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def source(ref='مصنوعی: DW-SW/01'):
    return {'source_ref':ref, 'approved_by':'بازبین مصنوعی'}


def part(id='P1', x='0', z='0', length='5', height='3', thickness='.25', y='0'):
    return dict(id=id, physical_part_id=id, x_m=x, z_m=z, y_m=y, length_m=length,
                height_m=height, thickness_m=thickness, **source('section/'+id))


def face(id, seg='P1', side='front', status='formed', contacts=None):
    return dict(id=id, segment_id=seg, side=side, status=status,
                contact_rectangles=[] if contacts is None else contacts, payment_ref='مصنوعی:صورتجلسه پرداخت قالب', **source('form/'+id))


def na(name):
    return dict(status='not_applicable', reason='خارج از قرارداد همین نمونه صرفاً مصنوعی', **source('schedule/'+name))


def sample():
    groups={k:na(k) for k in mod.BAR_GROUPS}
    groups['vertical'] = dict(status='confirmed', series=[dict(id='V1', physical_bar_set_id='V1',
        diameter_mm='16', count='8', count_scope='total_wall', unit_weight_kg_m='2.47',
        unit_weight_source='جدول نمونه مصنوعی',
        cut_parts=[dict(kind='straight',length_m='3', **source('bar/straight')),
                   dict(kind='lap',length_m='.4', **source('bar/lap'))], **source('bar/V1'))],
        **source('bars/vertical'))
    groups['horizontal'] = dict(status='confirmed', series=[dict(id='H1', physical_bar_set_id='H1',
        diameter_mm='12', count='4', count_scope='total_wall', unit_weight_kg_m='0.888',
        unit_weight_source='جدول نمونه مصنوعی H', cut_length_m='5', **source('bar/H1'))], **source('bars/horizontal'))
    return {
        'schema_version':mod.SCHEMA,'kind':'shear_wall','project_id':'P','floor_id':'L1','wall_id':'SW01',
        'physical_wall_id':'SW01-physical',
        'source':dict(mode='manual',source_id='DW-SW-01',length_unit='m',**source('manual/evidence')),
        'datum':dict(coordinate_ref='CS1',axis_ref='X-A',level_ref='L1+0.00',orientation='positive_x', approved_by='بازبین مصنوعی'),
        'segments':[part()],
        'openings':[dict(id='O1',segment_id='P1',x_m='1',z_m='1',width_m='1',height_m='1',**source('opening/O1'))],
        'interfaces':[],
        'formwork':dict(status='confirmed', payment_scope_ref='مصنوعی:مبنای مالی قرارداد', payment_approved_by='بازبین مصنوعی', **source('form/all'),
            edge_scope=dict(status='reviewed_complete', **source('form/scope')),
            main_faces=[face('Ffront',side='front'),face('Fback',side='back')], edge_faces=[]),
        'rebars':groups,
    }


def d(s):return Decimal(s)


def assert_code(example,code):
    with pytest.raises(mod.ShearWallValidationError) as e:mod.preview(example)
    assert e.value.code==code


def test_rectangular_concrete_opening_and_formwork_exact():
    r=mod.preview(sample())
    assert r['totals']['gross_concrete_m3']=='3.75'
    assert r['totals']['openings_m3']=='0.25'
    assert r['totals']['net_concrete_m3']=='3.5'
    assert r['totals']['geometric_main_formwork_m2']=='28'
    assert r['totals']['payable_formwork_m2']=='28'
    assert r['totals']['rebar_kg']=='84.944'
    assert r['rebar_groups']['horizontal']['kg']=='17.76'
    assert len(r['input_sha256'])==64
    assert r['status']=='standalone_reviewed_preview_not_committed'


def test_documented_interface_face_contact_excluded_exact():
    x=sample()
    x['interfaces']=[dict(id='JOINT-C1',segment_id='P1',foreign_member_id='C1',
       x_m='3',y_m='0',z_m='.5',width_m='.5',depth_m='.1',height_m='1',
       deduction_owner='shear_wall', common_datum_ref='CS1', **source('contact/C1'))]
    x['formwork']['main_faces'][0]['contact_rectangles']=[
       dict(id='C1-contact',x_m='3',z_m='.5',width_m='.5',height_m='1',**source('contact/face'))]
    x['formwork']['edge_faces']=[dict(id='side-right',physical_face_id='R-right',segment_id='P1',
       kind='right_end',status='formed',start_m='0',end_m='3',payment_ref='مصنوعی:صورتجلسه قالب',**source('edge/R'))]
    r=mod.preview(x)
    assert r['totals']['documented_interface_m3']=='0.05'
    assert r['totals']['net_concrete_m3']=='3.45'
    assert r['totals']['payable_main_formwork_m2']=='27.5'
    assert r['totals']['payable_edge_formwork_m2']=='0.75'
    assert r['totals']['payable_formwork_m2']=='28.25'


def test_two_adjacent_segments_with_explicit_faces_do_not_overlap():
    x=sample()
    x['segments'].append(part('P2',x='5',length='2',thickness='.3'))
    x['formwork']['main_faces'] += [face('F2-front',seg='P2',side='front'),face('F2-back',seg='P2',side='back')]
    r=mod.preview(x)
    assert r['totals']['gross_concrete_m3']=='5.55'
    assert r['totals']['net_concrete_m3']=='5.3'
    assert r['totals']['payable_main_formwork_m2']=='40'


def test_two_zone_shapes_can_share_only_boundary():
    x=sample()
    x['segments'][0]['length_m']='3'
    x['segments'].append(part('P2',x='3',length='2'))
    x['formwork']['main_faces'] += [face('F2-front',seg='P2',side='front'),face('F2-back',seg='P2',side='back')]
    assert mod.preview(x)['totals']['gross_concrete_m3']=='3.75'


def test_true_step_discontinuity_is_not_inferred():
    x=sample()
    x['segments'].append(part('P2',x='5',z='1',length='2',height='2'))
    x['formwork']['main_faces'] += [face('F2-front',seg='P2',side='front'),face('F2-back',seg='P2',side='back')]
    assert mod.preview(x)['totals']['gross_concrete_m3']=='4.75'


def test_main_face_not_required_is_zero_payable_but_still_geometric():
    x=sample()
    x['formwork']['main_faces'][1].update(status='not_required',reason='وجه تماس طبق دیتایل')
    r=mod.preview(x)
    assert r['totals']['geometric_main_formwork_m2']=='28'
    assert r['totals']['payable_main_formwork_m2']=='14'


def test_part_length_parts_and_direct_cut_same_quantity():
    x=sample();bar=x['rebars']['vertical']['series'][0]
    del bar['cut_parts'];bar['cut_length_m']='3.4'
    assert mod.preview(x)['totals']['rebar_kg']=='84.944'


def test_exact_decimal_without_float_rounding():
    x=sample();x['segments'][0]['length_m']='5.000000000000000001'
    r=mod.preview(x)
    assert r['totals']['gross_concrete_m3']=='3.75000000000000000075'
    assert d(r['totals']['net_concrete_m3']) == d('3.50000000000000000075')


def test_deterministic_sha_and_normalized_claims():
    x=sample();a=mod.preview(x);b=mod.preview(deepcopy(x))
    assert a==b
    assert 'p:l1:wall:sw01-physical' in a['physical_claims']
    assert 'p:l1:bar:v1' in a['physical_claims']
    assert_code_for_claim(x,a)


def assert_code_for_claim(x,a):
    with pytest.raises(mod.ShearWallValidationError) as e:
        mod.preview(x, existing_claims=set(a['physical_claims']))
    assert e.value.code=='DUPLICATE'


def test_new_manual_evidence_changes_input_hash_not_quantities():
    x=sample();a=mod.preview(x)
    x['source']['source_ref']='manual/new-evidence'
    b=mod.preview(x)
    assert a['input_sha256']!=b['input_sha256']
    assert a['totals']==b['totals']


def test_rebar_identity_duplicate_across_groups_denied():
    x=sample();g=x['rebars']['horizontal']=deepcopy(x['rebars']['vertical'])
    assert_code(x,'DUPLICATE')


def test_explicit_rebar_group_sum_two_different_series():
    x=sample();group=x['rebars']['vertical'];extra=deepcopy(group['series'][0]);extra['id']='V2';extra['physical_bar_set_id']='V2';extra['count']='2'
    group['series'].append(extra)
    assert mod.preview(x)['totals']['rebar_kg']=='101.74'


def test_openings_touching_allowed_edge_but_not_overlapping():
    x=sample()
    x['openings'][0].update(x_m='0',z_m='0')
    x['openings'].append(dict(id='O2',segment_id='P1',x_m='1',z_m='0',width_m='1',height_m='1',**source('O2')))
    assert mod.preview(x)['totals']['openings_m3']=='0.5'


def test_interface_with_cross_member_midwall_does_not_guess_contact():
    x=sample()
    x['interfaces']=[dict(id='C1',segment_id='P1',foreign_member_id='Column',x_m='3',y_m='.1',z_m='0',width_m='.3',depth_m='.05',height_m='1',deduction_owner='shear_wall',common_datum_ref='CS1',**source('cross'))]
    assert mod.preview(x)['totals']['documented_interface_m3']=='0.015'


def test_interface_reject_touching_without_face_contact():
    x=sample()
    x['interfaces']=[dict(id='C1',segment_id='P1',foreign_member_id='Column',x_m='3',y_m='0',z_m='0',width_m='.3',depth_m='.05',height_m='1',deduction_owner='shear_wall',common_datum_ref='CS1',**source('cross'))]
    assert_code(x,'FORMWORK')


def test_rc_wall_mandatory_rebar_cannot_be_marked_not_applicable():
    x=sample();x['rebars']['vertical']=na('vertical')
    assert_code(x,'REBAR_DETAIL')
    x=sample();x['rebars']['horizontal']=na('horizontal')
    assert_code(x,'REBAR_DETAIL')
    assert mod.preview(sample())['rebar_groups']['crossties']['kg'] is None


@pytest.mark.parametrize('field', ['schema_version','kind','project_id','floor_id','wall_id','physical_wall_id','source','datum','segments','openings','interfaces','formwork','rebars'])
def test_required_document_keys_cannot_be_omitted(field):
    x=sample();del x[field]
    assert_code(x,'SCHEMA')


@pytest.mark.parametrize('bad', ['NaN','Infinity','-Infinity','-1','0',float('nan'),0.2, True, [],None,'1e-100','999999999999999999999'])
def test_bad_thickness_fail_closed(bad):
    x=sample();x['segments'][0]['thickness_m']=bad
    with pytest.raises(mod.ShearWallValidationError):mod.preview(x)


@pytest.mark.parametrize('bad', ['NaN','Infinity','-Infinity','0','-1', 1.2, None, True, '1e-20'])
def test_bar_mass_and_count_reject_invalid(bad):
    x=sample();x['rebars']['vertical']['series'][0]['unit_weight_kg_m']=bad
    with pytest.raises(mod.ShearWallValidationError):mod.preview(x)


@pytest.mark.parametrize('bad', ['0','-1','2.5',2.5,float('inf'),None,False])
def test_rebar_counts_are_documented_integers(bad):
    x=sample();x['rebars']['vertical']['series'][0]['count']=bad
    with pytest.raises(mod.ShearWallValidationError):mod.preview(x)


@pytest.mark.parametrize('missing', ['source_ref','approved_by'])
def test_missing_sources_and_reviewers_block(missing):
    x=sample();x['segments'][0][missing]=''
    assert_code(x,'SOURCE')


@pytest.mark.parametrize('bad', ['unreviewed','needs_detail','confirmed','zero'])
def test_group_status_incorrect_or_incomplete_denied(bad):
    x=sample();x['rebars']['vertical']['status']=bad
    if bad=='confirmed':
        del x['rebars']['vertical']['series']
    with pytest.raises(mod.ShearWallValidationError):mod.preview(x)


@pytest.mark.parametrize('case', [
 'duplicate_part_id','duplicate_physical_part','overlapping_parts','opening_outside','opening_overlap','opening_other_segment',
 'missing_face','same_face_twice','formwork_unreviewed','invalid_approved','contact_on_opening','contact_outside',
 'duplicate_contact','contact_overlap','unsupported_drawing','unsupported_unit','missing_coordinate','wrong_orientation',
 'unapproved_rebar','double_cut_method','no_cut_method','wrong_part_kind','no_straight','missing_unit_weight_ref',
 'non_total_count_scope','unexpected_bar_group','unapproved_na','nonapplicable_series','duplicate_face','contact_too_large',
 'foreign_datum_mismatch','foreign_wrong_owner','foreign_outside','foreign_opening','duplicate_foreign_id',
 'foreign_overlap','unrecognized_field','missing_edge_scope','edge_scope_unreviewed','edge_missing_ref',
 'face_no_reason','wrong_geometry_kind',
])
def test_adversarial_matrix(case):
    x=sample()
    p=x['segments'][0]
    f=x['formwork']
    g=x['rebars']['vertical']['series'][0]
    if case=='duplicate_part_id':x['segments'].append(deepcopy(p))
    if case=='duplicate_physical_part':q=part('P2',x='5');q['physical_part_id']='P1';x['segments'].append(q)
    if case=='overlapping_parts':x['segments'].append(part('P2',x='4'))
    if case=='opening_outside':x['openings'][0]['x_m']='4.5'
    if case=='opening_overlap':x['openings'].append(dict(id='O2',segment_id='P1',x_m='1.5',z_m='1.5',width_m='1',height_m='1',**source('O2')))
    if case=='opening_other_segment':x['openings'][0]['segment_id']='unknown'
    if case=='missing_face':f['main_faces'].pop()
    if case=='same_face_twice':f['main_faces'].append(face('F3',side='front'))
    if case=='formwork_unreviewed':f['status']='unreviewed'
    if case=='invalid_approved':f['approved_by']=''
    if case=='contact_on_opening':f['main_faces'][0]['contact_rectangles']=[dict(id='A',x_m='1',z_m='1',width_m='.2',height_m='.2',**source('C'))]
    if case=='contact_outside':f['main_faces'][0]['contact_rectangles']=[dict(id='A',x_m='5',z_m='1',width_m='.2',height_m='.2',**source('C'))]
    if case=='duplicate_contact':
        q=dict(id='A',x_m='2',z_m='1',width_m='.2',height_m='.2',**source('C'));f['main_faces'][0]['contact_rectangles']=[q,q]
    if case=='contact_overlap':
        q=dict(id='A',x_m='2',z_m='1',width_m='.5',height_m='.5',**source('C'));
        f['main_faces'][0]['contact_rectangles']=[q,dict(q,id='B',x_m='2.2')]
    if case=='unsupported_drawing':x['source']['mode']='drawing'
    if case=='unsupported_unit':x['source']['length_unit']='cm'
    if case=='missing_coordinate':x['datum']['coordinate_ref']=''
    if case=='wrong_orientation':x['datum']['orientation']='around_y'
    if case=='unapproved_rebar':x['rebars']['vertical']['status']='needs_review'
    if case=='double_cut_method':g['cut_length_m']='3.4'
    if case=='no_cut_method':del g['cut_parts']
    if case=='wrong_part_kind':g['cut_parts'][0]['kind']='made_up_hook'
    if case=='no_straight':g['cut_parts'][0]['kind']='hook'
    if case=='missing_unit_weight_ref':g['unit_weight_source']=''
    if case=='non_total_count_scope':g['count_scope']='per_metre'
    if case=='unexpected_bar_group':x['rebars']['new_group']=na('new')
    if case=='unapproved_na':x['rebars']['crossties']['reason']=''
    if case=='nonapplicable_series':x['rebars']['crossties']['series']=[]
    if case=='duplicate_face':f['main_faces'][1]['id']='Ffront'
    if case=='contact_too_large':f['main_faces'][0]['contact_rectangles']=[dict(id='A',x_m='0',z_m='0',width_m='5',height_m='3',**source('C'))]
    if case=='missing_edge_scope':del f['edge_scope']
    if case=='edge_scope_unreviewed':f['edge_scope']['status']='unreviewed'
    if case=='edge_missing_ref':f['edge_faces'].append(dict(id='Side',physical_face_id='SIDE',segment_id='P1',kind='left_end',status='formed',start_m='0',end_m='3',payment_ref='مصنوعی:صورتجلسه قالب',**source('')))
    if case=='face_no_reason':f['main_faces'][0]['status']='not_required'
    if case=='wrong_geometry_kind':p['shape']='arbitrary_polygon'
    if case.startswith('foreign_') or case=='duplicate_foreign_id':
        j=dict(id='I1',segment_id='P1',foreign_member_id='B1',x_m='3',y_m='.1',z_m='0',width_m='.5',depth_m='.05',height_m='1',deduction_owner='shear_wall',common_datum_ref='CS1',**source('inter'))
        x['interfaces'].append(j)
        if case=='foreign_datum_mismatch':j['common_datum_ref']='bad'
        if case=='foreign_wrong_owner':j['deduction_owner']='foreign'
        if case=='foreign_outside':j['x_m']='5.1'
        if case=='foreign_opening':j.update(x_m='1',z_m='1')
        if case=='duplicate_foreign_id':x['interfaces'].append(deepcopy(j))
        if case=='foreign_overlap':x['interfaces'].append(dict(j,id='I2',x_m='3.1'))
    if case=='unrecognized_field':x['extra']='silent_data'
    with pytest.raises(mod.ShearWallValidationError):mod.preview(x)


def edge_dict(ident,kind,start,end,*,segment_id='P1',opening_id=None,jamb_side=None,status='formed'):
    item=dict(id=ident,physical_face_id=ident,segment_id=segment_id,kind=kind,status=status,
              start_m=start,end_m=end,payment_ref='صورتجلسه مصنوعی پرداخت قالب',**source('edge/'+ident))
    if opening_id is not None:item['opening_id']=opening_id
    if jamb_side is not None:item['jamb_side']=jamb_side
    if status=='not_required':item['reason']='تماس مستند طبق جزئیات مصنوعی'
    return item


def test_opening_jamb_verified_length_times_thickness():
    x=sample()
    x['formwork']['edge_faces']=[edge_dict('J1','opening_jamb','0','1',opening_id='O1',jamb_side='left'),
                                 edge_dict('J2','opening_jamb','0','1',opening_id='O1',jamb_side='right')]
    r=mod.preview(x)
    assert r['totals']['payable_edge_formwork_m2']=='0.5'
    assert r['totals']['payable_formwork_m2']=='28.5'


def test_partial_edge_and_adjacent_nonoverlap():
    x=sample();x['formwork']['edge_faces']=[edge_dict('R1','right_end','0','1'),edge_dict('R2','right_end','1','3')]
    assert mod.preview(x)['totals']['payable_edge_formwork_m2']=='0.75'


@pytest.mark.parametrize('case', ['outside','interval_overlap','missing_payment','missing_scope_payment',
                                    'missing_jamb_source','jamb_missing_side','jamb_wrong_opening','jamb_to_long',
                                    'boundary_jamb','touching_opening_edge','shared_edge','duplicate_physical_edge',
                                    'external_same_wall','duplicate_external_source','missing_payment_approval'])
def test_formwork_bounds_and_provenance(case):
    x=sample();es=x['formwork']['edge_faces'];fw=x['formwork']
    if case=='outside':es.append(edge_dict('E','right_end','0','4'))
    if case=='interval_overlap':es.extend([edge_dict('E1','right_end','0','2'),edge_dict('E2','right_end','1','3')])
    if case=='missing_payment':fw['main_faces'][0]['payment_ref']=''
    if case=='missing_scope_payment':fw['payment_scope_ref']=''
    if case=='missing_payment_approval':fw['payment_approved_by']=''
    if case=='missing_jamb_source':
        q=edge_dict('J','opening_jamb','0','1',opening_id='O1',jamb_side='left');q['source_ref']='';es.append(q)
    if case=='jamb_missing_side':es.append(edge_dict('J','opening_jamb','0','1',opening_id='O1'))
    if case=='jamb_wrong_opening':es.append(edge_dict('J','opening_jamb','0','1',opening_id='O2',jamb_side='left'))
    if case=='jamb_to_long':es.append(edge_dict('J','opening_jamb','0','2',opening_id='O1',jamb_side='left'))
    if case=='boundary_jamb':
        x['openings'][0]['x_m']='0';es.append(edge_dict('J','opening_jamb','0','1',opening_id='O1',jamb_side='left'))
    if case=='touching_opening_edge':
        x['openings'][0].update(x_m='0',z_m='1');es.append(edge_dict('J','left_end','1','2'))
    if case=='shared_edge':
        x['segments'].append(part('P2',x='5',length='2'))
        fw['main_faces'].extend([face('P2front','P2','front'),face('P2back','P2','back')]);es.append(edge_dict('J','right_end','0','3'))
    if case=='duplicate_physical_edge':
        es.extend([edge_dict('E1','right_end','0','1'),edge_dict('E1','right_end','1','2')])
    if case=='external_same_wall':
        x['interfaces']=[dict(id='C',segment_id='P1',foreign_member_id='SW01',
             x_m='3',y_m='.1',z_m='0',width_m='.5',depth_m='.05',height_m='1',
             deduction_owner='shear_wall',common_datum_ref='CS1',**source('C'))]
    if case=='duplicate_external_source':
        old=mod.preview(x);key=next(k for k in old['physical_claims'] if ':source:' in k)
        with pytest.raises(mod.ShearWallValidationError):mod.preview(x,existing_claims={key})
        return
    with pytest.raises(mod.ShearWallValidationError):mod.preview(x)


def test_persian_digits_normalize_rebar_physical_claims():
    x=sample()
    x['rebars']['vertical']['series'][0]['physical_bar_set_id']='V۱'
    a=mod.preview(x)
    assert 'p:l1:bar:v1' in a['physical_claims']


def test_high_precision_large_valid_values_still_exact():
    x=sample();x['segments'][0].update(length_m='1234567890.123456789012345',height_m='1.000000000000001',thickness_m='0.123456789012345678')
    x['openings'][0].update(x_m='0',z_m='0',width_m='0.111111111111111111',height_m='0.111111111111111111')
    r=mod.preview(x)
    # Independent rational reference: default Decimal precision would round here.
    rational = lambda text: Fraction(Decimal(text))
    gross = rational(x['segments'][0]['length_m']) * rational(x['segments'][0]['height_m']) * rational(x['segments'][0]['thickness_m'])
    deduction = rational(x['openings'][0]['width_m']) * rational(x['openings'][0]['height_m']) * rational(x['segments'][0]['thickness_m'])
    assert Fraction(d(r['totals']['gross_concrete_m3'])) == gross
    assert Fraction(d(r['totals']['net_concrete_m3'])) == gross - deduction
