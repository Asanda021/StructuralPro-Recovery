"""P8P2: one/four supervisor WBS-derived weeks and 5/6-floor planning."""
from types import SimpleNamespace
import pytest
from core.projects.weekly_ownership import define_team,recommended_team,derive_weeks
from core.projects.engineer_weekly_plan import check_week_item,weekly_summary,set_week_item_status
from core.projects.building_scale import building_scope,duration_comparison
from core.drawings.workflow_planning import new_workflow_plan,sync_measured_items
from core.projects.iran_worksite_calendar import make_calendar,calendarize


def _project():
    return {
        "source_sha256":"sha",
        "calendar":make_calendar(start_date="1405/08/09"),
        "calendar_approved":False,
        "tasks":[
            {"id":"foundation_rebar","title":"آرماتوربندی فونداسیون","discipline":"structure",
             "duration_days":2,"start_jalali":"1405/08/09","finish_jalali":"1405/08/10"},
            {"id":"plaster_base","title":"گچ خاک","discipline":"architecture",
             "duration_days":2,"start_jalali":"1405/08/09","finish_jalali":"1405/08/10"},
            {"id":"hvac_pipe","title":"لوله‌کشی تهویه","discipline":"mechanical",
             "duration_days":2,"start_jalali":"1405/08/09","finish_jalali":"1405/08/10"},
            {"id":"wiring","title":"سیم‌کشی برق","discipline":"electrical",
             "duration_days":2,"start_jalali":"1405/08/09","finish_jalali":"1405/08/10"},
        ],
    }


def test_one_supervisor_receives_all_four_disciplines_and_distinct_daily_checks():
    team=recommended_team(["مهندس سرپرست کل"])
    assert team["count"]==1 and len(team["people"][0]["trades"])==4
    result=derive_weeks(team,_project(),"1405/08/09",[],"sha")
    assert len(result["plans"])==1
    week=result["plans"][0]
    items=week["days"][0]["work_items"]
    assert len(items)==4
    assert {x["activity_id"] for x in items}=={
        "foundation_rebar","plaster_base","hvac_pipe","wiring"}
    rebar=next(x for x in items if x["activity_id"]=="foundation_rebar")
    electrical=next(x for x in items if x["activity_id"]=="wiring")
    assert any("میلگرد" in x["text"] for x in rebar["checklist"])
    assert any("سیم" in x["text"] for x in electrical["checklist"])
    assert rebar["checklist"]!=electrical["checklist"]
    assert all(row["origin"]=="schedule_generated" for row in items)
    assert all(row["review_required"] for row in items)


def test_four_supervisors_get_exclusive_trade_tasks_and_signed_checks_survive_sync():
    team=recommended_team(["سازه","معماری","مکانیک","برق"])
    first=derive_weeks(team,_project(),"1405/08/09",[],"sha")["plans"]
    assert len(first)==4
    for i,expected in enumerate(("foundation_rebar","plaster_base","hvac_pipe","wiring")):
        rows=first[i]["days"][0]["work_items"]
        assert len(rows)==1 and rows[0]["activity_id"]==expected
    electric=first[3]["days"][0]["work_items"][0]
    checked=check_week_item(first,"supervisor-4","1405/08/09","1405/08/09",
                            electric["id"],"check-1",done=True,operator="بازبین")
    again=derive_weeks(team,_project(),"1405/08/09",checked,"sha")["plans"]
    assert weekly_summary(again,"supervisor-4","1405/08/09")["checked_count"]==1
    changed=_project()
    changed["tasks"][3]["finish_jalali"]="1405/08/11"
    changed["tasks"][3]["duration_days"]=3
    replaced=derive_weeks(team,changed,"1405/08/09",again,"sha")["plans"]
    assert weekly_summary(replaced,"supervisor-4","1405/08/09")["checked_count"]==0
    assert len(replaced[3]["days"][2]["work_items"])==1
    assert all(len(replaced[x]["days"][0]["work_items"])==1 for x in (0,1,2))


