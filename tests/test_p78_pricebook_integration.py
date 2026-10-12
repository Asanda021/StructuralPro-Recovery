from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow
from core.estimate.pricebook_integration_v1 import to_price_rows

def test_integration_rejects_unpriced_and_accepts_valid():
    rows=[NormalizedPriceRow(1404,"ابنیه","1","Concrete","m3",100.0,"abc","x.xlsx"),
          NormalizedPriceRow(1404,"ابنیه","2","Note","m",None,"abc","x.xlsx")]
    out=to_price_rows(rows)
    assert len(out.accepted)==1
    assert out.missing_rate==1
