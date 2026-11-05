"""Public synthetic tests; no source DWG coordinates or handles."""
import pytest
import ezdxf
from core.drawings.dwg_dimension_unit_ambiguity import audit_dxf_dimension_annotation_ratios


def _synthetic():
    d=ezdxf.new('R2018')
    d.header['$INSUNITS']=0
    m=d.modelspace()
    pairs=[(7.7,'770'),(3.72,'372'),(0.5,'5'),(2.0,'<auto>'),(2.0,'50cm'),(3.2,'3.20')]
    for length,label in pairs:
        dimension=m.add_linear_dim(base=(0,2),p1=(0,0),p2=(length,0),angle=0).dimension
        dimension.dxf.text='' if label=='<auto>' else label
    return d


def test_mixed_numeric_dimension_annotations_do_not_infer_any_original_units():
    result=audit_dxf_dimension_annotation_ratios(_synthetic())
    assert result['dimension_total']==6
    assert result['numeric_override_text']==4
    assert result['automatic_or_placeholder_text']==1
    assert result['nonnumeric_override_text']==1
    assert result['nonnumeric_text_with_unit_token']==1
    assert result['annotation_ratio_near_100']==2
    assert result['annotation_ratio_near_10']==1
    assert result['annotation_ratio_near_1']==1
    assert result['annotation_ratio_outside_selected_bands']==0
    assert result['multiple_annotated_ratio_bands_observed'] is True
    assert result['inferred_original_dwg_unit'] is None
    assert result['geometry_approved_for_financial_takeoff'] is False
    assert result['financial_quantities_approved']==0
    assert all(not isinstance(v,(list,tuple,dict)) for v in result.values())


def test_uniform_100_override_does_not_authorize_centimetres():
    d=ezdxf.new('R2018');d.header['$INSUNITS']=0
    e=d.modelspace().add_linear_dim(base=(0,2),p1=(0,0),p2=(1,0),angle=0).dimension
    e.dxf.text='100'
    r=audit_dxf_dimension_annotation_ratios(d)
    assert r['annotation_ratio_near_100']==1
    assert r['inferred_original_dwg_unit'] is None
    assert r['source_dwg_dimstyle_and_units_independently_verified'] is False


def test_number_with_unit_is_not_parsed_as_geometry():
    d=ezdxf.new('R2018');d.header['$INSUNITS']=0
    e=d.modelspace().add_linear_dim(base=(0,2),p1=(0,0),p2=(1,0),angle=0).dimension
    e.dxf.text='150cm'
    r=audit_dxf_dimension_annotation_ratios(d)
    assert r['nonnumeric_text_with_unit_token']==1
    assert r['numeric_override_text']==0
    assert not r['dxf_dimension_label_is_authoritative_measurement']


@pytest.mark.parametrize('tol', [0, -1, float('inf'),float('nan'), 0.5,True, '0.01'])
def test_invalid_tolerance_rejected(tol):
    with pytest.raises(ValueError): audit_dxf_dimension_annotation_ratios(_synthetic(),ratio_tolerance=tol)


def test_converted_no_dimensions_does_not_claim_source_evidence():
    d=ezdxf.new('R2018')
    with pytest.raises(ValueError, match='No measurable'):
        audit_dxf_dimension_annotation_ratios(d)


def test_dimension_blocks_distinguished_from_modelspace():
    d=ezdxf.new('R2018');d.header['$INSUNITS']=0
    a=d.modelspace().add_linear_dim(base=(0,2),p1=(0,0),p2=(1,0),angle=0).dimension
    a.dxf.text='100'
    b=d.blocks.new('PART').add_linear_dim(base=(0,2),p1=(0,0),p2=(1,0),angle=0).dimension
    b.dxf.text='10'
    r=audit_dxf_dimension_annotation_ratios(d)
    assert r['dimension_total']==2
    assert r['direct_modelspace_dimension']==1
    assert r['outside_direct_modelspace_dimension']==1
