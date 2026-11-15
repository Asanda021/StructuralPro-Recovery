"""Synthetic, privacy-safe proof-chain tests for column locations in PDF drawings."""
from copy import deepcopy
from core.drawings.pdf_column_position_ledger import compile_column_position_ledger


def source():
    doc="PDF001"
    node={"candidate_id":f"{doc}:p14:r1:c1", "document_id":doc,"page":14,
          "row":1,"column":1,"x_pt":180.0,"y_pt":155.5,
          "column_context_candidate":True,
          "status":"GRID_LOCATION_VECTOR_TYPE_CANDIDATE",
          "symbol_status":"COMPACT_VECTOR_SYMBOL_CANDIDATE",
          "suggested_type":"C2",
          "vector_type_label_evidence":{"tag":"C2", "bbox_pt":[184,164,195,173]},
          "independent_axis_grid_witness":{"status":"PROPOSED_INDEPENDENT_GRID_REGISTRATION",
               "axis_document_id":doc,"axis_page":13,"axis_candidate_id":f"{doc}:p13:r1:c1"},
          "cross_sheet_type_reference":{"tag":"C2","status":"PROPOSED_UNVERIFIED",
               "details":[{"document_id":doc,"page":19,"dimension_kind":"length",
                           "dimension_m":"14.00","status":"PROPOSED_UNVERIFIED"}]}}
    return {"documents":[{"document_id":doc,"page_count":19}],
            "page_view_summaries":[
                {"document_id":doc,"page":13,"status":"EXPLICIT_SHEET_TITLE","sheet_kind":"axis_plan"},
                {"document_id":doc,"page":14,"status":"EXPLICIT_SHEET_TITLE","sheet_kind":"column_type_plan"}],
            "independent_axis_grid_registrations":[{
                "status":"PROPOSED_INDEPENDENT_GRID_REGISTRATION",
                "axis_plan":{"document_id":doc,"page":13},
                "column_plan":{"document_id":doc,"page":14}}],
            "grid_location_candidates":[node],
            "architectural_floor_plan_candidates":[
                {"document_id":doc,"page":1,"sheet_kind":"pilot_floor_plan"},
                {"document_id":doc,"page":2,"sheet_kind":"ground_floor_plan"},
                {"document_id":doc,"page":3,"sheet_kind":"first_floor_plan"}]}


def test_four_way_chain_still_not_column_quantity():
    r=compile_column_position_ledger(source())
    x=r['positions'][0]
    assert x['status']=='FOUR_WAY_DRAWING_EVIDENCE_CANDIDATE'
    assert x['axis_evidence']['page']==13
    assert x['type_detail_evidence']['page']==19
    assert x['type_detail_evidence']['type_detail_length_m']=='14.00'
    assert x['proposed_type']=='C2'
    assert r['per_sheet'][0]['type_label_position_candidates']=={'C2':1}
    assert x['physical_member_quantity'] is None
    assert x['floor_instances_verified'] is None
    assert not x['financially_payable'] and not r['complete']
    assert r['verified_total_physical_members'] is None


def test_three_architectural_floor_titles_do_not_triple_columns():
    r=compile_column_position_ledger(source())
    assert len(r['source_floor_plan_inventory'])==3
    assert r['floor_multiplier'] is None
    assert r['floor_repetition_evidence_status'].startswith('BLOCKED_')
    assert r['quantity_approval_count']==0


def test_missing_axis_registration_is_separate_blocker():
    data=source();data['independent_axis_grid_registrations']=[]
    assert compile_column_position_ledger(data)['positions'][0]['status']=='REVIEW_UNCORROBORATED_AXIS'


def test_fake_axis_same_page_cannot_verify():
    data=source();data['grid_location_candidates'][0]['independent_axis_grid_witness']['axis_page']=14
    assert compile_column_position_ledger(data)['positions'][0]['status']=='REVIEW_UNCORROBORATED_AXIS'


def test_missing_glyph_cannot_be_inferred_from_type_name():
    data=source();data['grid_location_candidates'][0]['vector_type_label_evidence']=None
    x=compile_column_position_ledger(data)['positions'][0]
    assert x['status']=='REVIEW_MISSING_OR_AMBIGUOUS_TYPE'
    assert x['proposed_type'] is None


def test_stroked_label_not_supported_other_sheet_never_counted():
    data=source();data['grid_location_candidates'][0]['page']=13
    assert compile_column_position_ledger(data)['positions']==[]


