from core.projects.workflow import project_health, audit_project, export_package, import_package, copy_project
from core.takeoff.estimate_history import delta
from core.reports.custom import build_custom_report

def test_project_workflow_roundtrip(tmp_path):
    p={"id":"p1","name":"نمونه","takeoffs":[{"member_code":"F1","quantities":[{"amount":2,"unit":"m3"}]}]}
    assert project_health(p)["ready"]
    assert audit_project(p)["takeoff_count"]==1
    q=tmp_path/"p.spro"
    export_package(p,q)
    assert import_package(q)["name"]=="نمونه"
    assert copy_project(p,"p2")["id"]=="p2"

def test_estimate_delta_and_custom_report():
    d=delta([{"code":"A","q":1}],[{"code":"A","q":2},{"code":"B","q":1}])
    assert len(d["added"])==1 and len(d["changed"])==1
    assert build_custom_report([{"a":1,"b":2}],["b","a"])[0]=={"b":2,"a":1}
