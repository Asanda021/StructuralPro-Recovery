from core.estimate.pricebook_historical_matrix_v1 import required_cells,validate_cells
from core.estimate.pricebook_full_building_pricing_v2 import price_full_building
def test_p100_requires_all_24_cells():
    cells=[{"year":y,"discipline":d,"source_url":"https://official.example/x","local_path":f"{y}-{i}.xlsx","sha256":"a"*64,"row_count":1} for i,(y,d) in enumerate(required_cells())]
    assert validate_cells(cells)["cells"]==24
def test_p101_prices_full_building_shape():
    class R:
        year=1404; discipline="ابنیه"; item_code="080101"; description="بتن"; unit="م3"; unit_price=1250000; source_sha256="b"*64; source_file="1404.xlsx"
    out=price_full_building([{"takeoff_id":"q1","item_code":"۰۸۰۱۰۱","unit":"م3","quantity":3.5}],[R()],1404,"ابنیه")
    assert out[0]["total"]==4375000 and out[0]["source_sha256"]=="b"*64


def test_p101_multi_discipline_project_pricing():
    from core.estimate.pricebook_full_building_pricing_v2 import ProductionRow, price_full_building_project
    rows = [
        ProductionRow(1404,"ابنیه","1001","Concrete","m3",1000.0,"sha-a","abnieh.xlsx"),
        ProductionRow(1404,"تاسیسات مکانیکی","2001","Pipe","m",250.0,"sha-m","mechanical.xlsx"),
    ]
    takeoff = [
        {"takeoff_id":"A1","discipline":"ابنیه","item_code":"۱۰۰۱","unit":"m3","quantity":2},
        {"takeoff_id":"M1","discipline":"تاسیسات مکانیکی","item_code":"۲۰۰۱","unit":"m","quantity":4},
    ]
    priced = price_full_building_project(takeoff, rows, 1404)
    assert [r["total"] for r in priced] == [2000.0, 1000.0]
    assert all(r["source_sha256"] for r in priced)
