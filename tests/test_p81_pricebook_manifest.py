from core.estimate.pricebook_manifest_v1 import source_manifest, coverage_gate
from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow

def test_manifest_groups_sources():
    rows=[NormalizedPriceRow(1404,"ابنیه","1","A","m",2,"h","a.xlsx"),
          NormalizedPriceRow(1404,"ابنیه","2","B","m",None,"h","a.xlsx")]
    m=source_manifest(rows)
    assert m["sources"][0]["rows"]==2
    assert m["sources"][0]["priced_rows"]==1
    assert coverage_gate(m,["ابنیه"])["green"]
