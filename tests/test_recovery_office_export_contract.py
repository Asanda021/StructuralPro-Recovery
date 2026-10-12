"""Offline spreadsheet/document format acceptance without network/GitHub Actions."""
from __future__ import annotations
import csv
import zipfile
import xml.etree.ElementTree as ET
from core.reports.exporters import export_csv, export_xlsx, export_docx, export_pdf
import pytest

ROWS = [{'code':'0101','description':'بتن پی','quantity':2.5,'unit':'m3'}]
COLS = [('code','کد'),('description','شرح'),('quantity','مقدار'),('unit','واحد')]


def test_csv_preserves_persian_and_leading_zero(tmp_path):
    p=export_csv(ROWS,tmp_path/'quantity.csv',title='گزارش متره',columns=COLS)
    assert p.read_bytes().startswith(b'\xef\xbb\xbf')
    with p.open(encoding='utf-8-sig',newline='') as f:
        records=list(csv.reader(f))
    assert 'گزارش متره' in records[0]
    assert ['0101','بتن پی','2.5','m3'] in records


def test_xlsx_has_real_persian_rtl_sheets_and_quantities(tmp_path):
    p=export_xlsx(ROWS,tmp_path/'quantity.xlsx',title='گزارش متره',columns=COLS)
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        wb=z.read('xl/workbook.xml').decode('utf-8')
        assert 'ریز متره' in wb and 'خلاصه' in wb
        sheet=z.read('xl/worksheets/sheet1.xml').decode('utf-8')
        assert 'rightToLeft="1"' in sheet or 'rightToLeft="true"' in sheet
        sheet_node=ET.fromstring(sheet)
        texts=[cell.text for cell in sheet_node.iter() if cell.text]
        assert '0101' in texts
        assert 'بتن پی' in texts
        assert '2.5' in texts


def test_docx_has_real_persian_table_and_rows(tmp_path):
    p=export_docx(ROWS,tmp_path/'quantity.docx',title='گزارش متره',columns=COLS)
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        document=z.read('word/document.xml').decode('utf-8')
        assert 'گزارش متره' in document
        assert '0101' in document
        assert 'بتن پی' in document
        assert 'w:bidiVisual' in document


def test_pdf_fails_closed_when_bidi_engine_is_missing(tmp_path):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
    except ImportError:
        with pytest.raises(RuntimeError, match='فارسی'):
            export_pdf(ROWS,tmp_path/'quantity.pdf',title='گزارش متره',columns=COLS)
    else:
        p=export_pdf(ROWS,tmp_path/'quantity.pdf',title='گزارش متره',columns=COLS)
        assert p.is_file() and p.stat().st_size>1000
