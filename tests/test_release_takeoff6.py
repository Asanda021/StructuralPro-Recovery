"""Release gate for the six takeoff/estimating upgrades."""
from core.drawings.graphical_takeoff import ScaleCalibration,MeasurementStore,Point
from core.ai.auto_takeoff import LocalAutoTakeoff
from core.takeoff.assemblies import AssemblyLibrary
from core.takeoff.workflow import TakeoffWorkflow

def test_six_capabilities_gate():
    s=ScaleCalibration.parse("1:100")
    store=MeasurementStore()
    assert store.add_length([Point(0,0),Point(1,0)],s).value==1
    assert store.add_area([Point(0,0),Point(1,0),Point(1,1),Point(0,1)],s).value==1
    assert store.add_count(3).value==3
    assert AssemblyLibrary().get("SLAB-CON").expand(2)[1]["quantity"]==24
    assert LocalAutoTakeoff().auto_scale("S=1:50")==50
    assert TakeoffWorkflow().build_estimate([{"quantity":2,"price_code":"X"}],{"X":10})[0]["total"]==20
