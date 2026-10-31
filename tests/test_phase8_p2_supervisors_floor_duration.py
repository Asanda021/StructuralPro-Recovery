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
