from core.estimate.user_pricebook_import_gate_v1 import import_gate
from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow

def test_user_import_green_when_provenance_complete():
    r=NormalizedPriceRow(1404,"ابنیه","1","بتن","m3",100,"a"*64,"user.xlsx")
    x=import_gate([r],1404,"ابنیه")
    assert x["green"] and x["fingerprint"]

def test_user_import_rejects_mixed_discipline():
    r=NormalizedPriceRow(1404,"تاسیسات برقی","1","کابل","m",100,"a"*64,"user.xlsx")
    x=import_gate([r],1404,"ابنیه")
    assert not x["green"]
