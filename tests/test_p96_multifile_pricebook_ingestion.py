import zipfile
from core.estimate.pricebook_ingestion_v1 import load_archive

def test_zip_archive_ingests_multiple_files(tmp_path):
    z=tmp_path/"pb.zip"; a=tmp_path/"a.csv"; b=tmp_path/"b.csv"
    a.write_text("item_code,description,unit,rate\n100,A,m3,1000\n",encoding="utf-8")
    b.write_text("item_code,description,unit,rate\n200,B,m,2000\n",encoding="utf-8")
    with zipfile.ZipFile(z,"w") as zz:
        zz.write(a,"a.csv"); zz.write(b,"b.csv")
    rows=load_archive(z,1404)
    assert {r.item_code for r in rows}=={"100","200"}
