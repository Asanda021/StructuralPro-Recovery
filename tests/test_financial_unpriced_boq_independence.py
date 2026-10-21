"""Independent financial ledgers must remain operational for unpriced or unreviewed BOQ."""
import pytest

from core.platform.application import StructuralProApp


@pytest.mark.parametrize("hand_entered_price", [False, True])
def test_financial_ledgers_survive_unpriced_or_unreviewed_boq(tmp_path, hand_entered_price):
    app = StructuralProApp(tmp_path)
    app.create_project("دفتر مستقل با متره بدون نرخ قطعی", "FIN-NO-RATE")
    params = dict(length=3, height=2, openings=0, count=1,
                  source_id="fixture:FIN:wall-physical-1")
    if hand_entered_price:
        params.update(price_code="TEST-01", unit_price=100)
    app.add_takeoff("FIN-NO-RATE", "building", "wall", **params)
    app.add_project_cost("FIN-NO-RATE", "مصالح", 1200)
    app.add_project_commitment("FIN-NO-RATE", 3000, paid_amount=500)
    app.add_project_receipt("FIN-NO-RATE", 400)
    before = app.open_project("FIN-NO-RATE")
    dash = app.financial_dashboard("FIN-NO-RATE")
    assert dash["line_count"] == 1
    assert dash["contract_amount"] is None
    assert dash["base_amount"] is None
    assert dash["cumulative_work"] is None
    assert dash["progress_percent"] is None
    assert dash["gross_margin"] is None
    assert dash["actual_cost"] == 1200
    assert dash["estimate_status"] == "unavailable"
    assert dash["warnings"]
    position = app.project_financial_position("FIN-NO-RATE")
    assert position["contract_amount"] is None
    assert position["earned_value"] is None
    assert position["committed_cost"] == 3000
    assert position["unpaid_commitments"] == 2500
    assert position["received"] == 400
    assert position["actual_cost"] == 1200
    assert app.open_project("FIN-NO-RATE") == before
    # Independent reports export even with BOQ but no approved source pricebook.
    cost_path = tmp_path / "independent_cost.xlsx"
    finance_path = tmp_path / "independent_financial.xlsx"
    assert app.project_cost_report("FIN-NO-RATE", "xlsx", cost_path) == cost_path
    assert app.project_financial_report("FIN-NO-RATE", "xlsx", finance_path) == finance_path
    assert cost_path.stat().st_size > 0 and finance_path.stat().st_size > 0
    assert app.open_project("FIN-NO-RATE") == before
    with pytest.raises(ValueError):
        app.recalculate_estimate("FIN-NO-RATE")
    assert app.open_project("FIN-NO-RATE") == before
    app.store.close()


def test_reviewed_pricebook_still_enables_real_contract_snapshot(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه با نرخ تأییدشده", "PRICED")
    app.add_takeoff("PRICED", "building", "wall", source_id="fixture:priced:wall-01",
                    length=3, height=2, openings=0, count=1,
                    price_code="TEST-01", unit_price=100)
    price_file = tmp_path / "reviewed_pricebook.csv"
    price_file.write_text(
        "year,group,chapter,code,description,unit,unit_price\n"
        "1405,ابنیه,01,TEST-01,دیوار,m2,100\n", encoding="utf-8"
    )
    app.import_project_pricebook("PRICED", price_file, year=1405,
                                 approved_by="بازبین مستقل داده آزمون")
    dash = app.financial_dashboard("PRICED")
    assert dash["estimate_status"] == "verified"
    assert dash["contract_amount"] == 600
    assert dash["line_count"] == 1
    assert dash["actual_cost"] == 0
    assert app.open_project("PRICED").get("estimate")
    app.store.close()
