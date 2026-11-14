"""Independent integer-day oracles and regressions for the two schedule paths."""
from copy import deepcopy
from itertools import product

import pytest

from core.drawings.workflow_planning import edit_activity
from core.platform.application import StructuralProApp
from core.projects.crew_capacity import level_shared_crew_resources
from core.projects.engineer_weekly_plan import check_week_item
from core.projects.iran_worksite_calendar import calendarize, make_calendar
from core.projects.precedence_model import calculate_precedence
from core.projects.scheduling import cpm
from core.projects.weekly_ownership import derive_weeks, recommended_team
from test_phase4_structure import activity, cmd, structure


ALL_DAYS = {"weekdays": list(range(7)), "holidays": []}
START = "2026-01-02"
FIELDS = ("es", "ef", "ls", "lf", "total_float", "free_float")
OFFSET_FIELDS = (
    "start_workday_offset", "end_workday_offset",
    "latest_start_workday_offset", "latest_end_workday_offset",
    "total_float_workdays", "free_float_workdays",
)


def plan_for(durations, relations):
    return {"tasks": [
        {"id": name, "duration_days": duration,
         "predecessors": [pred for pred, succ, _, _ in relations if succ == name],
         "links": [{"predecessor": pred, "type": kind, "lag_days": lag}
                   for pred, succ, kind, lag in relations if succ == name]}
        for name, duration in durations.items()
    ]}


def calendar_cpm(durations, relations, **kwargs):
    return cpm(
        [{"id": name, "duration": duration} for name, duration in durations.items()],
        [{"pred": a, "succ": b, "type": kind, "lag": lag}
         for a, b, kind, lag in relations],
        **{"start": START, "calendar": ALL_DAYS, **kwargs},
    )


def enumerated_oracle(durations, relations, horizon):
    """Exhaust finite start vectors against endpoint inequalities, with no graph passes."""
    names = tuple(durations)
    feasible = []
    for vector in product(*(range(horizon - durations[k] + 1) for k in names)):
        begins = dict(zip(names, vector))
        ends = {k: begins[k] + durations[k] for k in names}
        events = {"S": begins, "F": ends}
        if all(events[kind[1]][b] >= events[kind[0]][a] + lag
               for a, b, kind, lag in relations):
            feasible.append((max(ends.values()), vector))
    finish = min(end for end, _ in feasible)
    optimal = [vector for end, vector in feasible if end == finish]
    early = tuple(map(min, zip(*optimal)))
    late = tuple(map(max, zip(*optimal)))
    assert early in optimal
    expected = {}
    for i, name in enumerate(names):
        free = max(v[i] - early[i] for v in optimal if v[:i] + v[i + 1:] == early[:i] + early[i + 1:])
        expected[name] = (early[i], early[i] + durations[name], late[i],
                          late[i] + durations[name], late[i] - early[i], free)
    return finish, expected


@pytest.mark.parametrize("kind", ["FS", "SS", "FF", "SF"])
@pytest.mark.parametrize("lag", [-2, 0, 2])
def test_shared_offsets_match_independent_endpoint_oracle(kind, lag):
    check_both_engines({"A": 4, "B": 2}, [("A", "B", kind, lag)], 10)


@pytest.mark.parametrize(("durations", "relations", "horizon"), [
    ({"A": 2, "B": 3, "M": 0}, [("A", "B", "FS", 0), ("B", "M", "FS", 0)], 6),
    ({"A": 1, "B": 2, "C": 2, "M": 0}, [
        ("A", "B", "FS", 0), ("A", "C", "FS", 0),
        ("B", "M", "FS", 0), ("C", "M", "FS", 0),
    ], 5),
    ({"A": 4, "B": 2, "C": 1, "D": 3}, [
        ("A", "B", "FF", -1), ("A", "C", "SS", 1), ("B", "D", "SF", 2),
    ], 7),
    ({"A": 3, "B": 2, "C": 3, "M": 0}, [("A", "M", "FS", 0)], 5),
], ids=["chain-and-milestone", "two-tied-critical-paths", "mixed-parallel-ends", "multiple-ends"])
def test_shared_networks_match_independent_endpoint_oracle(durations, relations, horizon):
    check_both_engines(durations, relations, horizon)


def check_both_engines(durations, relations, horizon):
    finish, expected = enumerated_oracle(durations, relations, horizon)
    offsets = calculate_precedence(plan_for(durations, relations), include_cpm=True)
    calendar = calendar_cpm(durations, relations)
    assert offsets["indicative_total_workdays"] == calendar["duration"] == finish
    assert {t["id"]: tuple(t[key] for key in OFFSET_FIELDS) for t in offsets["tasks"]} == expected
    assert {key: tuple(row[field] for field in FIELDS) for key, row in calendar["activities"].items()} == expected
    assert set(calendar["critical_ids"]) == {name for name, row in expected.items() if row[4] == 0}


