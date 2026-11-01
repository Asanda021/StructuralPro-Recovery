"""SYNTHETIC WBS/session data; real scheduling, signing and serialization."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.drawings.workflow_planning import new_workflow_plan, sync_measured_items, edit_activity, apply_resource_limits
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.projects.weekly_ownership import recommended_team, derive_weeks
from core.projects.engineer_weekly_plan import check_week_item
from core.projects.iran_worksite_calendar import make_calendar, calendarize


@pytest.mark.parametrize("change", ["quantity", "source_ref", "review_digest"])
def test_manually_timed_work_revokes_inspection_on_changed_measurement(change):
    item=SimpleNamespace(id="takeoff-1", label="دیوار بلوکی", takeoff_code="",
        quantity=96, unit="m2", source_ref="source-row-A",
        cad_evidence={"review":{"digest":"review-one"}})
    plan=new_workflow_plan(drawing_source="drawing.dxf",source_sha256="sha",
                            structure="concrete",disciplines=["architecture"])
    plan=edit_activity(plan,"block_wall",duration_days=4)
    plan=sync_measured_items(plan,[item])
    plan=calendarize(plan,make_calendar(start_date="1405/08/09"))
    task=next(t for t in plan["tasks"] if t["id"]=="block_wall")
    day=task["start_jalali"]
    team=recommended_team(["سرپرست"])
    weeks=derive_weeks(team,plan,day,[],"sha")["plans"]
    week=weeks[0]
    row=next(x for d in week["days"] for x in d["work_items"] if x["activity_id"]=="block_wall")
    weeks=check_week_item(weeks,"supervisor-1",week["week_start"],day,row["id"],
                          "check-1",done=True,operator="بازبین مستقل")
    if change=="quantity":item.quantity=97
    elif change=="source_ref":item.source_ref="source-row-B"
    else:item.cad_evidence["review"]["digest"]="review-two"
    updated=sync_measured_items(deepcopy(plan),[item])
    result=derive_weeks(team,updated,day,weeks,"sha")
    new=next(x for d in result["plans"][0]["days"] for x in d["work_items"] if x["id"]==row["id"])
    assert not new["checklist"][0]["done"]
    assert new["checklist"][0]["checked_by"] is None
    assert result["invalidated_signed_checks"]
    assert result["plans"][0]["invalidated_inspection_history"]
    assert next(t for t in updated["tasks"] if t["id"]=="block_wall")["duration_days"]==4


def test_removed_supervisor_loses_active_assignment_but_keeps_signed_history():
    plan={"source_sha256":"sha","calendar":make_calendar(start_date="1405/08/09"),
          "tasks":[{"id":"wiring","title":"سیم‌کشی برق","discipline":"electrical",
             "duration_days":1,"start_jalali":"1405/08/09","finish_jalali":"1405/08/09"}]}
    first=recommended_team(["سازه","معماری","مکانیک","برق"])
    weeks=derive_weeks(first,plan,"1405/08/09",[],"sha")["plans"]
    old=next(w for w in weeks if w["engineer_id"]=="supervisor-4")
    row=old["days"][0]["work_items"][0]
    weeks=check_week_item(weeks,"supervisor-4",old["week_start"],"1405/08/09",row["id"],
                         "check-1",done=True,operator="بازبین")
    second=recommended_team(["سرپرست کل"])
    result=derive_weeks(second,plan,"1405/08/09",weeks,"sha")
    inactive=next(w for w in result["plans"] if w["engineer_id"]=="supervisor-4")
    assert not any(x.get("origin")=="schedule_generated" for d in inactive["days"] for x in d["work_items"])
    assert inactive["invalidated_inspection_history"][0]["old_signed_record"]["checklist"][0]["done"]
    assert inactive["assignment_status"]=="INACTIVE_REASSIGNED"


def test_saved_levelled_session_restores_capacity_safe_dates(tmp_path):
    src=tmp_path/"source.dxf";src.write_bytes(b"synthetic source identity only")
    session=DrawingTakeoffSession(str(src))
    plan=new_workflow_plan(drawing_source=str(src),source_sha256=session.source_sha256,
                          structure="concrete",disciplines=["mechanical","electrical"])
    for key in ("rough_mechanical","rough_electrical"):
        plan=edit_activity(plan,key,crew="اکیپ مشترک")
    plan=calendarize(plan,make_calendar(start_date="1405/08/09"))
    plan=apply_resource_limits(plan,{"اکیپ مشترک":1},level=True)
    session.workflow_plan=plan
    loaded=DrawingTakeoffSession.from_dict(session.to_dict()).workflow_plan
    def offsets(p):
        return [(t["id"],t["start_workday_offset"],t["end_workday_offset"],
                 t["start_jalali"],t["finish_jalali"]) for t in p["tasks"]]
    assert offsets(loaded)==offsets(plan)
    assert loaded["resource_leveling_status"]=="PROPOSED_UNAPPROVED"
    assert not loaded["resource_conflicts"]
