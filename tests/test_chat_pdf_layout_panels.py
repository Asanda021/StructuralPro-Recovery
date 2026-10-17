"""Print-safe PDF layout regressions: do not round numbers or drop source columns."""
from xml.sax.saxutils import escape
import pytest
from reportlab.lib.pagesizes import A4, landscape
from core.reports import exporters

def _sample():
    columns = [('item_no', 'ردیف')] + [(f'field_{i}', f'عنوان {i}') for i in range(1, 15)]
    columns[6] = ('grand_total', 'مبلغ نهایی')
    precise = '76543.001836602551500'
    rows = [dict(item_no=i, grand_total=precise, **{
        f'field_{k}': f'دیگر ردیف {i}' for k in range(1, 15) if k != 6
    }) for i in range(1, 45)]
    return columns, rows, precise

def test_layout_retains_all_fields_and_repeats_identity_in_each_panel(monkeypatch):
    monkeypatch.setattr(exporters, '_pdf_text', lambda x: escape(str(x)))
    cols, rows, value = _sample()
    plan = exporters._pdf_column_plan(cols, rows, font=exporters._pdf_font(),
                                      usable_width=landscape(A4)[0] - 48)
    assert len(plan) > 1
    assert all(panel[0][0] == 'item_no' for panel in plan)
    assert all(sum(c[2] for c in panel) <= landscape(A4)[0] - 48 for panel in plan)
    assert set(c[0] for panel in plan for c in panel) == set(k for k, _ in cols)
    assert sum(c[0] == 'grand_total' for panel in plan for c in panel) == 1
    assert exporters._pdf_is_number(value)

def test_exported_pdf_preserves_full_decimal_digits(tmp_path, monkeypatch):
    from pypdf import PdfReader
    # ASCII substitution isolates layout; real Persian shaping has its own tests.
    monkeypatch.setattr(exporters, '_pdf_text', lambda x: escape(str(x)))
    cols, rows, value = _sample()
    path = exporters.export_pdf(rows, tmp_path / 'wide.pdf', title='Report layout', columns=cols)
    reader = PdfReader(path)
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    assert len(reader.pages) >= 2
    assert value in text
    assert all(float(page.mediabox.width) == pytest.approx(landscape(A4)[0]) for page in reader.pages)

def test_unprintably_long_number_is_rejected_not_clipped(monkeypatch):
    monkeypatch.setattr(exporters, '_pdf_text', lambda x: escape(str(x)))
    with pytest.raises(ValueError, match='عدد مالی'):
        exporters._pdf_column_plan([('quantity', 'مقدار')], [{'quantity': '9'*1000}],
                                   font=exporters._pdf_font(), usable_width=790)

def test_small_report_remains_on_one_page(tmp_path, monkeypatch):
    from pypdf import PdfReader
    monkeypatch.setattr(exporters, '_pdf_text', lambda x: escape(str(x)))
    path = exporters.export_pdf([{'item_no': 1, 'total': 123.12}], tmp_path / 'small.pdf',
                                title='Report', columns=[('item_no','ردیف'),('total','مبلغ')])
    assert len(PdfReader(path).pages) == 1
