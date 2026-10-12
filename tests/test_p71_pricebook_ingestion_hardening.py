from pathlib import Path
from zipfile import ZipFile
from core.estimate.pricebook_ingestion_v1 import PriceRow, coverage, load_archive

def test_coverage_is_evidence_first():
    rows=(PriceRow(1404,"01","010101","sample","m3",123.0),)
    c=coverage(rows,1404)
    assert c["row_count"]==1 and c["year_ok"] and len(c["fingerprint"])==64

def test_zip_archive_ingestion(tmp_path: Path):
    source=tmp_path/"rows.csv"
    source.write_text("item_code,description,unit,rate,chapter\n010101,sample,m3,123,01\n",encoding="utf-8")
    archive=tmp_path/"pricebook.zip"
    with ZipFile(archive,"w") as z: z.write(source,arcname="1404/rows.csv")
    rows=load_archive(archive,1404)
    assert rows[0].item_code=="010101" and rows[0].year==1404
