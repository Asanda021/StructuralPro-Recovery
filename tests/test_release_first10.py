import json
import pytest

from core.drawings.pdf_measurement import PDFMeasurementSession
from core.drawings.ifc_inventory import inventory, normalize_bim_rows, map_bim_to_price
from core.takeoff.estimate import build_estimate, compare_estimates
from core.projects.metadata import ProjectMetadata
from core.revisions.manager import RevisionManager
from core.commercial.progress import build_progress
from core.reports.production import prepare_report, totals

def test_pdf_measurement_calibration_area_hole_and_roundtrip():
    s=PDFMeasurementSession()
    assert s.calibrate(100,10) == pytest.approx(0.1)
    s.add_length(1,[(0,0),(100,0)])
    m=s.add_area(1,[(0,0),(100,0),(100,100),(0,100)],holes=[[(25,25),(75,25),(75,75),(25,75)]])
    assert m.quantity == pytest.approx(75)
    s.add_count(1,3,label="ستون")
    clone=PDFMeasurementSession.from_dict(json.loads(s.to_json()))
    assert len(clone.by_page(1))==3

def test_ifc_inventory_mapping():
    rows=[{"global_id":"1","ifc_type":"IfcWall","name":"W1","level":"L1","quantities":{"Length":10,"Area":20}},
          {"global_id":"2","ifc_type":"IfcWall","name":"W2","properties":{"Level":"L2"},"quantities":{"Length":5}}]
    inv=inventory(rows)
    assert inv["objects"]==2 and inv["by_type"]["IfcWall"]==2
    normalized=normalize_bim_rows(rows)
    mapped=map_bim_to_price(normalized,{"IfcWall":"WALL-01"})
    assert mapped[0]["price_code"]=="WALL-01"

def test_estimate_pipeline_and_compare():
    rows=[{"description":"دیوار","quantity":10,"unit":"m2","price_code":"1","unit_price":100},
          {"description":"دیوار","quantity":5,"unit":"m2","price_code":"1","unit_price":100}]
    a=build_estimate(rows,factors={"overhead":0.1})
    b=build_estimate(rows+[{"description":"کف","quantity":2,"unit":"m2","price_code":"2","unit_price":50}],factors={"overhead":0.1})
    assert a["cost"]["grand_total"]==pytest.approx(1650)
    assert compare_estimates(a,b)["delta"]>0

def test_project_metadata_validation():
    p=ProjectMetadata("P1","پروژه",area_m2=1200,floors=5,start_date="2026-10-01")
    assert p.validate()==[]
    assert ProjectMetadata("","","",area_m2=-1).validate()

def test_revision_manager():
    r=RevisionManager(); r.add([{"price_code":"A","quantity":1}],"A"); r.add([{"price_code":"A","quantity":2}],"B")
    result=r.compare(1,2)
    assert result["summary"]["changed"]==1

def test_progress():
    r=build_progress([{"code":"A","contract_quantity":100,"previous_quantity":20,"current_quantity":30,"unit_price":10}])
    assert r["lines"][0]["progress_percent"]==50
    assert r["lines"][0]["remaining_quantity"]==50
    assert r["current_total"]==300

def test_report_persian_columns():
    rows=prepare_report([{"price_code":"A","description":"دیوار","quantity":2,"unit":"m2","unit_price":100,"total":200}],"fa")
    assert rows[0]["شرح"]=="دیوار" and totals(rows)["amount"]==200
