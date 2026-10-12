from core.estimate.pricebook_integration_v1 import map_and_price
from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow

def test_bridge_prices_exact_code_unit():
    rows=[NormalizedPriceRow(1404,"ابنیه","123","بتن","m3",100,"h","a.xlsx")]
    out=map_and_price([{"takeoff_id":"t1","item_code":"123","unit":"m3","quantity":2}],rows,1404,"ابنیه")
    assert out.accepted[0]["total"]==200

def test_bridge_isolates_year_and_discipline():
    rows=[NormalizedPriceRow(1403,"ابنیه","123","قدیم","m3",10,"h","a.xlsx"),
          NormalizedPriceRow(1404,"تاسیسات برقی","123","برقی","m3",999,"h2","b.xlsx")]
    try:
        map_and_price([{"takeoff_id":"t1","item_code":"123","unit":"m3","quantity":1}],rows,1404,"ابنیه")
    except ValueError:
        return
    assert False
