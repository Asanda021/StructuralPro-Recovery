import pytest
from core.reports.production_report_package_v1 import build_report_package, validate_report_package

def test_rtl_report_package_is_deterministic():
    a=build_report_package(project_id="GOLDEN-RPT-001",revision="R1",report_data={"concrete_m3":12.5},export_files=("report.pdf","boq.xlsx"),rtl=True)
    b=build_report_package(project_id="GOLDEN-RPT-001",revision="R1",report_data={"concrete_m3":12.5},export_files=("report.pdf","boq.xlsx"),rtl=True)
    assert a==b
    assert validate_report_package(a)["valid"] is True

def test_unsupported_format_fails_closed():
    with pytest.raises(ValueError):
        build_report_package(project_id="P",revision="R1",report_data={"x":1},export_files=("report.docx",))

def test_non_rtl_production_package_fails_closed():
    package=build_report_package(project_id="P",revision="R1",report_data={"x":1},export_files=("report.pdf",),rtl=False)
    with pytest.raises(ValueError):
        validate_report_package(package)

def test_empty_report_fails_closed():
    with pytest.raises(ValueError):
        build_report_package(project_id="P",revision="R1",report_data={},export_files=("report.pdf",))
