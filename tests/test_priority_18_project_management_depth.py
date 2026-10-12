import pytest

from core.projects.management import DailyReport, MaterialRecord, MeetingRecord, ProjectManagement, ResourceRecord, ScheduleTask


def test_priority18_weighted_schedule_and_overdue():
    m = ProjectManagement(tasks=[ScheduleTask("T1", "Foundation", "2026-01-01", "2026-01-05", progress=50, weight=2), ScheduleTask("T2", "Frame", "2026-01-06", "2026-01-10", progress=100, status="done", weight=1)])
    s = m.schedule_summary(as_of="2026-01-20")
    assert s["weighted_progress"] == pytest.approx(66.6666667)
    assert s["completed_tasks"] == 1
    assert s["overdue_tasks"] == 1


def test_priority18_dependencies_and_atomic_validation():
    m = ProjectManagement(tasks=[ScheduleTask("T1", "A", "2026-01-01", "2026-01-02", progress=100, status="done"), ScheduleTask("T2", "B", "2026-01-03", "2026-01-04", predecessor_ids=("T1",))])
    assert m.dependency_ready("T2") is True
    m.add_task(ScheduleTask("T3", "C", "2026-01-05", "2026-01-06", predecessor_ids=("T2",)))
    assert "T3" in m.blocked_tasks()
    with pytest.raises(ValueError):
        m.add_task(ScheduleTask("T4", "D", "2026-01-07", "2026-01-08", predecessor_ids=("UNKNOWN",)))


def test_priority18_actual_vs_plan_reports_delay_days():
    m = ProjectManagement(tasks=[ScheduleTask("T1", "Delayed", "2026-01-01", "2026-01-05", actual_end="2026-01-08", progress=100)])
    row = m.actual_vs_plan()[0]
    assert row["delay"] is True
    assert row["delay_days"] == 3


def test_priority18_operational_dashboard():
    m = ProjectManagement(daily_reports=[DailyReport("R1", "2026-01-10", "work", progress=40, workforce=8)], resources=[ResourceRecord("E1", "crew", "labor", 4)], materials=[MaterialRecord("M1", "concrete", 12, "m3")], meetings=[MeetingRecord("MT1", "2026-01-01", "coordination", actions="Follow up", follow_up_date="2026-01-05")])
    d = m.dashboard(as_of="2026-01-10")
    assert d["daily_progress"]["latest_progress"] == 40
    assert d["resources"]["quantity_by_kind"]["labor"] == 4
    assert d["materials"]["quantity_by_material"]["concrete|m3"] == 12
    assert d["meeting_followup_count"] == 1


def test_priority18_application_persistence():
    from core.platform.application import StructuralProApp
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        app = StructuralProApp(tmp)
        try:
            app.create_project("Demo", "P1")
            manager = ProjectManagement(tasks=[ScheduleTask("T1", "Foundation", "2026-01-01", "2026-01-05", progress=25)])
            snap = app.save_project_management("P1", manager)
            assert snap["project_id"] == "P1"
            assert snap["dashboard"]["task_count"] == 1
            loaded = app.project_management_snapshot("P1", as_of="2026-01-10")
            assert loaded["actual_vs_plan"][0]["progress"] == 25
        finally:
            app.store.close()
