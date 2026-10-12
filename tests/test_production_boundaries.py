from core.platform.production_boundaries import License, validate_license, project_fingerprint, sync_envelope, collaboration_member, add_comment, approval_state
from core.pricing.production import validate_dataset_rows, price_analysis
from core.reports.rtl import report_schema

def test_offline_boundaries_and_collaboration():
    lic=License("abc",features=("takeoff",))
    assert validate_license(lic,"takeoff")["valid"]
    p={"name":"x","takeoffs":[]}
    assert len(project_fingerprint(p))==64
    assert sync_envelope("p1",2,p)["version"]==2
    assert collaboration_member("u1","engineer")["role"]=="engineer"
    comments=add_comment([], "u1", "بازبینی شد")
    assert comments[0]["text"]=="بازبینی شد"
    assert approval_state("approved","u1")["status"]=="approved"

def test_price_dataset_validation_and_report_schema():
    rows=[{"year":1405,"group":"ابنیه","chapter":"1","code":"1","description":"بتن","unit":"m3","unit_price":100}]
    assert validate_dataset_rows(rows,1405)["valid"]
    assert price_analysis(2,100,[1.1])["amount"]==220
    assert report_schema(["code","description"])["rtl"]
