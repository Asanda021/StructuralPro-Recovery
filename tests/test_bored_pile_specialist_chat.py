"""Synthetic bored pile, negative inputs, evidence, precision, physical identity."""
import json
from pathlib import Path
from decimal import Decimal, localcontext, Context
from copy import deepcopy
import pytest
from core.takeoff.bored_pile_specialist_chat import compile_piles, PileInputError, PI, GROUPS

REFERENCE = Path(__file__).resolve().parents[1]/'examples/bored_pile_documented_synthetic.json'

def sample():
    return json.loads(REFERENCE.read_text(encoding='utf-8'))

def test_theoretical_volume_with_explicit_datum_and_pi():
    d=sample(); r=compile_piles(d)
    with localcontext(Context(prec=256)):
        expected=PI * Decimal('0.8')**2 / 4 * Decimal('11.25')
    assert Decimal(r['totals']['m3']) == expected
    assert r['totals']['m2']=='0' and Decimal(r['totals']['kg'])==Decimal('8')*Decimal('12.2')*Decimal('1.58')+Decimal('80.125')*Decimal('.395')
    assert r['rows'][0]['evidence']['pi_used']==str(PI)
    assert len(r['rows'])==3 and {x['unit'] for x in r['rows']}=={'m3','kg'}


def test_no_mutation_and_deterministic_digest():
    d=sample(); old=deepcopy(d)
    a=compile_piles(d);b=compile_piles(d)
    assert d==old and a==b
    assert len(a['source_sha256'])==64


def test_explicit_approved_deduction_and_net_not_gross_payable():
    d=sample();p=d['piles'][0]
    p['interface']['ownership_status']='documented_deductions'
    p['deductions']=[dict(id='CAP-OV1',other_physical_id='cap-physical-01',owner='other_member',volume_m3='0.01000000000000000000001',source_ref='synthetic cap joint',approved_by='JointAuthor')]
    r=compile_piles(d)
    with localcontext(Context(prec=256)):
        expected=PI*Decimal('.8')**2/4*Decimal('11.25')-Decimal('.01000000000000000000001')
    assert Decimal(r['totals']['m3']) == expected
    assert r['rows'][0]['evidence']['deductions_m3']=='0.01000000000000000000001'


def test_separate_physical_piles_no_count_assumptions():
    d=sample();q=deepcopy(d['piles'][0]);q['id']='BP2';q['physical_id']='pile-physical-02'
    for group in GROUPS:
        if q['rebars'][group]['status']=='confirmed':
            for bar in q['rebars'][group]['series']:bar['physical_id'] += '-2'
    d['piles'].append(q)
    r=compile_piles(d)
    with localcontext(Context(prec=256)):
        expected=2*Decimal(compile_piles(sample())['totals']['m3'])
    assert Decimal(r['totals']['m3'])==expected
    assert len(r['physical_claims'])==2


def test_formwork_requires_faces_not_drilling_assumptions():
    d=sample();d['piles'][0]['formwork']={'status':'documented','faces':[dict(id='liner1',physical_id='face-liner-1',net_area_m2='1.125',source_ref='synthetic liner')],'approved_by':'FormworkAuthor'}
    r=compile_piles(d)
    assert r['totals']['m2']=='1.125'
    assert any(x['kind']=='formwork' for x in r['rows'])


def test_large_decimal_precision_is_kept():
    d=sample();d['piles'][0]['rebars']['longitudinal']['series'][0]['unit_weight_kg_m']='1.58000000000000000000000001'
    r=compile_piles(d)
    with localcontext(Context(prec=256)):
        expected=Decimal('8')*Decimal('12.2')*Decimal('1.58000000000000000000000001')+Decimal('80.125')*Decimal('.395')
    assert Decimal(r['totals']['kg']) == expected


@pytest.mark.parametrize('fault',[
    'bad_policy','missing_pile','missing_source','missing_datum','bad_top','reverse_levels','equal_levels',
    'zero_diameter','negative_diameter','float_diameter','nan','infinity','bool_diameter','bad_geometry',
    'bad_concrete','wrong_mix','wrong_interface','cap_overlap_without_deduction','no_overlap_with_deduction',
    'duplicate_pile','duplicate_physical','bad_rebars','missing_group','unreviewed_group','empty_series',
    'zero_count','fraction_count','negative_unit_mass','float_mass','duplicate_bar','missing_cut_ref',
    'bad_formwork','empty_formwork','duplicate_formwork','duplicate_deduction','overdeduction','missing_deduction_ref',
    'deduction_self_owner','deduction_owner_wrong','missing_pile_cap','unexpected_field','no_geometry_approval',
    'float_elevation','missing_approval'])
