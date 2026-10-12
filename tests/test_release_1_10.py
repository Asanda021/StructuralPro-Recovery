import json
import pytest

def test_dwg_dxf_extraction_and_layer_mapping(tmp_path):
    import ezdxf
    from core.drawings.dwg_takeoff import DWGTakeoffEngine
    p=tmp_path/"plan.dxf"; doc=ezdxf.new(); m=doc.modelspace()
    m.add_line((0,0),(3,0),dxfattribs={"layer":"WALL"})
    m.add_lwpolyline([(0,0),(2,0),(2,2),(0,2)],close=True,dxfattribs={"layer":"ROOM"})
    doc.saveas(p)
    d=DWGTakeoffEngine().import_file(p)
    s=DWGTakeoffEngine().summarize(d)
    assert s["entities"]==2 and "WALL" in s["layers"] and s["units"] == "m"
    rows=DWGTakeoffEngine().layer_takeoff(d,{"WALL":{"metric":"length","unit":"m","description":"دیوار"}})
    assert rows[0]["quantity"]==pytest.approx(3)

def test_pdf_measurement_edit_history_roundtrip():
    from core.drawings.pdf_measurement import PDFMeasurementSession
    s=PDFMeasurementSession(); s.calibrate(100,10)
    m=s.add_length(1,[(0,0),(100,0)],label="دیوار")
    s.edit(m.id,label="دیوار اصلاح‌شده"); assert s.by_page(1)[0].label=="دیوار اصلاح‌شده"
    payload=json.loads(s.to_json()); assert payload["history"]
    assert PDFMeasurementSession.from_dict(payload).totals()["by_unit"]["m"]==pytest.approx(10)

def test_ifc_duplicate_and_strict_mapping():
    from core.drawings.ifc_inventory import inventory,normalize_bim_rows,map_bim_to_price
    rows=[{"global_id":"1","ifc_type":"IfcWall","quantities":{"Length":10},"properties":{"Level":"1"}},
          {"global_id":"1","ifc_type":"IfcWall","quantities":{"Length":10},"properties":{"Level":"1"}}]
    assert inventory(rows)["duplicates"]==["1"]
    n=normalize_bim_rows(rows); assert len(n)==1
    assert map_bim_to_price(n,{"IfcWall":"W-1"})[0]["price_code"]=="W-1"
    with pytest.raises(ValueError): map_bim_to_price(n,{},strict=True)

def test_price_source_registry_validation():
    from core.pricing.source_registry import PriceSource,PriceSourceRegistry
    reg=PriceSourceRegistry(); src=PriceSource(1405,"building","فهرست","publisher","src-1")
    text="year,group,chapter,code,description,unit,unit_price\n1405,ابنیه,1,1-1,دیوار,m2,100"
    r=reg.validate_import(src,text); assert r["valid"] and len(r["sha256"])==64

def test_complete_progress():
    from core.commercial.progress import build_progress
    r=build_progress([{"contract_quantity":100,"previous_quantity":20,"current_quantity":30,"unit_price":10}],deductions=[20],payments=[100])
    assert r["completed_total"]==500 and r["payable_current"]==280 and r["balance_current"]==180

def test_report_layout_group_and_paging():
    from core.reports.designer import ReportLayout
    l=ReportLayout(columns=["کد","شرح","مقدار","مبلغ"],group_by="کد",page_size=2)
    rows=l.render_rows([{"price_code":"A","description":"x","quantity":1,"total":10},{"price_code":"A","description":"y","quantity":2,"total":20}])
    assert any("جمع A" in str(x.get("کد","")) for x in rows)
    assert len(l.pages(rows))>=1

def test_project_model_validation_and_workflow():
    from core.projects.project_model import ProjectModel
    p=ProjectModel("P1","پروژه"); p.add_floor("همکف"); p.add_drawing("plan.pdf",floor_id="1")
    assert p.validate()==[] and p.to_dict()["drawings"][0]["floor_id"]=="1"

def test_catalog_source_info():
    from core.pricing.catalog import PriceCatalog,PriceItem
    from core.pricing.source_registry import PriceSourceRegistry,PriceSource
    reg=PriceSourceRegistry(); reg.register(PriceSource(1405,"building","x","y","z"))
    c=PriceCatalog([PriceItem(1405,"g","c","1","x","m2",10)],source_registry=reg)
    assert c.source_info(1405,"building","z").source_id=="z"
