from core.bim.ifc_intelligence_v2 import extract_quantities, compare_bim_to_drawing
from core.bim.model import BIMElement

def test_ifc_quantities_are_normalized():
    e=BIMElement("g1","IFCBEAM",kind="beam",geometry={"Volume":2.5,"Area":10})
    rows=extract_quantities((e,))
    assert {r.quantity_name for r in rows}=={"volume","area"}

def test_bim_drawing_discrepancy_gate():
    rows=compare_bim_to_drawing({"volume":10},{"volume":10.002},tolerance=.001)
    assert rows[0].status=="mismatch"

def test_missing_side_is_explicit():
    rows=compare_bim_to_drawing({"volume":10},{})
    assert rows[0].status=="missing_drawing"
