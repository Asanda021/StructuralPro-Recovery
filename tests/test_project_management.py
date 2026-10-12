from core.projects.management import ProjectManagement,ScheduleTask,DailyReport,ResourceRecord,MaterialRecord,MeetingRecord
import pytest

def test_priority6_management_dashboard_and_schedule():
    m=ProjectManagement(tasks=[ScheduleTask("T1","Foundation","1405/07/01","1405/07/05",progress=40)],
        daily_reports=[DailyReport("R1","1405/07/02","work",40)],
        resources=[ResourceRecord("E1","crew","labor",3,"person")],
        materials=[MaterialRecord("M1","concrete",12,"m3","1405/07/02")],
        meetings=[MeetingRecord("MT1","1405/07/02","coordination")])
    assert m.schedule_summary()=={"task_count":1,"completed_tasks":0,"average_progress":40}
    d=m.dashboard(); assert d["material_record_count"]==1 and d["daily_report_count"]==1
    assert m.actual_vs_plan()[0]["delay"] is False

def test_priority6_rejects_invalid_progress_and_negative_resources():
    with pytest.raises(ValueError):
        ProjectManagement(tasks=[ScheduleTask("T1","x","a","b",progress=101)])
    with pytest.raises(ValueError):
        ProjectManagement(resources=[ResourceRecord("R1","x","equipment",-1)])

def test_priority6_duplicate_ids_are_rejected_atomically():
    m=ProjectManagement(tasks=[ScheduleTask("T1","x","a","b")])
    with pytest.raises(ValueError): m.add_task(ScheduleTask("T1","y","a","b"))
    assert len(m.tasks)==1
