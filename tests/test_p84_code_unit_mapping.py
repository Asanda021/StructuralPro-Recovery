from core.estimate.user_pricebook_code_mapping_v1 import map_by_code_unit
from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow

def test_exact_code_unit_mapping():
    rows=[NormalizedPriceRow(1404,"ابنیه","123","بتن","m3",100,"h","a.xlsx")]
    out=map_by_code_unit([{"takeoff_id":"t1","item_code":"123","unit":"m3"}],rows,1404,"ابنیه")
    assert out["green"] and out["count"]==1

def test_wrong_unit_is_unresolved():
    rows=[NormalizedPriceRow(1404,"ابنیه","123","بتن","m3",100,"h","a.xlsx")]
    out=map_by_code_unit([{"takeoff_id":"t1","item_code":"123","unit":"kg"}],rows,1404,"ابنیه")
    assert not out["green"]
