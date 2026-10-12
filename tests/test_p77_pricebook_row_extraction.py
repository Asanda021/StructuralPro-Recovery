from pathlib import Path
from core.estimate.pricebook_row_extraction_v1 import extract_csv, extract_json, validate_rows

def test_csv_rows_are_normalized(tmp_path):
    p=tmp_path/"x.csv"
    p.write_text("item_code,description,unit,unit_price\n1,Concrete,m3,123.5\n",encoding="utf-8")
    rows=extract_csv(p,1404,"ابنیه")
    assert rows[0].item_code=="1"
    assert rows[0].unit_price==123.5
    assert validate_rows(rows)["priced_rows"]==1

def test_json_rows_are_normalized(tmp_path):
    p=tmp_path/"x.json"
    p.write_text('[{"code":"2","شرح":"Steel","واحد":"kg","price":"4.2"}]',encoding="utf-8")
    rows=extract_json(p,1404,"ابنیه")
    assert rows[0].description=="Steel"
    assert rows[0].unit=="kg"
