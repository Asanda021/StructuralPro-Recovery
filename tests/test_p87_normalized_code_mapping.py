from core.estimate.user_pricebook_code_mapping_v1 import map_by_code_unit
from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow

def test_persian_digits_match_ascii_code():
    rows=[NormalizedPriceRow(1404,"ابنیه","۱۲-۰۳","شرح","m3",100,"sha","a.xlsx")]
    out=map_by_code_unit([{"takeoff_id":"t1","item_code":"12 – 03","unit":"m3"}],rows,1404,"ابنیه")
    assert out["green"] and out["count"]==1

def test_normalized_conflict_fails_closed():
    rows=[NormalizedPriceRow(1404,"ابنیه","۱۲۳","الف","m3",100,"a","a.xlsx"),
          NormalizedPriceRow(1404,"ابنیه","123","ب","m3",200,"b","b.xlsx")]
    try: map_by_code_unit([],rows,1404,"ابنیه")
    except ValueError: return
    assert False
