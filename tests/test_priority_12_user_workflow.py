from core.projects.user_workflow import evaluate_workflow, stage_status


def test_new_project_starts_with_project_stage():
    snapshot = evaluate_workflow({"id": "P1", "name": "Demo", "takeoffs": [], "boq": []})
    assert snapshot["current_stage"] == "takeoff"
    assert snapshot["completed"] == 1
    assert snapshot["stages"][0]["status"] == "complete"
    assert snapshot["stages"][1]["status"] == "ready"
    assert stage_status({"id": "P1", "name": "Demo"}, "boq") == "blocked"


def test_end_to_end_workflow_advances_deterministically():
    project = {
        "id": "P1",
        "name": "Demo",
        "takeoffs": [{"id": "1"}],
        "boq": [{"price_code": "A", "quantity": 10, "current_quantity": 2}],
        "estimate": {"boq": [{"price_code": "A"}], "summary": {"line_count": 1}},
        "statement_periods": [{"number": 1}],
        "cost_entries": [{"id": 1}],
        "financial_documents": [{"id": 1}],
    }
    snapshot = evaluate_workflow(project)
    assert snapshot["completion_percent"] == 100.0
    assert snapshot["current_stage"] == "report"
    assert all(item["status"] == "complete" for item in snapshot["stages"])
    assert snapshot["counts"] == {
        "takeoffs": 1,
        "boq": 1,
        "statement_periods": 1,
        "financial_records": 2,
    }


def test_missing_prerequisite_blocks_downstream_stages():
    project = {
        "id": "P1",
        "name": "Demo",
        "takeoffs": [],
        "boq": [{"price_code": "A", "quantity": 10}],
        "estimate": {"summary": {"line_count": 1}},
    }
    snapshot = evaluate_workflow(project)
    statuses = {item["key"]: item["status"] for item in snapshot["stages"]}
    assert statuses["takeoff"] == "ready"
    assert statuses["boq"] == "blocked"
    assert statuses["estimate"] == "blocked"
    assert statuses["report"] == "blocked"
    assert snapshot["blockers"]