def test_missing_detail_still_keeps_type_but_not_boq():
    data=source();data['grid_location_candidates'][0]['cross_sheet_type_reference']=None
    x=compile_column_position_ledger(data)['positions'][0]
    assert x['status']=='REVIEW_MISSING_OR_CONFLICTING_DETAIL'
    assert x['proposed_type']=='C2'
    assert not x['financially_payable']


def test_conflicting_details_blocked():
    data=source();data['grid_location_candidates'][0]['cross_sheet_type_reference']['details'].append(
        {'document_id':'PDF001','page':19,'dimension_kind':'length','dimension_m':'10.70',
         'status':'PROPOSED_UNVERIFIED'})
    assert compile_column_position_ledger(data)['positions'][0]['status']=='REVIEW_MISSING_OR_CONFLICTING_DETAIL'


def test_wrong_document_detail_blocked():
    data=source();data['grid_location_candidates'][0]['cross_sheet_type_reference']['details'][0]['document_id']='PDF002'
    assert compile_column_position_ledger(data)['positions'][0]['status']=='REVIEW_MISSING_OR_CONFLICTING_DETAIL'


def test_invalid_or_nonpositive_detail_blocked():
    for val in ('-1','0','NaN','Infinity','junk'):
        data=source();data['grid_location_candidates'][0]['cross_sheet_type_reference']['details'][0]['dimension_m']=val
        assert compile_column_position_ledger(data)['positions'][0]['status']=='REVIEW_MISSING_OR_CONFLICTING_DETAIL'


def test_same_page_is_not_independent_detail():
    data=source();data['grid_location_candidates'][0]['cross_sheet_type_reference']['details'][0]['page']=14
    assert compile_column_position_ledger(data)['positions'][0]['status']=='REVIEW_MISSING_OR_CONFLICTING_DETAIL'


def test_duplicate_grid_identity_blocked_not_counted():
    data=source();data['grid_location_candidates'].append(deepcopy(data['grid_location_candidates'][0]))
    r=compile_column_position_ledger(data)
    assert len(r['positions'])==1 and r['invalid'][0]['status']=='BLOCKED_DUPLICATE_GRID_IDENTITY'


def test_coordinate_duplicate_different_id_blocked():
    data=source();duplicate=deepcopy(data['grid_location_candidates'][0]);duplicate['candidate_id']='PDF001:p14:r1:c2';duplicate['column']=2
    data['grid_location_candidates'].append(duplicate)
    r=compile_column_position_ledger(data)
    assert len(r['positions'])==1 and r['invalid'][0]['status']=='BLOCKED_DUPLICATE_GEOMETRY'


def test_source_page_out_of_bounds_blocked():
    data=source();data['grid_location_candidates'][0]['page']=20
    r=compile_column_position_ledger(data)
    assert not r['positions'] and r['invalid'][0]['status']=='BLOCKED_INVALID_POSITION_PROVENANCE'


def test_fake_confirmed_financial_flags_ignored():
    data=source();n=data['grid_location_candidates'][0]
    n.update(physical_member_verified=True,financially_payable=True,quantity=999,approved=True)
    r=compile_column_position_ledger(data)
    assert r['positions'][0]['physical_member_quantity'] is None
    assert not r['positions'][0]['approved'] and not r['positions'][0]['financially_payable']


def test_conflicting_sheet_classification_rejected():
    import pytest
    data=source(); data['page_view_summaries'].append({'document_id':'PDF001','page':14,'status':'EXPLICIT_SHEET_TITLE','sheet_kind':'axis_plan'})
    with pytest.raises(ValueError):compile_column_position_ledger(data)


def test_multiple_axis_registrations_fail_closed():
    data=source();data['independent_axis_grid_registrations'].append(deepcopy(data['independent_axis_grid_registrations'][0]))
    x=compile_column_position_ledger(data)['positions'][0]
    assert x['status']=='REVIEW_UNCORROBORATED_AXIS'


def test_type_summary_is_per_sheet_not_project_members():
    data=source();second=deepcopy(data['grid_location_candidates'][0]);second.update(candidate_id='PDF001:p14:r1:c2',column=2,x_pt=254.0,suggested_type='C1')
    second['vector_type_label_evidence']['tag']='C1';second['cross_sheet_type_reference']['tag']='C1'
    second['independent_axis_grid_witness']['axis_candidate_id']='PDF001:p13:r1:c2'
    data['grid_location_candidates'].append(second)
    r=compile_column_position_ledger(data)
    assert r['per_sheet'][0]['type_label_position_candidates']=={'C1':1,'C2':1}
    assert r['per_sheet'][0]['approved_physical_member_count'] is None
    assert r['verified_total_physical_members'] is None