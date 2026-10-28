"""E4 read-only BOQ navigation must use the same identity as canonical search."""
from copy import deepcopy

from PySide6.QtWidgets import QApplication, QTableWidget

from app.project_search_panel import display_verified_boq_row
from core.search.global_search import search_project


def test_boq_search_id_and_row_id_do_not_cross_select_another_row():
    """Current RED: UI prioritizes row_id while search prioritizes id."""
    app = QApplication.instance() or QApplication([])
    project = {
        "id": "P", "name": "Explicit BOQ identity",
        "boq": [
            {"id": "ENTRY-01", "row_id": "PRINT-02",
             "description": "کف طبقه", "quantity": "17.25", "unit": "m2"},
            {"id": "ENTRY-02", "row_id": "ENTRY-01",
             "description": "سقف طبقه", "quantity": "29.50", "unit": "m2"},
        ],
    }
    before = deepcopy(project)
    hits = [x for x in search_project(project, "کف طبقه")
            if x["kind"] == "boq" and x["route"] == "boq"]
    assert len(hits) == 1 and hits[0]["entity_id"] == "ENTRY-01"
    assert hits[0]["link_status"] != "ambiguous_record"
    table = QTableWidget(0, 6)
    try:
        selected = display_verified_boq_row(project, hits[0]["entity_id"], table)
        assert selected == 0, "Search must never open the other BOQ row by alias"
        assert table.currentRow() == 0
        assert table.item(0, 1).text() == "کف طبقه"
        assert table.item(0, 2).text() == "17.25"
        assert {x.row() for x in table.selectionModel().selectedIndexes()} == {0}
        assert project == before, "Read-only BOQ browsing changed engineering/financial data"
    finally:
        table.close()
        app.processEvents()


def test_boq_search_id_and_row_id_can_target_second_row():
    app = QApplication.instance() or QApplication([])
    project = {
        "id": "P", "name": "Explicit BOQ identity",
        "boq": [
            {"id": "ENTRY-01", "row_id": "PRINT-02", "description": "کف طبقه"},
            {"id": "ENTRY-02", "row_id": "ENTRY-01", "description": "سقف طبقه"},
        ],
    }
    hits = [x for x in search_project(project, "سقف طبقه")
            if x["kind"] == "boq" and x["route"] == "boq"]
    assert len(hits) == 1 and hits[0]["entity_id"] == "ENTRY-02"
    table = QTableWidget(0, 6)
    try:
        assert display_verified_boq_row(project, hits[0]["entity_id"], table) == 1
        assert table.currentRow() == 1
        assert table.item(1, 1).text() == "سقف طبقه"
    finally:
        table.close()
        app.processEvents()
