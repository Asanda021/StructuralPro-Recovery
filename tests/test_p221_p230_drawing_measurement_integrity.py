from core.drawing.measurement_integrity_v1 import MeasurementEvidence,accept_measurements,fingerprint
import pytest
def e(v=5): return MeasurementEvidence("sheet1","line",v,"m","Lpx/scale","1:100")
def test_valid(): assert accept_measurements([e()])[0].value==5
def test_no_scale_fails():
 with pytest.raises(ValueError): MeasurementEvidence("s","line",1,"m","x","").validate()
def test_negative_fails():
 with pytest.raises(ValueError): e(-1).validate()
def test_duplicate_fails():
 with pytest.raises(ValueError): accept_measurements([e(),e()])
def test_fingerprint(): assert fingerprint([e()])==fingerprint([e()])