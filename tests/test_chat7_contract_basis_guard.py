"""Guard issued BOQ and previously valued estimate against stale financial exports."""
import pytest
from core.platform.application import StructuralProApp

def _app(tmp_path):
    a=StructuralProApp(tmp_path)
    a.create_project("کنترل", "P")
    a.add_takeoff("P","building","wall",source_id="synthetic:wall1",system="L1",
                  length=10,height=3,openings=0,count=1,price_code="W01",unit_price=100)
    file=tmp_path/"prices.csv"
    file.write_text("year,group,chapter,code,description,unit,unit_price\n"
                    "1405,ابنیه,01,W01,دیوار,m2,100\n",encoding="utf-8")
    a.import_project_pricebook("P",file,year=1405,approved_by="synthetic:reviewer")
    assert a.recalculate_estimate("P")["cost"]["base"]==pytest.approx(3000)
    return a,file

def test_payable_boq_edit_invalidates_prior_estimate(tmp_path):
    a,_=_app(tmp_path)
    a.revise_takeoff("P","synthetic:wall1",expected_revision=1,domain="building",
                     item="wall",system="L1",length=5,height=3,openings=0,count=1)
    assert not a.open_project("P").get("estimate")
    assert a.financial_dashboard("P")["contract_amount"]==pytest.approx(1500)
    a.store.close()

def test_unapproved_price_change_does_not_reuse_stale_estimate(tmp_path):
    a,_=_app(tmp_path)
    data=a.open_project("P")
    data["boq"][0]["unit_price"]=900
    a.store.save("P",data)
    assert not a.open_project("P").get("estimate")
    assert a.financial_dashboard("P")["contract_amount"] is None
    a.store.close()

def test_current_work_quantity_does_not_invalidate_contract(tmp_path):
    a,_=_app(tmp_path)
    data=a.open_project("P")
    data["boq"][0]["current_quantity"]=4
    a.store.save("P",data)
    assert a.open_project("P")["estimate"]["cost"]["base"]==pytest.approx(3000)
    a.save_statement_period("P",current_quantities={"W01":4})
    a.store.close()

@pytest.mark.parametrize("kind",["quantity","price","reviewer"])
def test_issued_statement_guards_contract_basis_and_rolls_back(tmp_path,kind):
    a,_=_app(tmp_path)
    a.save_statement_period("P",current_quantities={"W01":2})
    before=a.open_project("P")
    changed=a.open_project("P")
    if kind=="quantity": changed["boq"][0]["quantity"]=40
    if kind=="price": changed["boq"][0]["unit_price"]=99
    if kind=="reviewer": changed["user_pricebook_review"]["approved_by"]="other"
    with pytest.raises(ValueError,match="اصلاحیه"):
        a.store.save("P",changed)
    assert a.open_project("P")==before
    a.store.close()

def test_tampered_pricebook_blocks_report_and_statement_preview(tmp_path):
    a,file=_app(tmp_path)
    file.write_text(file.read_text(encoding="utf-8").replace(",100\n",",300\n"),encoding="utf-8")
    before=a.open_project("P")
    with pytest.raises(ValueError,match="فهرست‌بها"):
        a.build_statement("P")
    path=tmp_path/"bad.xlsx"
    with pytest.raises(ValueError,match="فهرست‌بها"):
        a.report("P","xlsx",path)
    assert not path.exists() and a.open_project("P")==before
    a.store.close()
