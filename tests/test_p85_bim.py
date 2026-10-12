import pytest
from core.bim.model import BIMElement
from core.bim.takeoff import quantities

def test_bim_preserves_identity_level_type_materials():
 e=BIMElement("G1","IFCBEAM","B1","structural","beam","L2","BeamType",("Concrete",),{"P":1},{"volume":2.5},"ifc:x:G1")
 assert e.global_id=="G1" and e.level=="L2" and e.type_name=="BeamType" and e.material_names==("Concrete",)

def test_bim_quantity_uses_explicit_volume_only():
 e=BIMElement("G1","IFCBEAM",geometry={"volume":2.5},source_id="ifc:x:G1")
 q=quantities((e,))[0]
 assert q.quantity==pytest.approx(2.5) and q.unit=="m3"

def test_bim_does_not_guess_missing_geometry():
 e=BIMElement("G1","IFCBEAM",source_id="ifc:x:G1")
 assert quantities((e,))==()

def test_bim_area_quantity():
 e=BIMElement("G1","IFCSLAB",geometry={"area":100},source_id="ifc:x:G1")
 assert quantities((e,))[0].unit=="m2"


def test_bim_model_can_hold_geometric_dimensions_without_inference():
 e=BIMElement("G3","IFCWALL",geometry={"bbox_length":5.0,"bbox_width":0.2,"bbox_height":3.0})
 assert e.geometry["bbox_length"]==5.0 and e.has_quantity_geometry