def test_two_and_three_supervisors_cover_all_trades_without_unassigned_owner():
    for count in (2,3):
        group=recommended_team([f"مهندس {i}" for i in range(count)])
        assert group["count"]==count
        assert len(group["owners"])==4
        assert len(derive_weeks(group,_project(),"1405/08/09",[],"sha")["plans"])==count
    with pytest.raises(ValueError,match="بدون رشته"):
        define_team(["سرپرست ۱","سرپرست ۲"],
                    {"structure":0,"architecture":0,"mechanical":0,"electrical":0})


def test_source_mismatch_or_missing_master_start_never_invents_weekly_schedule():
    group=recommended_team(["سرپرست کل"])
    with pytest.raises(ValueError,match="نسخه"):
        derive_weeks(group,_project(),"1405/08/09",[],"other")
    p=_project()
    p["calendar"]["start_date"]=None
    with pytest.raises(ValueError,match="شروع"):
        derive_weeks(group,p,"1405/08/09",[],"sha")


def test_5_and_6_storey_projects_differ_only_for_confirmed_typical_floor_scope():
    sample=SimpleNamespace(id="R1",label="دیوار بلوکی تیپ",takeoff_code="",
        cad_evidence=None,quantity=96,unit="m2",source_ref="floor-1")
    def plan_for(floors,source):
        plan=new_workflow_plan(drawing_source="p.dxf",source_sha256="s",
             structure="concrete",disciplines=["architecture"])
        plan["building_scope"]=building_scope(floors,100,
            source_scope=source,repeat_floors=floors if source=="single_typical_floor" else 1)
        return sync_measured_items(plan,[sample])
    five=plan_for(5,"single_typical_floor")
    six=plan_for(6,"single_typical_floor")
    whole=plan_for(6,"whole_building")
    def row(p):return next(t for t in p["tasks"] if t["id"]=="block_wall")
    assert row(five)["scheduled_quantity"]=="480"
    assert row(six)["scheduled_quantity"]=="576"
    assert row(five)["duration_days"]==20
    assert row(six)["duration_days"]==24
    assert six["indicative_total_workdays"]>five["indicative_total_workdays"]
    assert row(whole)["scheduled_quantity"]=="96"
    assert row(whole)["duration_days"]==4
    assert row(whole)["quantity_multiplier_evidence"]["factor"]==1
    with pytest.raises(ValueError,match="نباید"):
        building_scope(6,100,source_scope="whole_building",repeat_floors=6)
    comparison=duration_comparison(96,"block_wall","m2",floor_counts=(5,6),crews=2)
    assert [x["expected_workdays"] for x in comparison]==[20,24]


def test_future_1411_calendar_is_not_expired_but_unverified_holidays_are_visible():
    plan={"tasks":[{"id":"x","duration_days":3,"predecessors":[]}]}
    scheduled=calendarize(plan,make_calendar(start_date="1411/01/05"))
    assert scheduled["scheduled_end_jalali"].startswith("1411/")
    assert scheduled["calendar_holiday_revision_required"]
    assert scheduled["unreviewed_holiday_years"]==[1411]



def test_area_and_six_storeys_change_provisional_master_plan_even_without_takeoff():
    from core.projects.building_scale import scaled_initial_wbs
    def estimate(floors):
        p=new_workflow_plan(drawing_source="a.dxf",source_sha256="sha",
                            structure="concrete",disciplines=["architecture"])
        size=building_scope(floors,100)
        return scaled_initial_wbs(p,size)
    five,six=estimate(5),estimate(6)
    a=next(t for t in five["tasks"] if t["id"]=="masonry")
    b=next(t for t in six["tasks"] if t["id"]=="masonry")
    assert b["duration_days"]>a["duration_days"]
    assert b["duration_status"]=="AREA_FLOOR_HEURISTIC_UNAPPROVED"
    assert six["size_reference"]=="5 typical floors × 100 m2 per floor"
    assert six["size_estimate_status"]=="OFFICE_HEURISTIC_UNAPPROVED"
    assert next(t for t in five["tasks"] if t["id"]=="foundation")["duration_days"]==next(
        t for t in six["tasks"] if t["id"]=="foundation"
    )["duration_days"]


