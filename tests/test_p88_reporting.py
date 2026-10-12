import pytest
from core.reports import ReportRequest, ReportService

def test_unified_report_filters_cancelled_and_builds_pages():
    request=ReportRequest("boq","گزارش متره",page_size=1)
    rows=[{"item_no":1,"description":"Concrete","quantity":10,"unit":"m3","total":100,"status":"active"},{"item_no":2,"description":"Cancelled","quantity":2,"unit":"m3","total":20,"status":"cancelled"}]
    result=ReportService.build(request,rows)
    assert len(result["rows"])==1 and result["totals"]["amount"]==100
    assert len(result["pages"])==1 and result["schema"]["rtl"] is True

def test_report_can_explicitly_include_cancelled_lines():
    request=ReportRequest("financial","گزارش مالی",include_cancelled=True)
    result=ReportService.build(request,[{"description":"A","quantity":1,"unit":"kg","total":10,"status":"active"},{"description":"B","quantity":1,"unit":"kg","total":5,"status":"cancelled"}])
    assert result["totals"]["amount"]==15

def test_report_filters_without_mutating_source():
    rows=[{"description":"A","group":"concrete","quantity":1,"unit":"m3"},{"description":"B","group":"steel","quantity":2,"unit":"kg"}]
    result=ReportService.build(ReportRequest("takeoff","Takeoff",filters={"group":"concrete"}),rows)
    assert len(result["rows"])==1 and rows[1]["group"]=="steel"

def test_report_rejects_invalid_request_and_nonfinite_amount():
    with pytest.raises(ValueError): ReportRequest("unknown","x")
    with pytest.raises(ValueError): ReportService.build(ReportRequest("boq","x"),[{"description":"A","quantity":1,"unit":"m3","total":float("nan")}])

def test_audit_report_is_traceable():
    result=ReportService.build_audit(ReportRequest("audit","Audit"),events=[{"event":"BOQ_CREATED","source_id":"S1"}])
    assert result["metadata"]["audit"] is True and result["rows"][0]["source_id"]=="S1"
