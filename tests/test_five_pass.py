from core.drawings.unified_takeoff import UnifiedDrawingTakeoff
from core.pricing.catalog import PriceCatalog, PriceItem
from core.pricing.dataset import PriceDataset
from core.reports.quality import prepare_rows, summary
from core.ai.project_assistant import ProjectAssistant

def test_unified_pdf_candidates_to_rows():
    s=UnifiedDrawingTakeoff()
    inspection={"kind":"pdf","candidates":[{"source":"pdf:p1","description":"Wall","quantity":2,"unit":"m","needs_confirmation":True}]}
    rows=s.candidates_to_rows(inspection,{1:True})
    assert rows[0]["quantity"]==2 and rows[0]["needs_confirmation"] is True

def test_price_dataset_manifest_and_duplicate_validation():
    items=[PriceItem(1405,"ابنیه","بتن","A","بتن","m3",10),
           PriceItem(1405,"ابنیه","بتن","A","بتن","m3",10)]
    d=PriceDataset()
    assert d.validate(items)
    assert d.manifest([items[0]])["count"]==1

def test_report_quality_persian():
    rows=prepare_rows([{"source":"manual","price_code":"A","description":"بتن","quantity":2,"unit":"m3","unit_price":100}], "fa")
    assert list(rows[0])==["ردیف","منبع","کد فهرست‌بها","شرح","مقدار","واحد","بهای واحد","مبلغ"]
    assert summary(rows)["grand_total"]==200

def test_project_assistant_offline_review():
    r=ProjectAssistant().review({"name":"P","takeoffs":[{"member_code":"wall","quantities":[{"amount":-1,"unit":"m","price_code":"A"}]}]})
    assert r["offline"] is True
    assert any(x["code"]=="negative_quantity" for x in r["issues"])

def test_project_assistant_compare():
    r=ProjectAssistant().compare_rows([{"description":"A","quantity":2}],[{"description":"A","quantity":3}])
    assert r[0]["delta"]==1