def test_qt_jalali_calendar_picker_returns_selected_project_start():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtCore import QDate,QTimer
    from PySide6.QtWidgets import QApplication,QCalendarWidget,QPushButton
    from app.drawing_workflow_dialog import DrawingWorkflowIntakeDialog
    app=QApplication.instance() or QApplication(["Jalali Project Picker"])
    intake=DrawingWorkflowIntakeDialog("a.dxf",{"kind":"concrete"})
    seen=[]
    def choose_date():
        modal=app.activeModalWidget()
        picker=modal.findChild(QCalendarWidget,"VisibleProjectStartCalendar")
        assert picker is not None
        assert "Jalali" in picker.calendar().name()
        picker.setSelectedDate(QDate(2027,3,21))
        seen.append(picker.selectedDate())
        for control in modal.findChildren(QPushButton):
            if "تأیید تاریخ" in control.text():
                control.click()
                break
    try:
        QTimer.singleShot(0,choose_date)
        intake._choose_project_date()
        assert seen and intake.selected_start_date()=="1406/01/01"
    finally:
        intake.close()
        app.processEvents()



@pytest.mark.parametrize("count",[1,4])
def test_real_qt_cad_intake_assigns_supervisors_and_derives_week_from_wbs(tmp_path,count):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    import ezdxf
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app=QApplication.instance() or QApplication(["WBS Weekly Integration"])
    drawing=tmp_path/f"building_{count}.dxf"
    dxf=ezdxf.new("R2018")
    dxf.modelspace().add_line((0,0),(4,4))
    dxf.saveas(drawing)
    window=GraphicalTakeoffDialog()
    try:
        window.show()
        window.open_drawing(str(drawing))
        app.processEvents()
        dialog=window._workflow_intake_dialog
        assert dialog is not None and dialog.isVisible()
        dialog.pricing_mode.setCurrentIndex(1)
        dialog.automatic_schedule.setCurrentIndex(1)
        dialog.supervision_count.setCurrentIndex(count-1)
        dialog.disciplines["architecture"].setChecked(True)
        dialog.disciplines["mechanical"].setChecked(True)
        dialog.disciplines["electrical"].setChecked(True)
        dialog._selected_start_date="1405/08/09"
        dialog.typical_floor_area.setValue(100)
        dialog.building_floors.setValue(6)
        dialog.begin.click()
        app.processEvents()
        plan=window.session.workflow_plan
        assert plan is not None and plan["calendar"]["start_date"]=="1405/08/09"
        assert plan["building_scope"]["total_floors"]==6
        assert window.session.supervision_team["count"]==count
        assert window.weekly_button.isEnabled()
        window.open_engineer_weekly_plan()
        app.processEvents()
        assert len(window.session.engineer_weekly_plans)==count
        assert all(w["derived_from_wbs"] for w in window.session.engineer_weekly_plans)
        assert window._engineer_weekly_dialog.table.rowCount()>=7
    finally:
        window.close()
        app.processEvents()


