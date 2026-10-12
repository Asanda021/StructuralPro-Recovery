"""Priority 53 — large-project performance acceptance."""

from core.platform.application import StructuralProApp


def test_priority_53_large_project_snapshot_and_pagination(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    project_id = "large-project-53"
    project = app.create_project("Large Project", project_id)

    # Model a realistic large in-memory project without invoking the calculator
    # 10k+ rows is the repository's documented large-project threshold.
    project["takeoffs"] = [
        {"id": str(i), "source_id": f"S-{i}", "quantities": [{"amount": i + 1}]}
        for i in range(12000)
    ]
    project["boq"] = [
        {"item_code": f"BOQ-{i}", "quantity": i + 1, "unit": "m3"}
        for i in range(12000)
    ]
    app.store.save(project_id, project)

    snapshot = app.project_performance_snapshot(project_id)
    assert snapshot["large_project"] is True
    assert snapshot["total_collection_rows"] >= 24000
    assert snapshot["largest_collection_count"] == 12000
    assert snapshot["payload_bytes"] > 0

    first = app.project_collection_page(project_id, "takeoffs", page=1, page_size=250)
    last = app.project_collection_page(project_id, "takeoffs", page=48, page_size=250)
    assert first["total"] == 12000
    assert len(first["items"]) == 250
    assert first["has_next"] is True
    assert last["has_next"] is False
    assert len(last["items"]) == 250
    assert first["items"][0]["id"] == "0"
    assert last["items"][-1]["id"] == "11999"
