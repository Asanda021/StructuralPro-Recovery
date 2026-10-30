"""Phase 7 E7: exact grouped report subtotals, without mutating takeoff/BOQ."""
from decimal import Decimal

import pytest

from core.reports.designer import ReportLayout


def test_exact_grouped_subtotals_and_unchanged_source():
    rows = [
        {"group": "الف", "total": Decimal("0.10"), "item_no": "0001"},
        {"group": "الف", "total": "0.20", "item_no": "0002"},
        {"group": "ب", "total": "123456789012345678.123456789", "item_no": "0003"},
    ]
    before = [dict(x) for x in rows]
    out = ReportLayout(group_by="group", columns=["ردیف", "مبلغ"]).render_rows(rows)
    assert out[2] == {"group": "جمع الف", "مبلغ": Decimal("0.30")}
    assert out[-1] == {"group": "جمع ب", "مبلغ": Decimal("123456789012345678.123456789")}
    assert out[0]["ردیف"] == "0001"
    assert rows == before


@pytest.mark.parametrize("invalid", ["NaN", "Infinity", "not-a-number", True, float("inf")])
def test_invalid_grouped_total_is_not_silently_skipped(invalid):
    with pytest.raises(ValueError, match="invalid report total"):
        ReportLayout(group_by="group").render_rows([{"group": "الف", "total": invalid}])


def test_grouping_key_need_not_be_a_displayed_column():
    rows = [{"zone": "A", "total": "0.15"}, {"zone": "B", "total": "0.25"}]
    out = ReportLayout(group_by="zone", columns=["مبلغ"]).render_rows(iter(rows))
    assert [(x["zone"], x["مبلغ"]) for x in out if "zone" in x] == [
        ("جمع A", Decimal("0.15")), ("جمع B", Decimal("0.25"))
    ]


def test_empty_and_zero_page_size_are_explicit():
    assert ReportLayout(group_by="group").pages([]) == [[]]
    with pytest.raises(ValueError, match="page_size"):
        ReportLayout(page_size=0).pages([{"total": "1"}])
