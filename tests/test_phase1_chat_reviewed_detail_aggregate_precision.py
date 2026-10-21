"""Read-only, source-backed reviewed-detail regression on loss of small paid parts.

Uses explicit synthetic dimensional fixtures; no real engineering certification.
"""
import pytest
from core.takeoff.reviewed_detail_calculators import calculate_reviewed_detail


def row(name, **fields):
    return dict(id=name, source_ref=f'SYNTHETIC-DOC-{name}', approved_by='SyntheticReviewer', **fields)


@pytest.mark.parametrize('kind,rows', [
    ('net_surface', [row('F1', count='1', length_m='1e16', width_m='1', openings_m2='1')]),
    ('concrete_regions', [row('R1', length_m='1e16', width_m='1', thickness_m='1',
        voids=[dict(id='V1', volume_m3='1', source_ref='SYNTHETIC-VOID',approved_by='Reviewer')])]),
    ('rectangle_volume', [row('A', count='1', length_m='1e16',width_m='1', thickness_m='1'),
                          row('B', count='1', length_m='1',width_m='1', thickness_m='1')]),
    ('concrete_regions', [row('R1', length_m='2e16', width_m='1', thickness_m='1',
        voids=[dict(id='V1',volume_m3='1e16',source_ref='DOC-A', approved_by='Reviewer'),
               dict(id='V2',volume_m3='1',source_ref='DOC-B',approved_by='Reviewer')])]),
])
def test_missing_nonzero_deduction_or_component_must_fail_closed(kind, rows):
    with pytest.raises(ValueError):
        calculate_reviewed_detail(kind, {'entries': rows})


@pytest.mark.parametrize('kind,rows,expected,unit', [
    ('net_surface', [row('F1',count='1',length_m='4',width_m='3',openings_m2='2')],10.,'m2'),
    ('concrete_regions', [row('R1',length_m='2',width_m='3',thickness_m='2',
         voids=[dict(id='V1',volume_m3='2',source_ref='DOC-A',approved_by='Reviewer')])],10.,'m3'),
    ('rectangle_volume', [row('A',count='1',length_m='2',width_m='1',thickness_m='1'),
                          row('B',count='1',length_m='3',width_m='1',thickness_m='1')],5.,'m3'),
    ('steel_profile_schedule', [row('P',count='2',length_m='3',unit_weight_kg_m='4.5',
         unit_weight_source='SYNTHETIC-CATALOG')],27.,'kg'),
    ('piece_schedule', [row('P',count='3',spec_ref='SYNTHETIC-PART')],3.,'عدد'),
    ('concrete_regions', [row('R1',length_m='2',width_m='3',thickness_m='2',voids=[])],12.,'m3'),
])
def test_existing_valid_specialist_quantities_are_unchanged(kind,rows,expected,unit):
    output=calculate_reviewed_detail(kind, {'entries': rows})
    assert output['quantity']==pytest.approx(expected) and output['unit']==unit


def test_negative_or_excessive_deduction_remains_rejected():
    rows=[row('F',count='1',length_m='2',width_m='2',openings_m2='5')]
    with pytest.raises(ValueError):calculate_reviewed_detail('net_surface',{'entries':rows})
