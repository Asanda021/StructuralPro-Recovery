from core.estimate.user_pricebook_mapping_v1 import candidates_for, map_user_takeoff
from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow

def test_candidates_are_year_and_discipline_isolated():
    rows=[
      NormalizedPriceRow(1404,"ابنیه","1","بتن","m3",100,"h","a.xlsx"),
      NormalizedPriceRow(1403,"ابنیه","2","بتن قدیم","m3",90,"h","b.xlsx"),
      NormalizedPriceRow(1404,"تاسیسات برقی","3","کابل","m",80,"h","c.xlsx")]
    c=candidates_for(rows,1404,"ابنیه")
    assert [x["item_code"] for x in c]==["1"]

def test_mapping_requires_review_gate_for_weak_match():
    rows=[NormalizedPriceRow(1404,"ابنیه","1","بتن","m3",100,"h","a.xlsx")]
    result=map_user_takeoff([{"takeoff_id":"t1","description":"کاملا متفاوت","unit":"m3"}],rows,1404,"ابنیه")
    assert not result["gate"]["green"]
