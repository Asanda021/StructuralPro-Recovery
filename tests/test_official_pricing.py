from core.pricing.catalog import PriceCatalog
from core.pricing.official_import import import_official_csv

def test_official_csv_import_requires_schema(tmp_path):
    p=tmp_path/"prices.csv"; p.write_text("year,group,chapter,code,description,unit,unit_price\n1405,ابنیه,1,1-1,Concrete,m3,100\n",encoding="utf-8")
    c=PriceCatalog(); r=import_official_csv(p,c)
    assert r["rows"]==1 and r["official_verified"] is False
