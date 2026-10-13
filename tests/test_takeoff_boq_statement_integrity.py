"""Pricebook provenance and physical BOQ bound a statement across SQLite reopens."""
import pytest
from core.platform.application import StructuralProApp

def _project(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("کارگاه مالی آزمایشی", "P")
    app.add_takeoff("P","building","wall",source_id="drawing:wall-1",system="L1",
                    length=10,height=3,openings=0,count=1,
                    price_code="TEST-01",unit_price=100)
    return app

def test_full_chain_requires_approved_pricebook_then_persists_statement(tmp_path):
    app = _project(tmp_path)
    initial = app.open_project("P")
    with pytest.raises(ValueError): app.recalculate_estimate("P")
    with pytest.raises(ValueError): app.save_statement_period("P",current_quantities={"TEST-01": 7})
    assert app.open_project("P") == initial
    price_file = tmp_path/"synthetic-pricebook.csv"
    price_file.write_text("year,group,chapter,code,description,unit,unit_price\n"
                          "1405,ابنیه,01,TEST-01,دیوار,m2,100\n",encoding="utf-8")
    app.import_project_pricebook("P",price_file,year=1405,approved_by="synthetic:independent-checker")
    estimate = app.recalculate_estimate("P")
    assert estimate["cost"]["base"] == pytest.approx(3000)
    boq = app.open_project("P")["boq"]
    assert boq[0]["source_ids"] == ["drawing:wall-1"]
    assert boq[0]["quantity"] == pytest.approx(30)
    before = app.open_project("P")
    with pytest.raises(ValueError,match="progress exceeds contract"):
        app.save_statement_period("P",current_quantities={"TEST-01":31})
    assert app.open_project("P") == before
    period = app.save_statement_period("P",period_no=1,current_quantities={"TEST-01":7},retention_rate=.1)
    assert period["gross_current"] == pytest.approx(700)
    assert period["payable_current"] == pytest.approx(630)
    app.store.close()
    reopened = StructuralProApp(tmp_path)
    assert reopened.open_project("P")["takeoffs"] == before["takeoffs"]
    assert reopened.statement_periods("P")[0] == period
    assert reopened.open_project("P")["estimate"]["cost"]["base"] == pytest.approx(3000)
    reopened.store.close()

def test_tampered_pricebook_rejects_new_statement_and_financial_valuation(tmp_path):
    app = _project(tmp_path)
    file = tmp_path/"pricebook.csv"
    file.write_text("year,group,chapter,code,description,unit,unit_price\n"
                    "1405,ابنیه,01,TEST-01,دیوار,m2,100\n",encoding="utf-8")
    app.import_project_pricebook("P",file,year=1405,approved_by="synthetic:reviewer")
    app.recalculate_estimate("P")
    before = app.open_project("P")
    file.write_text(file.read_text(encoding="utf-8").replace(",100\n",",999\n"),encoding="utf-8")
    with pytest.raises(ValueError,match="فهرست‌بها"):
        app.save_statement_period("P",current_quantities={"TEST-01":2})
    with pytest.raises(ValueError,match="فهرست‌بها"):
        app.recalculate_estimate("P")
    assert app.financial_dashboard("P")["contract_amount"] is None
    assert app.open_project("P") == before
    app.store.close()

def test_duplicate_real_takeoff_source_does_not_mutate_boq(tmp_path):
    app = _project(tmp_path)
    before = app.open_project("P")
    with pytest.raises(ValueError,match="تکراری"):
        app.add_takeoff("P","building","wall",source_id="drawing:wall-1",system="L1",
                        length=10,height=3,openings=0,count=1)
    assert app.open_project("P") == before
    app.store.close()
