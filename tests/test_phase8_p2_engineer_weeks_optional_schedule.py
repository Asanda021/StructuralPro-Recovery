"""P8/P2: per-engineer weekly tasks, optional auto schedule, blank contract rates."""
from __future__ import annotations
import os
from copy import deepcopy
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from core.projects.engineer_weekly_plan import (
    create_engineer_week,add_week_item,check_week_item,set_week_item_status,
    weekly_summary,week_start_of,
)
from core.commercial.statement_basis import (
    choose_statement_mode,operator_price_status,set_operator_contract_price,
    review_contract_rates,validate_statement_pricing,
)
from core.drawings.takeoff_session import DrawingTakeoffSession


def test_each_engineer_has_independent_seven_day_plans_and_checklists():
    a=create_engineer_week([],"S1","مهندس سازه","1405/08/09",source_sha256="sha")
    assert len(a[0]["days"])==7
    assert a[0]["days"][0]["day_name"]=="شنبه"
    assert a[0]["days"][0]["jalali"]=="1405/08/09"
    assert a[0]["days"][6]["day_name"]=="جمعه"
    b=create_engineer_week(a,"M1","مهندس مکانیک","1405/08/10",source_sha256="sha")
    assert b[1]["week_start"]=="1405/08/09"
    assert len(b)==2
    with pytest.raises(ValueError,match="قبلاً"):
        create_engineer_week(b,"S1","نام دیگر","1405/08/11",source_sha256="sha")
    c=add_week_item(b,"S1","1405/08/09","1405/08/09",
        "بازدید کیفیت بتن",activity_id="concrete_frame",
        checklist=["تطبیق نقشه مصوب","بررسی آرماتور","ثبت گزارش"])
    assert sum(len(d["work_items"]) for d in c[1]["days"])==0
    record=c[0]["days"][0]["work_items"][0]
    assert record["source_ref"]==""
    assert record["status"]=="planned"
    with pytest.raises(ValueError,match="چک‌لیست"):
        set_week_item_status(c,"S1","1405/08/09","1405/08/09",
            record["id"],"done",operator="بازبین")
    for index in range(1,4):
        c=check_week_item(c,"S1","1405/08/09","1405/08/09",
            record["id"],f"check-{index}",done=True,operator="مهندس سازه")
    c=set_week_item_status(c,"S1","1405/08/09","1405/08/09",
        record["id"],"done",operator="ناظر مقیم")
    summary=weekly_summary(c,"S1","1405/08/09")
    assert summary["completed_items"]==1
    assert summary["checked_count"]==3
    assert weekly_summary(c,"M1","1405/08/09")["completed_items"]==0
    assert b[0]["days"][0]["work_items"]==[]  # immutable update
    c=check_week_item(c,"S1","1405/08/09","1405/08/09",
        record["id"],"check-2",done=False,operator="ناظر")
    assert weekly_summary(c,"S1","1405/08/09")["checked_count"]==2
    assert c[0]["days"][0]["work_items"][0]["status"]=="in_progress"


def test_engineer_week_and_optout_preferences_persist_without_auto_wbs():
    session=DrawingTakeoffSession()
    session.workflow_preferences={
        "source_sha256":"","pricing_mode":"contract_rates",
        "contract_price_entry":"operator_blank",
        "automatic_scheduling":False,
    }
    session.engineer_weekly_plans=create_engineer_week(
        [],"C1","مهندس برق","1406/01/01",source_sha256=""
    )
    assert session.workflow_plan is None
    restored=DrawingTakeoffSession.from_dict(session.to_dict())
    assert restored.workflow_plan is None
    assert restored.workflow_preferences["automatic_scheduling"] is False
    assert restored.workflow_preferences["pricing_mode"]=="contract_rates"
    assert restored.engineer_weekly_plans[0]["engineer_name"]=="مهندس برق"
    # 1406/01/01 was a Sunday, so its Saturday-based workweek starts
    # on the last day of Esfand 1405.
    assert restored.engineer_weekly_plans[0]["week_start"]=="1405/12/29"