def test_fail_closed(fault):
    d=sample();p=d['piles'][0]
    cut=dict(id='CUT1',other_physical_id='CAP1',owner='other_member',volume_m3='.01',source_ref='synthetic-cut',approved_by='Reviewer')
    if fault=='bad_policy':d['policy']='wrong'
    elif fault=='missing_pile':d['piles']=[]
    elif fault=='missing_source':d['source']['source_id']=''
    elif fault=='missing_datum':d['datum'].pop('vertical_datum_ref')
    elif fault=='bad_top':p['top_elevation_m']='X'
    elif fault=='reverse_levels':p['top_elevation_m']='-15'
    elif fault=='equal_levels':p['top_elevation_m']=p['bottom_elevation_m']
    elif fault=='zero_diameter':p['diameter_m']='0'
    elif fault=='negative_diameter':p['diameter_m']='-1'
    elif fault=='float_diameter':p['diameter_m']=.8
    elif fault=='nan':p['diameter_m']='NaN'
    elif fault=='infinity':p['diameter_m']='Infinity'
    elif fault=='bool_diameter':p['diameter_m']=True
    elif fault=='bad_geometry':p['geometry']['other']='fake'
    elif fault=='bad_concrete':p['concrete']['status']='unknown'
    elif fault=='wrong_mix':p['concrete']['mix_ref']=''
    elif fault=='wrong_interface':p['interface']['ownership_status']='approved_by_software'
    elif fault=='cap_overlap_without_deduction':p['interface']['ownership_status']='documented_deductions'
    elif fault=='no_overlap_with_deduction':p['interface']['ownership_status']='documented_no_overlap';p['deductions']=[cut]
    elif fault=='duplicate_pile':d['piles'].append(deepcopy(p))
    elif fault=='duplicate_physical':q=deepcopy(p);q['id']='NEW';d['piles'].append(q)
    elif fault=='bad_rebars':p['rebars']='NONE'
    elif fault=='missing_group':p['rebars'].pop('starters')
    elif fault=='unreviewed_group':p['rebars']['longitudinal']['status']='unreviewed'
    elif fault=='empty_series':p['rebars']['longitudinal']['series']=[]
    elif fault=='zero_count':p['rebars']['longitudinal']['series'][0]['count']='0'
    elif fault=='fraction_count':p['rebars']['longitudinal']['series'][0]['count']='3.2'
    elif fault=='negative_unit_mass':p['rebars']['longitudinal']['series'][0]['unit_weight_kg_m']='-.4'
    elif fault=='float_mass':p['rebars']['longitudinal']['series'][0]['unit_weight_kg_m']=1.58
    elif fault=='duplicate_bar':p['rebars']['spiral_ties']['series'][0]['physical_id']=p['rebars']['longitudinal']['series'][0]['physical_id']
    elif fault=='missing_cut_ref':p['rebars']['longitudinal']['series'][0]['cut_length_ref']=''
    elif fault=='bad_formwork':p['formwork']['status']='undocumented'
    elif fault=='empty_formwork':p['formwork']={'status':'documented','faces':[],'approved_by':'X'}
    elif fault=='duplicate_formwork':p['formwork']={'status':'documented','faces':[dict(id='a',physical_id='f',net_area_m2='1',source_ref='A'),dict(id='b',physical_id='f',net_area_m2='2',source_ref='B')],'approved_by':'X'}
    elif fault=='duplicate_deduction':p['deductions']=[cut,cut]
    elif fault=='overdeduction':p['deductions']=[{**cut,'volume_m3':'1000'}]
    elif fault=='missing_deduction_ref':p['deductions']=[{**cut,'source_ref':''}]
    elif fault=='deduction_self_owner':p['deductions']=[{**cut,'other_physical_id':p['physical_id']}]
    elif fault=='deduction_owner_wrong':p['deductions']=[{**cut,'owner':'pile'}]
    elif fault=='missing_pile_cap':p['interface']['pile_cap_id']=''
    elif fault=='unexpected_field':p['waste_percentage']='0.03'
    elif fault=='no_geometry_approval':p['geometry']['approved_by']=''
    elif fault=='float_elevation':p['top_elevation_m']=-1.25
    elif fault=='missing_approval':p['rebars']['longitudinal']['approved_by']=''
    with pytest.raises(PileInputError):compile_piles(d)

@pytest.mark.parametrize('quantity',[
    '0.0000000000000000000000000000000000000000000000000000000000001',
    '1234567890123456789012345678901234567890123456789012345678901',
    '1E+61','1E-61',
])
def test_beyond_documented_decimal_numeric_contract_is_blocked(quantity):
    data=sample();data['piles'][0]['diameter_m']=quantity
    with pytest.raises(PileInputError):compile_piles(data)


def test_no_excavation_or_casing_is_automatically_generated():
    result=compile_piles(sample())
    assert all(row['kind'] not in {'excavation','casing','overpour','grout','spoil'} for row in result['rows'])
    assert 'حفاری' in result['limit']


def test_linear_metre_material_not_guessed_from_helix_pitch():
    data=sample()
    s=data['piles'][0]['rebars']['spiral_ties']['series'][0]
    del s['cut_length_m']
    s['pitch_m']='0.2'
    with pytest.raises(PileInputError):compile_piles(data)