def test_signed_weekly_check_is_revoked_if_takeoff_quantity_changes_without_date_change():
    team=recommended_team(["مهندس کل"])
    plan=_project()
    plan["tasks"][0]["scheduled_quantity"]="10"
    plan["tasks"][0]["linked_item_ids"]=["item-A"]
    weeks=derive_weeks(team,plan,"1405/08/09",[],"sha")["plans"]
    inspection=next(item for item in weeks[0]["days"][0]["work_items"]
                    if item["activity_id"]=="foundation_rebar")
    amended=check_week_item(
        weeks,"supervisor-1","1405/08/09","1405/08/09",
        inspection["id"],"check-1",done=True,operator="مهندس ناظر",
    )
    assert weekly_summary(amended,"supervisor-1","1405/08/09")["checked_count"]==1
    plan["tasks"][0]["scheduled_quantity"]="20"  # same dates, changed work volume
    regenerated=derive_weeks(team,plan,"1405/08/09",amended,"sha")
    assert inspection["id"] in regenerated["invalidated_signed_checks"]
    audit=regenerated["plans"][0]["invalidated_inspection_history"]
    assert len(audit)==1
    assert audit[0]["old_signed_record"]["checklist"][0]["checked_by"]=="مهندس ناظر"
    assert audit[0]["old_signed_record"]["schedule_snapshot"]["scheduled_quantity"]=="10"
    assert audit[0]["reason"]=="CHANGED_SOURCE_QUANTITY_OWNER_OR_WBS"
    assert weekly_summary(regenerated["plans"],"supervisor-1","1405/08/09")["checked_count"]==0
    unchanged=derive_weeks(team,plan,"1405/08/09",regenerated["plans"],"sha")["plans"]
    assert len(unchanged[0]["invalidated_inspection_history"])==1
    repl=next(item for item in regenerated["plans"][0]["days"][0]["work_items"]
              if item["activity_id"]=="foundation_rebar")
    assert repl["schedule_snapshot"]["scheduled_quantity"]=="20"
    assert not repl["checklist"][0]["done"]
    assert repl["status"]=="planned"


def test_reassigning_trade_flags_orphaned_signed_checks_from_original_supervisor():
    old=recommended_team(["سرپرست همه"])
    plan=_project()
    weeks=derive_weeks(old,plan,"1405/08/09",[],"sha")["plans"]
    x=next(item for item in weeks[0]["days"][0]["work_items"]
           if item["activity_id"]=="wiring")
    weeks=check_week_item(weeks,"supervisor-1","1405/08/09","1405/08/09",
        x["id"],"check-1",done=True,operator="ناظر")
    reassigned=define_team(["مهندس ۱","مهندس ۲"],
        {"structure":0,"architecture":0,"mechanical":1,"electrical":1})
    out=derive_weeks(reassigned,plan,"1405/08/09",weeks,"sha")
    assert x["id"] in out["invalidated_signed_checks"]
    assert out["plans"][0]["invalidated_inspection_history"][0]["reason"]=="REMOVED_OR_REASSIGNED_FROM_MASTER_WBS"
    assert not any(item["activity_id"]=="wiring"
                   for item in out["plans"][0]["days"][0]["work_items"])
    assert any(item["activity_id"]=="wiring"
               for item in out["plans"][1]["days"][0]["work_items"])


def test_renaming_responsible_supervisor_revokes_previous_signatures():
    group=recommended_team(["مهندس احمدی"])
    data=_project()
    weeks=derive_weeks(group,data,"1405/08/09",[],"sha")["plans"]
    row=next(item for item in weeks[0]["days"][0]["work_items"]
             if item["activity_id"]=="foundation_rebar")
    approved=check_week_item(
        weeks,"supervisor-1","1405/08/09","1405/08/09",
        row["id"],"check-1",done=True,operator="مهندس احمدی"
    )
    replacement=recommended_team(["مهندس رضایی"])
    updated=derive_weeks(replacement,data,"1405/08/09",approved,"sha")
    assert row["id"] in updated["invalidated_signed_checks"]
    assert weekly_summary(updated["plans"],"supervisor-1","1405/08/09")["checked_count"]==0
    first=next(item for item in updated["plans"][0]["days"][0]["work_items"]
               if item["activity_id"]=="foundation_rebar")
    assert first["schedule_snapshot"]["supervisor_name"]=="مهندس رضایی"
    assert first["status"]=="planned"
