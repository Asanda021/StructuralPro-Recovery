from core.reports.rtl_export_contract_v1 import ReportCell, ReportSection, render_rtl, report_fingerprint

def sample():
    return (ReportSection("خلاصه پروژه",(ReportCell("حجم بتن","125.40"),ReportCell("وزن میلگرد","18,250"))),)

def test_rtl_report_contains_rtl_mark_and_persian_text():
    out = render_rtl(sample())
    assert out.startswith("\u200f")
    assert "خلاصه پروژه" in out

def test_report_is_deterministic():
    assert report_fingerprint(sample()) == report_fingerprint(sample())

def test_empty_report_rejected():
    try:
        render_rtl(())
    except ValueError:
        pass
    else:
        raise AssertionError("empty report must fail")
