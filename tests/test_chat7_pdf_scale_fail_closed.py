"""Reject guessed, non-finite and malformed PDF scale/distance inputs."""
import pytest
from core.drawings.pdf_takeoff import PDFTakeoffAdapter

@pytest.mark.parametrize('scale',[True,False,0,-1,float('nan'),float('inf'),'1:0',
                                   '1:100 1:50','drawing:1:100','1:-100','1:NaN','1:100garbage'])
def test_explicit_scale_only(scale):
    with pytest.raises(ValueError):
        PDFTakeoffAdapter.normalize_scale(scale)

@pytest.mark.parametrize('value',[-1,0,float('nan'),float('inf'),True])
def test_nonfinite_negative_or_zero_area_rejected(value):
    with pytest.raises(ValueError):
        PDFTakeoffAdapter().measure_area(value,'1:100')

@pytest.mark.parametrize('unit',['inch','pixel','','M'])
def test_unsupported_units_not_silently_treated_as_meter(unit):
    with pytest.raises(ValueError):
        PDFTakeoffAdapter().pixel_to_model(1,'1:100',unit)

@pytest.mark.parametrize('distance',[-1,0,True,float('nan'),float('inf')])
def test_invalid_distance_never_produces_payable_length(distance):
    with pytest.raises(ValueError):
        PDFTakeoffAdapter().pixel_to_model(distance,'1:100','cm')

@pytest.mark.parametrize('coords',[(0,0,0,0),(0,0,float('nan'),3),(-2,0,float('inf'),0)])
def test_invalid_line_coordinates_rejected(coords):
    with pytest.raises(ValueError):
        PDFTakeoffAdapter().measure_line(*coords,'1:100','cm')

def test_real_explicit_pdf_scale_reference_passes():
    a=PDFTakeoffAdapter()
    assert a.normalize_scale('1 / 50')==50
    assert a.measure_line(-1,0,1,0,'1:100','cm').value==pytest.approx(2)
    assert a.measure_area(.01,'1:100','m').value==pytest.approx(100)