@pytest.mark.parametrize(("durations", "relations"), [
    ({"A": -1}, []),
    ({"A": True}, []),
    ({"A": 1.5}, []),
    ({"A": 1, "B": 2}, [("A", "B", "FS", 0), ("B", "A", "SS", -1)]),
    ({"A": 1, "B": 2}, [("missing", "B", "FS", 0)]),
    ({"A": 1, "B": 2}, [("A", "B", "FS", 0), ("A", "B", "SS", 0)]),
], ids=["negative-duration", "boolean-duration", "fractional-duration", "cycle", "missing", "conflicting-links"])
def test_both_engines_reject_invalid_network(durations, relations):
    with pytest.raises(ValueError):
        calculate_precedence(plan_for(durations, relations), include_cpm=True)
    with pytest.raises(ValueError):
        calendar_cpm(durations, relations)


def test_both_engines_reject_duplicate_activity_id():
    offset = {"id": "A", "duration_days": 1, "predecessors": []}
    with pytest.raises(ValueError):
        calculate_precedence({"tasks": [offset, dict(offset)]}, include_cpm=True)
    task = {"id": "A", "duration": 1}
    with pytest.raises(ValueError):
        cpm([task, dict(task)], [], start=START, calendar=ALL_DAYS)


def test_offset_error_preserves_inputs_for_an_invalid_later_task():
    plan = plan_for({"A": 2, "B": 3}, [("MISSING", "B", "FS", 0)])
    before = deepcopy(plan)
    with pytest.raises(ValueError):
        calculate_precedence(plan, include_cpm=True)
    assert plan == before


def test_recomputing_draft_drops_float_from_its_old_network():
    plan = calculate_precedence(plan_for({"A": 2, "B": 1}, []), include_cpm=True)
    plan["tasks"][1]["duration_days"] = 4
    calculate_precedence(plan)
    assert "cpm_scope" not in plan
    assert all(not set(OFFSET_FIELDS[2:]).intersection(task) for task in plan["tasks"])
    assert plan["indicative_total_workdays"] == 4


@pytest.mark.parametrize("mode", ["offset-cpm", "crew-leveling"])
def test_reverse_ordered_long_chain_without_python_recursion(mode):
    n = 1500
    ids = [str(i) for i in range(n)]
    plan = plan_for({k: 1 for k in reversed(ids)}, [
        (a, b, "FS", 0) for a, b in zip(ids, ids[1:])
    ])
    if mode == "offset-cpm":
        result = calculate_precedence(plan, include_cpm=True)
    else:
        for task in plan["tasks"]:
            task["crew_pool"] = "C"
        result = level_shared_crew_resources(plan, {"C": 1})
        assert result["resource_conflict_count"] == 0
        assert result["resource_leveling_status"] == "PROPOSED_UNAPPROVED"
    assert result["indicative_total_workdays"] == n
    for task in result["tasks"]:
        i = int(task["id"])
        assert (task["start_workday_offset"], task["end_workday_offset"]) == (i, i + 1)
        if mode == "offset-cpm":
            assert tuple(task[k] for k in OFFSET_FIELDS) == (i, i + 1, i, i + 1, 0, 0)


@pytest.mark.parametrize(("field", "value"), [
    ("deadline", "2026-01-02"), ("calendar_id", "crew-calendar"),
    ("actual_start", "2026-01-03"), ("remaining_duration", 1),
])
def test_calendar_cpm_rejects_unsupported_schedule_inputs(field, value):
    with pytest.raises(ValueError):
        cpm([{"id": "A", "duration": 3, field: value}], [], start=START, calendar=ALL_DAYS)


@pytest.mark.parametrize("field", ["calendar", "not_before"])
def test_offset_cpm_rejects_date_or_calendar_inputs(field):
    plan = plan_for({"A": 1}, [])
    if field == "calendar":
        plan[field] = ALL_DAYS
    else:
        plan["tasks"][0][field] = "2026-01-06"
    with pytest.raises(ValueError):
        calculate_precedence(plan, include_cpm=True)


