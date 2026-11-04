"""Regression of user-supplied legacy metre workbook schema against REAL pricebook API.

The original four user files are NOT checked into GitHub or uploaded as
workflow artifacts. These tiny synthetic Excel documents reproduce only the
layout necessary to test the current production pricebook import boundary.
They must be REJECTED rather than being incorrectly treated as a verified
price catalog; this test is not real-file end-to-end acceptance.
"""
from pathlib import Path

import pytest
from openpyxl import Workbook

from core.pricing.catalog import PriceCatalog
from core.pricing.import_service import PricebookImportService


@pytest.mark.parametrize("kind", ["metre", "summary"])
def test_legacy_metre_or_summary_cannot_silently_be_imported_as_pricebook(tmp_path: Path, kind: str):
    wb = Workbook()
    ws = wb.active
    if kind == "metre":
        ws.title = "S_6_1"
        ws.append(["فرم متره"])
        ws.append(["فصل ششم - قالب بندی"])
        ws.append(["رديف", "شرح عمليات", "تعداد", "طول", "عرض", "ضخامت", "طول جزئی", "سطح", "حجم", "وزن", "شماره قيمت", "قیمت", "قیمت کل"])
        ws.append([None, None, None, None, None, "ارتفاع"])
        ws.append([3, "كنار پي هاي تيپ A", 12, 1.2, None, 0.5, 0.6, None, 7.2, None, "0 60101", 42900, 1])
    else:
        ws.title = "خلاصه صورت وضعيت"
        ws.append(["برگ خلاصه صورت وضعيت"])
        ws.append(["رديف", "شماره فصل فهرست بها", "شرح", "مبلغ بدون ضریب", "ضریب بالاسری", "ضریب طبقات", "قیمت نهایی"])
        ws.append([7, "فصل هفتم", "كارهاي فولادي با ميلگرد", 30816253.97, 1.03, 1.0302, "=D3*E3*F3"])
    path = tmp_path / (kind + ".xlsx")
    wb.save(path)
    wb.close()
    catalog = PriceCatalog()
    service = PricebookImportService(catalog)
    with pytest.raises(ValueError, match="ساختار فایل Excel قابل تشخیص نیست"):
        service.inspect(path, year=1387)
    assert catalog.years() == [], "Bad legacy workbook must not change pricing catalog"


def test_legacy_metre_arithmetic_oracle_exposes_wrong_payment_amount():
    # From audited input: S_6_1!I7=7.2, L7=42900, M7=1.
    assert 7.2 * 42900 == pytest.approx(308880)
    assert 308880 - 1 == pytest.approx(308879)


def test_legacy_chapter_mismatch_is_not_a_rounding_error():
    # Golden cached-value regression; NOT a live source-document read in CI.
    detail = 16628551.22778
    summary = 30816253.97
    assert summary - detail == pytest.approx(14187702.74222)
    assert abs(summary - detail) > 1e7
