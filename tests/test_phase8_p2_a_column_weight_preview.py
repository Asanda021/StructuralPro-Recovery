"""Synthetic checks: weights are explicitly assumed and never payable."""
import json
from decimal import Decimal
import pytest

from core.drawings.pdf_column_weight_preview import (draft_component_weight_preview,
    write_weight_preview, export_weight_preview_xlsx)


def schedule():
    return {'status':'DRAFT_COMPLETE_GRID_EVIDENCE', 'document_sha256':'abc',
            'plan_page':14,'grid_node_count':15,'draft_extended_length_total_m':'169.70',
            'groups':[{'type_tag':'C1','grid_location_candidates':11,'printed_type_length_m':'10.70',
                       'draft_extended_length_m':'117.70'},
                      {'type_tag':'C2','grid_location_candidates':2,'printed_type_length_m':'14.00',
                       'draft_extended_length_m':'28.00'},
                      {'type_tag':'C3','grid_location_candidates':2,'printed_type_length_m':'12.00',
                       'draft_extended_length_m':'24.00'}],
            'rows':[{'candidate_id':'synthetic','grid_row':1,'grid_column':1,'plan_page':14,
                     'type_tag':'C1','x_pt':2,'y_pt':3,'status':'DRAFT_TYPE_LENGTH_CANDIDATE'}]}


def scenarios():
    return {x:{'profile_name':'IPE16 hypothetical','profile_count':'2','profile_unit_mass_kg_m':'15.8'}
            for x in ['C1','C2','C3']}


def test_realistic_column_profile_example_is_math_only():
    r=draft_component_weight_preview(schedule(),scenarios())
    assert Decimal(r['draft_weight_total_kg'])==Decimal('5362.52')
    assert Decimal(r['profile_mass_total_kg'])==Decimal('5362.52')
    assert r['status']=='DRAFT_SCENARIO_COMPLETE'
    assert not r['approved'] and not r['financially_payable']
    assert all(not x['approved'] and not x['financially_payable'] for x in r['groups'])


def test_missing_scenario_never_infers_weight():
    r=draft_component_weight_preview(schedule(),{'C1':scenarios()['C1']})
    assert r['status']=='DRAFT_SCENARIO_PARTIAL'
    assert r['groups'][1]['estimated_total_kg'] is None


def test_plate_weight_is_explicit_volume_times_density():
    specs=scenarios();specs['C1'].update(plate_count=2,plate_length_mm=200,plate_width_mm=100,
                                          plate_thickness_mm=10,steel_density_kg_m3=7850)
    r=draft_component_weight_preview(schedule(),specs)
    assert Decimal(r['plate_mass_total_kg'])==Decimal('34.54')


@pytest.mark.parametrize('bad', ['NaN','Infinity','-1','',True,'1,000'])
def test_invalid_unit_weight_fails_closed(bad):
    specs=scenarios();specs['C1']['profile_unit_mass_kg_m']=bad
    with pytest.raises(ValueError):draft_component_weight_preview(schedule(),specs)


def test_plate_count_without_dimensions_fails_closed():
    specs=scenarios();specs['C1']['plate_count']='2'
    with pytest.raises(ValueError):draft_component_weight_preview(schedule(),specs)


def test_non_reviewed_source_schedule_is_blocked():
    s=schedule();s['status']='BLOCKED_NON_UNIQUE_COLUMN_TYPE_PLAN'
    with pytest.raises(ValueError):draft_component_weight_preview(s,scenarios())


def test_export_preserves_nonfinancial_status(tmp_path):
    s=schedule();r=draft_component_weight_preview(s,scenarios())
    j=tmp_path/'weights.json';c=tmp_path/'weights.csv';x=tmp_path/'weights.xlsx'
    write_weight_preview(r,json_path=j,csv_path=c)
    export_weight_preview_xlsx(s,r,x)
    assert json.loads(j.read_text())['approved'] is False
    assert 'financially_payable' in c.read_text(encoding='utf-8-sig')
    assert x.exists() and x.stat().st_size>1500

def test_xlsx_contains_live_formulas_and_does_not_execute_label_text(tmp_path):
    from openpyxl import load_workbook

    source = schedule()
    source['rows'][0].update(source_operator_ids=['PDF001:p14:d7:s2'], detail_page=19,
                             printed_dimension_text='L=10.70 m', printed_length_bbox_pt=[2, 4, 8, 11])
    inputs = scenarios()
    inputs['C1']['profile_name'] = '=1+1'
    output = tmp_path / 'متره.xlsx'
    export_weight_preview_xlsx(source, draft_component_weight_preview(source, inputs), output)
    with output.open('rb') as stream:
        book = load_workbook(stream, data_only=False)
        try:
            types = book['Types']
            positions = book['PDF positions']
            assert types['D2'].value == '=B2*C2'
            assert types['F2'].value == 15.8 and types['F2'].data_type == 'n'
            assert types['Q2'].value == '=1+1' and types['Q2'].data_type == 's'
            assert book['Preview']['B11'].value == '=SUM(Types!O2:O4)'
            assert book['Preview']['C11'].value == 5362.52
            assert 'PDF001:p14:d7:s2' in positions['K2'].value
            assert positions['L2'].value == 19 and positions['M2'].value == 'L=10.70 m'
        finally:
            book.close()
