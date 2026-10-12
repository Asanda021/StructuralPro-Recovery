import pytest
from core.bim.pipeline import BIMPipelineResult
from core.bim.model import BIMElement
from core.bim.takeoff import quantities
from core.takeoff.drawing_pipeline import DrawingTakeoffPipeline

def test_bim_quantity_source_is_boq_traceable():
 e=BIMElement("G1","IFCBEAM","Beam 1","structural","beam",geometry={"volume":3},source_id="ifc:x:G1")
 q=quantities((e,))[0]
 boq=DrawingTakeoffPipeline().to_boq(DrawingTakeoffPipeline().normalize([{"source":q.source_id,"description":q.description,"quantity":q.quantity,"unit":q.unit,"price_code":q.item_code}]))
 assert boq[0]["source"]=="ifc:x:G1" and boq[0]["quantity"]==3

def test_unresolved_bim_geometry_is_not_guessed():
 e=BIMElement("G2","IFCCOLUMN",source_id="ifc:x:G2")
 assert quantities((e,))==()
