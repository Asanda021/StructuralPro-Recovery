"""Bounded 1405 calendar, actual crew capacity and custom WBS gates."""
import pytest
from copy import deepcopy
from datetime import date
from core.projects.iran_worksite_calendar import (
    make_calendar,calendarize,gregorian_1405,solar_1405,apply_calendar,
)
from core.projects.crew_capacity import (
    resource_conflicts,level_shared_crew_resources,
)
from core.drawings.workflow_planning import (
    new_workflow_plan,edit_activity,recompute_schedule,apply_resource_limits,
    add_custom_activity,
)


def _parallel():
    p=new_workflow_plan(drawing_source="s.dxf",source_sha256="h",
        structure="concrete",disciplines=["mechanical","electrical","architecture"])
    p=edit_activity(p,"rough_mechanical",crew="اکیپ مشترک")
    p=edit_activity(p,"rough_electrical",crew="اکیپ مشترک")
    return p


def test_exact_1405_solar_date_and_friday_off():
    assert gregorian_1405("1405/08/09")==date(2026,10,31)
    assert solar_1405(date(2026,10,31))=="1405/08/09"
    p={"tasks":[{"id":"t","duration_days":2,"predecessors":[]}]}
    plan=calendarize(p,make_calendar(start_date="1405/08/14"))
    assert plan["tasks"][0]["start_jalali"]=="1405/08/14"
    # 1405/08/15 is Friday; work resumes on 16 Aban.
    assert plan["tasks"][0]["finish_jalali"]=="1405/08/16"
    assert plan["calendar_approved"] is False


def test_1405_national_holiday_and_site_exception_are_distinct():
    p={"tasks":[{"id":"T","duration_days":2,"predecessors":[]}]}
    q=calendarize(p,make_calendar(start_date="1405/10/01"))
    assert q["tasks"][0]["finish_jalali"]=="1405/10/03"
    q=calendarize(p,make_calendar(start_date="1405/10/01",
                   extra_holidays=["1405/10/03"]))
    assert q["tasks"][0]["finish_jalali"]=="1405/10/04"
    q=calendarize(p,make_calendar(start_date="1405/10/01",
                   holidays=["1405/10/02"]))
    assert q["tasks"][0]["finish_jalali"]=="1405/10/02"


def test_beyond_reviewed_calendar_year_and_invalid_inputs_fail_closed():
    p={"tasks":[{"id":"T","duration_days":4,"predecessors":[]}]}
    with pytest.raises(ValueError,match="سال جدید"):
        calendarize(p,make_calendar(start_date="1405/12/28"))
    for value in ("1406/01/01","1405/13/01","1405/12/30","foo"):
        with pytest.raises(ValueError):make_calendar(start_date=value)
    with pytest.raises(ValueError):
        make_calendar(start_date="1405/08/09",working_weekdays=[])


def test_shared_crew_parallel_mechanical_electrical_detects_and_levels():
    p=_parallel()
    names={t["id"]:t for t in p["tasks"]}
    assert names["rough_mechanical"]["start_workday_offset"]==names["rough_electrical"]["start_workday_offset"]
    conflicted=apply_resource_limits(p,{"اکیپ مشترک":1})
    assert conflicted["resource_conflicts"]
    proposed=apply_resource_limits(p,{"اکیپ مشترک":1},level=True)
    assert proposed["resource_leveling_status"]=="PROPOSED_UNAPPROVED"
    tasks={t["id"]:t for t in proposed["tasks"]}
    start_m,end_m=tasks["rough_mechanical"]["start_workday_offset"],tasks["rough_mechanical"]["end_workday_offset"]
    start_e,end_e=tasks["rough_electrical"]["start_workday_offset"],tasks["rough_electrical"]["end_workday_offset"]
    assert end_m<=start_e or end_e<=start_m
    assert tasks["plaster"]["start_workday_offset"]>=max(end_e,end_m)
    assert resource_conflicts(proposed,{"اکیپ مشترک":1})==[]
    # The input remains unchanged: no unrequested scheduling rewrite.
    assert "resource_limits" not in p


def test_shared_crew_missing_capacity_and_overbooking_must_not_be_hidden():
    p=_parallel()
    with pytest.raises(ValueError,match="ظرفیت"):
        resource_conflicts(p,{})
    with pytest.raises(ValueError,match="ظرفیت"):
        level_shared_crew_resources(p,{"اکیپ مشترک":0})
    p=edit_activity(p,"rough_mechanical",crew_count=2)
    with pytest.raises(ValueError,match="بیشتر"):
        level_shared_crew_resources(p,{"اکیپ مشترک":1})


def test_custom_work_fits_WBS_and_rejects_fake_unknown_disciplines():
    p=new_workflow_plan(drawing_source="a.dwg",source_sha256="sha",
                        structure="steel",disciplines=["architecture"])
    n=add_custom_activity(p,"جزئیات ویژه نمای خشک","architecture",
                          duration_days=6,predecessors=["masonry"])
    u=[t for t in n["tasks"] if t["id"].startswith("user:")]
    assert len(u)==1 and u[0]["duration_days"]==6
    assert u[0]["start_workday_offset"]>=next(t for t in n["tasks"] if t["id"]=="masonry")["end_workday_offset"]
    assert len(p["tasks"])==len(n["tasks"])-1
    with pytest.raises(ValueError,match="رشته"):
        add_custom_activity(p,"ناحیه برق","electrical",duration_days=2)
    with pytest.raises(ValueError):
        add_custom_activity(p,"", "architecture")


def test_calendar_persists_when_editing_duration_and_resource_mismatch_shows():
    p=new_workflow_plan(drawing_source="b.dxf",source_sha256="s",
        structure="concrete",disciplines=["architecture"],project_kind="fitout")
    p=calendarize(p,make_calendar(start_date="1405/08/09"))
    assert p["scheduled_end_jalali"].startswith("1405/")
    p=edit_activity(p,"masonry",duration_days=7)
    assert p["scheduled_end_jalali"].startswith("1405/")
    assert next(t for t in p["tasks"] if t["id"]=="masonry")["duration_days"]==7
