from decimal import Decimal
import pytest
from core.report.professional_reports_v2 import ReportRow, build_report, export_schema

def rows():
    return [ReportRow("C-01","Concrete column","m3",Decimal("2.5"),"draw-1",Decimal("100"),"IRR",Decimal("0.2"))]

def test_report_is_deterministic_and_exports():
    r=build_report(rows(),report_type="estimate",title="Project Report",project_id="P1",branding={"company":"StructuralPro"})
    assert len(r.fingerprint)==64
    x=export_schema(r,format="xlsx")
    assert x["columns"][0]=="item_code" and x["totals"]["amount"]==Decimal("100")

def test_duplicate_and_invalid_rows_fail_closed():
    rs=rows()+rows()
    with pytest.raises(ValueError): build_report(rs,report_type="boq",title="x",project_id="P1")
    bad=ReportRow("X","x","m3",Decimal("-1"),"s")
    with pytest.raises(ValueError): build_report([bad],report_type="boq",title="x",project_id="P1")

def test_amount_requires_currency():
    with pytest.raises(ValueError): build_report([ReportRow("X","x","m3",Decimal("1"),"s",Decimal("2"),None)],report_type="boq",title="x",project_id="P1")