def test_calendar_start_not_before_and_milestone_are_boundary_dates():
    cal = {"weekdays": [0, 1, 2, 3, 4], "holidays": ["2027-03-22", "2027-03-23"]}
    links = [("A", "M", "FS", 0)]
    # Independent enumeration after Sat Mar 20: Wed 24, Thu 25, Fri 26, Mon 29.
    result = calendar_cpm({"A": 2, "M": 0}, links, start="2027-03-20", calendar=cal)
    assert result["start"] == "2027-03-24" and result["finish_boundary"] == "2027-03-26"
    assert result["activities"]["A"]["finish"] == "2027-03-25"
    assert result["activities"]["M"]["finish"] == "2027-03-26"
    constrained = cpm([{"id": "A", "duration": 1, "not_before": "2027-03-27"}], [],
                      start="2027-03-20", calendar=cal)
    assert constrained["activities"]["A"]["start"] == "2027-03-29"


def test_jalali_summary_includes_terminal_zero_day_milestone():
    plan = plan_for({"A": 2, "M": 0}, [("A", "M", "FS", 0)])
    jalali = make_calendar(start_date="1405/12/29", working_weekdays=[0, 1, 2, 3, 4],
                           official_holidays=False, extra_holidays=["1406/01/02", "1406/01/03"])
    result = calendarize(plan, jalali)
    work, milestone = result["tasks"]
    assert (work["start_jalali"], work["finish_jalali"]) == ("1406/01/04", "1406/01/05")
    assert milestone["start_jalali"] == milestone["finish_jalali"] == "1406/01/06"
    assert result["scheduled_end_jalali"] == "1406/01/06"
    assert result["calendar_approved"] is False


@pytest.mark.parametrize("change", ["calendar", "crew", "duration", "predecessor"])
def test_weekly_review_is_revoked_and_archived_after_schedule_input_change(change):
    source = "synthetic-drawing-revision"
    plan = plan_for({"A": 2, "B": 0}, [])
    plan.update(source_sha256=source, status="DRAFT_UNAPPROVED")
    plan["tasks"][0].update(title="دیوار", discipline="architecture", crew="Crew A")
    team = recommended_team(["سرپرست آزمایشی"])
    calendar = make_calendar(start_date="1405/08/09", official_holidays=False)
    dated = calendarize(plan, calendar)
    day = dated["tasks"][0]["start_jalali"]
    week = derive_weeks(team, dated, day, [], source)["plans"][0]
    row = next(x for d in week["days"] for x in d["work_items"])
    signed = check_week_item([week], "supervisor-1", week["week_start"], day, row["id"],
                             "check-1", done=True, operator="بازبین آزمایشی")
    if change == "calendar":
        updated = calendarize(dated, make_calendar(start_date="1405/08/09",
                              official_holidays=False, extra_holidays=["1405/08/20"]))
    elif change == "crew":
        updated = edit_activity(dated, "A", crew="Crew B")
    elif change == "duration":
        updated = edit_activity(dated, "A", duration_days=3)
    else:
        updated = edit_activity(dated, "A", predecessors=["B"])
    if change != "duration":
        assert [(t["start_jalali"], t["finish_jalali"]) for t in dated["tasks"]] == [
            (t["start_jalali"], t["finish_jalali"]) for t in updated["tasks"]
        ]
    review = derive_weeks(team, updated, day, signed, source)
    assert row["id"] in review["invalidated_signed_checks"]
    current_week = review["plans"][0]
    current_row = next(x for d in current_week["days"] for x in d["work_items"] if x["id"] == row["id"])
    assert current_row["review_required"] and not current_row["checklist"][0]["done"]
    assert current_row["checklist"][0]["checked_by"] is None
    historic = current_week["invalidated_inspection_history"][0]["old_signed_record"]
    assert historic["checklist"][0]["checked_by"] == "بازبین آزمایشی"
    assert historic["checklist"][0]["done"]


@pytest.mark.parametrize("invalid", ["cycle", "over-horizon", "deadline"])
def test_invalid_edit_is_atomic_even_in_partially_configured_sqlite_schedule(tmp_path, invalid):
    service = StructuralProApp(tmp_path)
    try:
        service.create_project("Synthetic schedule", "P")
        structure(service)
        for name in ("A", "B", "C"):
            activity(service, name)
        cmd(service, "schedule_calendar", start=START, calendar=ALL_DAYS)
        cmd(service, "schedule_activity", id="A", duration=2,
            relationships=[{"pred": "B", "succ": "A", "type": "FS", "lag": 0}])
        before = service.open_project("P")
        before_digest = service.store.current_digest("P")
        revisions = service.store.revisions("P")
        invalid_data = {
            "cycle": {"duration": 1, "relationships": [{"pred": "A", "succ": "B", "type": "FS", "lag": 0}]},
            "over-horizon": {"duration": 100001, "relationships": []},
            "deadline": {"duration": 1, "relationships": [], "deadline": "2026-01-05"},
        }
        with pytest.raises(ValueError):
            cmd(service, "schedule_activity", id="B", **invalid_data[invalid])
        assert service.open_project("P") == before
        assert service.store.current_digest("P") == before_digest
        assert service.store.revisions("P") == revisions
    finally:
        service.store.close()


