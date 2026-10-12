from pathlib import Path
import csv
from openpyxl import Workbook

from core.pricing.catalog import PriceCatalog
from core.pricing.import_service import PricebookImportService


def test_excel_pricebook_import_maps_persian_headers(tmp_path):
    path = tmp_path / "فهرست-1404.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "ابنیه"
    ws.append(["سال", "رشته", "فصل", "شماره ردیف", "شرح", "واحد", "بهای واحد"])
    ws.append([1404, "ابنیه", "01", "010101", "بتن آماده", "مترمکعب", 12500000])
    ws.append([1404, "ابنیه", "01", "010102", "آرماتور", "کیلوگرم", 85000])
    wb.save(path)

    catalog = PriceCatalog()
    service = PricebookImportService(catalog)
    receipt = service.import_file(path, year=1404, replace_year=True)

    assert receipt.format == "excel"
    assert receipt.rows == 2
    assert catalog.get("010101", 1404).unit_price == 12500000
    assert catalog.get("010102", 1404).unit == "کیلوگرم"


def test_csv_pricebook_import_remains_supported(tmp_path):
    path = tmp_path / "pricebook.csv"
    path.write_text(
        "year,group,chapter,code,description,unit,unit_price,analysis,notes\n"
        "1404,ابنیه,01,010103,قالب‌بندی,m2,950000,,\n",
        encoding="utf-8-sig",
    )
    catalog = PriceCatalog()
    receipt = PricebookImportService(catalog).import_file(path, year=1404)
    assert receipt.rows == 1
    assert catalog.resolve("010103", 1404)["status"] == "ok"


def test_invalid_pricebook_fails_closed(tmp_path):
    path = tmp_path / "bad.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["شرح", "واحد"])
    ws.append(["بدون کد", "متر"])
    wb.save(path)
    service = PricebookImportService(PriceCatalog())
    try:
        service.import_file(path, year=1404)
    except ValueError as exc:
        assert "ساختار فایل Excel قابل تشخیص نیست" in str(exc)
    else:
        raise AssertionError("invalid pricebook must fail closed")


def test_persian_csv_headers_are_supported(tmp_path):
    path = tmp_path / "pricebook-fa.csv"
    path.write_text(
        "سال,رشته,فصل,شماره ردیف,شرح,واحد,بهای واحد\n"
        "1404,ابنیه,01,010104,آجرکاری,مترمربع,2500000\n",
        encoding="utf-8-sig",
    )
    catalog = PriceCatalog()
    receipt = PricebookImportService(catalog).import_file(path, year=1404)
    assert receipt.rows == 1
    assert catalog.get("010104", 1404).unit_price == 2500000
