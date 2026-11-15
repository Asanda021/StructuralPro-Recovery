"""P8/P2-A: conditional steel component matching, never source approval."""
from copy import deepcopy
import pytest
from core.drawings.pdf_column_profile_reconcile import reconcile_column_profile_components


def nodes(per_type=None):
    counts=per_type or {'C1':11,'C2':2,'C3':2}
    out=[];i=0
    for tag,n in counts.items():
        for _ in range(n):
            i+=1
            out.append(dict(candidate_id=f'PDF001:p14:r{i}:c1',document_id='PDF001',
               page=14,suggested_type=tag,status='GRID_LOCATION_VECTOR_TYPE_CANDIDATE',
               vector_type_label_evidence=dict(tag=tag,status='PROPOSED_UNVERIFIED'),
               independent_axis_grid_witness=dict(axis_document_id='PDF001',axis_page=13,
                   status='PROPOSED_INDEPENDENT_GRID_REGISTRATION'),
               cross_sheet_type_reference=dict(tag=tag,status='PROPOSED_UNVERIFIED',
                   details=[dict(document_id='PDF001',page=19,dimension_kind='length',
                       dimension_m={'C1':'10.70','C2':'14.00','C3':'12.00'}[tag])]),
               type_verified=False,financially_payable=False))
    return out


def specs():
    return [dict(tag=tag,profile='IPE16',profiles_per_symbol=2,
            length_m=length,document_id='PDF001',page=19,
            evidence_kind='VISUALLY_REVIEWED_PDF_DETAIL')
            for tag,length in [('C1','10.70'),('C2','14.00'),('C3','12.00')]]


def ref():
    return [dict(tag=tag,profile='IPE16',profile_piece_count=pcount,
            length_m=length,unit_mass_kg_per_m='15.80',reported_mass_kg=total,
            document_id='REF001',page=20,workbook_anchor=f'MFX1:S16:{tag}')
            for tag,pcount,length,total in [
                ('C1',22,'10.70','3719.32'),('C2',4,'14.00','884.80'),
                ('C3',4,'12.00','758.40')]]


def test_profile_factor_two_is_supported_by_detail_and_reference_not_floors():
    r=reconcile_column_profile_components(nodes(),specs(),ref())
    assert r['summary']=={'DOCUMENT_COMPONENT_ARITHMETIC_MATCH_UNVERIFIED':3}
    assert {x['tag']:x['expected_piece_count'] for x in r['rows']}=={'C1':22,'C2':4,'C3':4}
    assert {x['tag']:x['independent_arithmetic_kg'] for x in r['rows']}=={
        'C1':'3719.32','C2':'884.80','C3':'758.40'}
    assert all(x['section_piece_multiplier']==2 for x in r['rows'])
    assert all(not x['approved'] and not x['member_identity_approved']
               and not x['financially_payable'] for x in r['rows'])
    assert r['approved_financial_rows']==0 and r['physical_member_count'] is None
    assert r['floor_repetition_multiplier'] is None and r['complete'] is False


def test_reference_cannot_supply_missing_multiplier():
    x=specs();x[0].pop('profiles_per_symbol')
    r=reconcile_column_profile_components(nodes(),x,ref())
    assert r['summary']['BLOCKED_MISSING_EVIDENCE']==1
    assert r['invalid'][0]['side']=='section'
    assert r['approved_financial_rows']==0


def test_reference_count_never_forces_double_profile_inference():
    x=specs();x[0]['profiles_per_symbol']=1
    r=reconcile_column_profile_components(nodes(),x,ref())
    assert r['rows'][0]['expected_piece_count']==11
    assert r['rows'][0]['status']=='BLOCKED_PROFILE_PIECE_COUNT'


def test_false_reported_weight_rejected():
    x=ref();x[1]['reported_mass_kg']='885.80'
    r=reconcile_column_profile_components(nodes(),specs(),x)
    assert next(x for x in r['rows'] if x['tag']=='C2')['status']=='BLOCKED_PROFILE_WEIGHT_MISMATCH'


def test_changed_length_requires_source_evidence():
    x=specs();x[2]['length_m']='12.50'
    r=reconcile_column_profile_components(nodes(),x,ref())
    assert next(y for y in r['rows'] if y['tag']=='C3')['status']=='BLOCKED_DETAIL_IDENTITY_OR_LENGTH'


def test_duplicate_position_identity_rejected():
    x=nodes();x.append(deepcopy(x[0]))
    r=reconcile_column_profile_components(x,specs(),ref())
    assert r['invalid'][0]['status']=='BLOCKED_INVALID_PLAN_WITNESS'
    assert 'duplicate' in r['invalid'][0]['reason']
    assert r['approved_financial_rows']==0


def test_second_column_sheet_not_doubled_as_second_floor():
    x=nodes();extra=deepcopy(x[0]);extra.update(candidate_id='PDF001:p15:r1:c1',page=15)
    x.append(extra)
    r=reconcile_column_profile_components(x,specs(),ref())
    assert r['summary']['BLOCKED_MULTIPLE_OR_MISSING_COLUMN_PLAN_SHEETS']==3
    assert not r['complete']


def test_invalid_axis_or_glyph_witness_cannot_count():
    for field in ('independent_axis_grid_witness','vector_type_label_evidence',
                  'cross_sheet_type_reference'):
        x=nodes();x[0].pop(field)
        r=reconcile_column_profile_components(x,specs(),ref())
        assert r['invalid'][0]['status']=='BLOCKED_INVALID_PLAN_WITNESS'
        assert r['approved_financial_rows']==0


def test_different_axis_source_invalidates_location():
    x=nodes();x[0]['independent_axis_grid_witness']['axis_document_id']='PDF999'
    r=reconcile_column_profile_components(x,specs(),ref())
    assert 'distinct sheet' in r['invalid'][0]['reason']


def test_phony_approval_flags_are_not_new_source_evidence():
    x=nodes();x[0]['financially_payable']=True
    r=reconcile_column_profile_components(x,specs(),ref())
    assert r['invalid'][0]['status']=='BLOCKED_INVALID_PLAN_WITNESS'


def test_untrusted_decimal_inputs_and_negative_mass_fail_closed():
    for bad in ('1,580','-1','nan','inf',True,None):
        x=ref();x[0]['unit_mass_kg_per_m']=bad
        r=reconcile_column_profile_components(nodes(),specs(),x)
        assert r['invalid'][0]['side']=='reference'
        assert r['approved_financial_rows']==0


def test_missing_reference_blocks_selected_type_only():
    x=ref()[1:]
    r=reconcile_column_profile_components(nodes(),specs(),x)
    assert next(y for y in r['rows'] if y['tag']=='C1')['status']=='BLOCKED_MISSING_EVIDENCE'
    assert r['matched_component_type_rows']==2


def test_duplicate_reference_type_blocks_not_average():
    x=ref();x.append(deepcopy(x[0]))
    r=reconcile_column_profile_components(nodes(),specs(),x)
    assert next(y for y in r['rows'] if y['tag']=='C1')['status']=='BLOCKED_MISSING_EVIDENCE'


def test_invalid_source_member_tag_rejected():
    x=nodes();x[0]['suggested_type']='UNKNOWN'
    r=reconcile_column_profile_components(x,specs(),ref())
    assert r['invalid'][0]['status']=='BLOCKED_INVALID_PLAN_WITNESS'


def test_empty_input_has_no_pass_or_financial_promotion():
    r=reconcile_column_profile_components([],[],[])
    assert r['matched_component_type_rows']==0 and r['rows']==[]
    assert r['approved_financial_rows']==0 and r['complete'] is False