def test_blank_price_is_not_zero_and_operator_must_enter_explicit_amount(tmp_path,monkeypatch):
    import core.reports.aec_office_package as office
    monkeypatch.setattr(office,"audit_boq",lambda project,require_pricebook=False:{
        "pricing_complete":all(x.get("unit_price") is not None for x in project.get("boq",[]))
    })
    project={"boq":[
        {"price_code":"C-1","item_code":"I-1","unit":"m2",
         "description":"دیوار بلوکی","unit_price":"125000"},
        {"price_code":"C-2","item_code":"I-2","unit":"count",
         "description":"درب ورودی","unit_price":"4500000"},
    ]}
    choose_statement_mode(project,"contract_rates","operator_blank")
    assert all(row["unit_price"] is None for row in project["boq"])
    assert project["boq"][0]["pre_operator_unit_price"]=="125000"
    assert operator_price_status(project)["missing_codes"]==["C-1","C-2"]
    assert not operator_price_status(project)["ready_for_review"]
    with pytest.raises(ValueError):
        review_contract_rates(project,tmp_path/"notyet.txt","ناظر")
    for invalid in ("",None,"nan","-1","0"):
        with pytest.raises(ValueError):
            set_operator_contract_price(project,"C-1",invalid,"اپراتور")
    first=set_operator_contract_price(project,"C-1","125000","اپراتور اول")
    assert first["ready_for_payment"] is False
    assert operator_price_status(project)["missing_codes"]==["C-2"]
    set_operator_contract_price(project,"C-2","4600000","اپراتور دوم")
    assert operator_price_status(project)["ready_for_review"]
    agreement=tmp_path/"contract.txt"
    agreement.write_text("agreed prices contract v1",encoding="utf-8")
    reviewed=review_contract_rates(project,agreement,"سرپرست دفتر فنی")
    assert reviewed["sha256"]
    assert validate_statement_pricing(project)["mode"]=="contract_rates"
    with pytest.raises(ValueError,match="قابل تغییر"):
        project["statement_periods"]=[{"number":1}]
        choose_statement_mode(project,"pricebook")
    project.pop("statement_periods")
    set_operator_contract_price(project,"C-2","4800000","اپراتور دوم")
    assert "statement_contract_rate_review" not in project
    with pytest.raises(ValueError,match="بازبینی"):
        validate_statement_pricing(project)


def test_prefilled_contract_rate_does_not_erase_existing_BOQ_values():
    p={"boq":[{"price_code":"W","unit_price":"750","item_code":"W","unit":"m"}]}
    choose_statement_mode(p,"contract_rates","prefilled")
    assert p["boq"][0]["unit_price"]=="750"
    assert p["statement_contract_price_entry"]=="prefilled"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(["StructuralPro engineer weekly tests"])


def test_real_qt_dialog_finance_first_and_optional_auto_wbs(qapp,tmp_path):
    import ezdxf
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from app.drawing_workflow_dialog import DrawingWorkflowIntakeDialog
    file=tmp_path/"one.dxf"
    dwg=ezdxf.new("R2018")
    dwg.modelspace().add_line((0,0),(2,4))
    dwg.saveas(file)
    widget=GraphicalTakeoffDialog()
    try:
        widget.show()
        widget.open_drawing(str(file))
        qapp.processEvents()
        intake=widget._workflow_intake_dialog
        assert intake is not None and intake.isVisible()
        assert intake.pricing_mode.currentData() is None
        assert intake.automatic_schedule.currentData() is None
        assert intake.automatic_schedule_selected() is False
        intake.pricing_mode.setCurrentIndex(2)
        assert intake.contract_price_entry.isEnabled()
        intake.contract_price_entry.setCurrentIndex(1)
        intake.automatic_schedule.setCurrentIndex(2)
        assert intake.automatic_schedule_selected() is False
        intake.begin.click()
        qapp.processEvents()
        assert widget.session.workflow_preferences["pricing_mode"]=="contract_rates"
        assert widget.session.workflow_preferences["contract_price_entry"]=="operator_blank"
        assert widget.session.workflow_preferences["automatic_scheduling"] is False
        assert widget.session.workflow_plan is None
        assert not widget.schedule_button.isEnabled()
        assert widget.weekly_button.isEnabled()
        widget.weekly_button.click()
        qapp.processEvents()
        weekly=widget._engineer_weekly_dialog
        assert weekly is not None and weekly.isVisible()
        weekly.engineer_id.setText("S1")
        weekly.engineer_name.setText("مهندس سازه")
        weekly.week_date.setText("1405/08/09")
        weekly.create_button.click()
        assert len(widget.session.engineer_weekly_plans)==1
        assert weekly.table.rowCount()==7
        assert weekly.table.item(0,0).text()=="شنبه"
        assert weekly.table.item(0,1).text()=="1405/08/09"
    finally:
        widget.close()
        qapp.processEvents()