def test_leveling_accepts_the_same_default_zero_lag_as_offset_scheduling():
    plan = plan_for({"A": 2, "B": 1}, [("A", "B", "FS", 0)])
    plan["tasks"][1]["links"][0].pop("lag_days")
    leveled = level_shared_crew_resources(plan, {})
    assert leveled["indicative_total_workdays"] == 3
    assert leveled["tasks"][1]["start_workday_offset"] == 2


def test_weekly_reviews_are_preserved_when_the_schedule_inputs_match():
    plan = plan_for({"A": 1}, [])
    plan["source_sha256"] = "same-synthetic-source"
    plan["tasks"][0].update(title="دیوار", discipline="architecture", crew="Crew A")
    plan = calendarize(plan, make_calendar(start_date="1405/08/09", official_holidays=False))
    team = recommended_team(["بازبین"])
    day = "1405/08/09"
    week = derive_weeks(team, plan, day, [], plan["source_sha256"])["plans"][0]
    row = week["days"][0]["work_items"][0]
    signed = check_week_item([week], week["engineer_id"], week["week_start"], day, row["id"],
                             "check-1", done=True, operator="بازبین")
    refreshed = derive_weeks(team, deepcopy(plan), day, signed, plan["source_sha256"])
    assert not refreshed["invalidated_signed_checks"]
    assert refreshed["plans"][0]["days"][0]["work_items"][0]["checklist"][0]["checked_by"] == "بازبین"


def test_calendar_and_relationship_edits_leave_audited_baseline_and_finance_intact(tmp_path):
    service = StructuralProApp(tmp_path)
    try:
        service.create_project("Synthetic baseline", "P")
        structure(service)
        activity(service, "A")
        activity(service, "B")
        cmd(service, "schedule_calendar", start="2026-01-02", calendar=ALL_DAYS)
        cmd(service, "schedule_activity", id="A", duration=2, relationships=[])
        cmd(service, "schedule_activity", id="B", duration=1,
            relationships=[{"pred": "A", "succ": "B", "type": "FS", "lag": 0}])
        baseline = cmd(service, "schedule_baseline", reference="TEST-BASE", approved_by="reviewer")
        before = service.open_project("P")
        cmd(service, "schedule_calendar", start="2026-01-02",
            calendar={"weekdays": [0, 1, 2, 3, 4], "holidays": ["2026-01-05"]})
        cmd(service, "schedule_activity", id="A", duration=3, relationships=[])
        cmd(service, "schedule_activity", id="B", duration=1,
            relationships=[{"pred": "A", "succ": "B", "type": "SS", "lag": 1}])
        current = service.project_schedule("P")
        assert baseline["result"]["activities"]["B"]["finish"] == "2026-01-04"
        assert (current["duration"], current["activities"]["B"]["start"],
                current["finish_boundary"]) == (3, "2026-01-06", "2026-01-08")
        after = service.open_project("P")
        assert after["schedule_baselines"] == [baseline]
        assert baseline["approved_by"] == "reviewer" and baseline["version"] == 1
        assert [r["op"] for r in after["project_control_history"][-3:]] == [
            "schedule_calendar", "schedule_activity", "schedule_activity"
        ]
        for key in ("boq", "financial_records", "statement_periods"):
            assert after.get(key) == before.get(key)
        service.store.close()
        service = StructuralProApp(tmp_path)
        assert service.open_project("P") == after
        assert service.project_schedule("P") == current
    finally:
        service.store.close()


def test_parallel_critical_activities_are_not_displayed_as_one_path(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.project_controls_workspace import ProjectControlsWorkspace

    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path)
    view = None
    try:
        service.create_project("Synthetic parallel paths", "P")
        structure(service)
        activity(service, "A")
        activity(service, "B")
        cmd(service, "schedule_calendar", start=START, calendar=ALL_DAYS)
        for name in ("A", "B"):
            cmd(service, "schedule_activity", id=name, duration=2, relationships=[])
        current = service.project_schedule("P")
        assert current["relationships"] == [] and current["critical_ids"] == ["A", "B"]
        view = ProjectControlsWorkspace(service, "P")
        assert view.schedule_info.text().startswith("فعالیت‌های بحرانی: A, B")
    finally:
        if view is not None:
            view.close()
            qt.processEvents()
        service.store.close()
