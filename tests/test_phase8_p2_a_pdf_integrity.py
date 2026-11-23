"""Synthetic PDF → reviewed BOQ regressions with independent geometry oracles."""
from copy import deepcopy
from decimal import Decimal

import pymupdf
import pytest

from core.drawing.pdf_graphics import GraphicalPDFAdapter
from core.drawings.graphical_takeoff import Point
from core.drawings.pdf_takeoff import PDFPageInfo, PDFTakeoffAdapter
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.platform.application import StructuralProApp
from core.reports.aec_office_package import audit_boq


def pdf(path, *, content="vector", offset=0):
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=200)
        if content in {"scan", "hybrid"}:
            tile = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 24, 24), False)
            tile.clear_with(80)
            page.insert_image(pymupdf.Rect(30, 30, 160, 160), pixmap=tile)
        if content != "scan":
            page.draw_rect(pymupdf.Rect(9 + offset, 9, 20 + offset, 20))
        doc.save(path)
    return path


def line(session, *coordinates):
    session.calibrate(1, 100, 10)
    return session.add_length([Point(*p) for p in coordinates], takeoff_code="SYNTH-L")


def area(session, x1, x2, *, holes=()):
    if not session.calibration:
        session.calibrate(1, 100, 10)
    return session.add_area(
        [Point(x1, 80), Point(x2, 80), Point(x2, 180), Point(x1, 180)],
        holes=[[Point(*p) for p in ring] for ring in holes],
        takeoff_code="SYNTH-A",
    )


@pytest.fixture
def app(tmp_path):
    service = StructuralProApp(tmp_path / "store")
    service.create_project("آزمون مصنوعی متره", "P")
    yield service
    service.store.close()


def save(app, session):
    return app.save_drawing_takeoff_session("P", session)


def commit(app, receipt, item):
    return app.commit_drawing_takeoff_to_boq(
        "P", receipt["session_id"], [item.id],
        expected_session_revision=receipt["revision"],
    )


def unchanged(app):
    return app.store.current_digest("P"), deepcopy(app.open_project("P"))


def test_pdf_quantity_review_receipt_cannot_enter_finance(app, tmp_path):
    from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
    from core.drawings.takeoff_bridge import session_to_boq_rows
    from test_phase8_p2_a_pdf_combined_graph import registry
    from test_phase8_p2_a_pdf_occurrence_review import _explicit_set, _review_region

    paths = _explicit_set(tmp_path)
    plan = paths[0]
    revision_register = registry(*[(path, "SYNTHETIC", "R2", "CURRENT") for path in paths])
    review_region = _review_region(plan)
    before_intake = unchanged(app)
    report = inspect_pdf_sheet_set(paths, revision_registry=revision_register, quantity_review_regions=[review_region])
    assert unchanged(app) == before_intake
    receipt = report["quantity_evidence_review"]
    row, = receipt["rows"]
    candidate = row["quantity_candidate"]
    assert Decimal(str(candidate["value"])) == Decimal("0.56") and candidate["unit"] == "m3"
    assert row["engineering_approved"] is row["financially_payable"] is False
    assert receipt["quantity_approval_count"] == 0
    assert receipt["financially_payable"] is receipt["aggregate_permitted"] is False

    # Even an existing valid PDF session cannot accept a source-graph node as
    # one of its explicitly selected measurement item IDs.
    session = DrawingTakeoffSession(str(plan))
    line(session, (100, 75), (180, 75))
    stored = save(app, session)
    before = unchanged(app)
    review_id = candidate["node_id"]
    with pytest.raises(ValueError):
        session_to_boq_rows(receipt, session_id=stored["session_id"], selected_item_ids=[review_id])
    with pytest.raises(ValueError):
        save(app, receipt)
    with pytest.raises(ValueError):
        app.commit_drawing_takeoff_to_boq("P", None, [review_id], expected_session_revision=0,
                                          pdf_draft=receipt)
    partial_draft = {**receipt, "drawing_source": str(plan), "source_sha256": review_region["source_sha256"]}
    with pytest.raises(ValueError, match="شناسه متره در نشست وجود ندارد"):
        app.commit_drawing_takeoff_to_boq("P", None, [review_id], expected_session_revision=0,
                                          pdf_draft=partial_draft)
    with pytest.raises(ValueError, match="نشست نقشه معتبر نیست"):
        app.commit_drawing_takeoff_to_boq("P", None, [review_id], expected_session_revision=0,
                                          pdf_draft={**partial_draft, "items": [candidate]})
    with pytest.raises(ValueError, match="شناسه متره در نشست وجود ندارد"):
        app.commit_drawing_takeoff_to_boq("P", stored["session_id"], [review_id],
                                          expected_session_revision=stored["revision"])
    with pytest.raises(ValueError):
        app.commit_ai_takeoff_proposal("P", receipt, user_confirmed=True)
    with pytest.raises(ValueError, match="BOQ"):
        app.recalculate_estimate("P")
    assert unchanged(app) == before
    assert not before[1]["takeoffs"] and not before[1]["boq"] and not before[1].get("estimate")


@pytest.mark.parametrize("case", ["outside", "outside-hole", "hybrid", "scan"])
def test_pdf_commit_rejects_unproven_page_region(app, tmp_path, case):
    path = pdf(tmp_path / "plan.pdf", content=case if case in {"scan", "hybrid"} else "vector")
    session = DrawingTakeoffSession(str(path))
    if case == "outside":
        item = line(session, (500, 500), (600, 500))
    elif case == "outside-hole":
        item = area(session, 70, 170, holes=[[(190,80),(210,80),(210,100),(190,100)]])
    else:
        item = line(session, (80, 100), (180, 100))
    receipt = save(app, session)
    before = unchanged(app)
    with pytest.raises(ValueError):
        commit(app, receipt, item)
    assert unchanged(app) == before


def test_hybrid_rejects_raster_region_but_preserves_separate_vector_region(app, tmp_path):
    session = DrawingTakeoffSession(str(pdf(tmp_path / "plan.pdf", content="hybrid")))
    item = line(session, (21, 24), (42, 24))
    commit(app, save(app, session), item)
    assert Decimal(str(app.open_project("P")["boq"][0]["quantity"])) == Decimal("2.1")


@pytest.mark.parametrize("kind", ["length", "area"])
def test_geometrically_overlapping_pdf_rows_cannot_be_registered_twice(app, tmp_path, kind):
    path = str(pdf(tmp_path / "plan.pdf"))
    first, duplicate = DrawingTakeoffSession(path), DrawingTakeoffSession(path)
    if kind == "length":
        before_item = line(first, (100, 70), (200, 70))
        next_item = line(duplicate, (200, 70), (150, 70), (100, 70))
    else:
        before_item = area(first, 80, 180)
        next_item = area(duplicate, 130, 180)
    commit(app, save(app, first), before_item)
    receipt = save(app, duplicate)
    before = unchanged(app)
    with pytest.raises(ValueError):
        commit(app, receipt, next_item)
    assert unchanged(app) == before


@pytest.mark.parametrize("change", ["geometry", "omission", "source"])
def test_saved_pdf_revision_cannot_rewrite_committed_items(app, tmp_path, change):
    session = DrawingTakeoffSession(str(pdf(tmp_path / "plan.pdf")))
    item = line(session, (60, 60), (160, 60))
    result = commit(app, save(app, session), item)
    if change == "geometry":
        session.edit(item.id, geometry=((60, 60), (110, 60)), quantity=5)
    elif change == "omission":
        session.remove(item.id)
    else:
        session.drawing_source = str(pdf(tmp_path / "replacement.pdf"))
        session.source_sha256 = DrawingTakeoffSession(session.drawing_source).source_sha256
        session.edit(item.id, source_ref=session._source_ref(1, item.id))
    before = unchanged(app)
    with pytest.raises(ValueError, match="اصلاحیه"):
        app.save_drawing_takeoff_session(
            "P", session, session_id=result["session_id"], expected_revision=result["revision"])
    assert unchanged(app) == before


def test_replacing_pdf_while_opening_the_commit_snapshot_is_detected(app, tmp_path, monkeypatch):
    path = pdf(tmp_path / "plan.pdf")
    replacement = pdf(tmp_path / "replacement.pdf", offset=1)
    session = DrawingTakeoffSession(str(path))
    item = line(session, (60,60), (160,60))
    receipt = save(app, session)
    before = unchanged(app)
    real_open = pymupdf.open

    def replace_on_read(*args, **kwargs):
        if kwargs.get("stream") is not None and replacement.exists():
            replacement.replace(path)
        return real_open(*args, **kwargs)

    import fitz
    monkeypatch.setattr(pymupdf, "open", replace_on_read)
    monkeypatch.setattr(fitz, "open", replace_on_read)
    with pytest.raises(ValueError, match="تغییر"):
        commit(app, receipt, item)
    assert unchanged(app) == before


@pytest.mark.parametrize("loss", ["removed", "changed"])
def test_financial_boq_audit_requires_live_effective_pdf(app, tmp_path, loss):
    path = pdf(tmp_path / "plan.pdf")
    session = DrawingTakeoffSession(str(path))
    item = line(session, (60,60), (160,60))
    commit(app, save(app, session), item)
    assert audit_boq(app.open_project("P"))["reconciled"]
    path.unlink()
    if loss == "changed":
        pdf(path, offset=1)
    before = unchanged(app)
    with pytest.raises(ValueError, match="PDF"):
        audit_boq(app.open_project("P"))
    assert unchanged(app) == before


def test_reviewed_opening_amendment_remains_reportable_after_sqlite_reopen(tmp_path):
    from test_phase2_polygon_amendments import setup, propose
    from core.reports.custom_batch import _source_rows

    app, session, item, receipt, source_id = setup(tmp_path)
    original = deepcopy(app.open_project("P")["takeoffs"])
    amend = propose(app, session, item, receipt, source_id, tmp_path, "opening")
    app.review_beam_amendment("P", amend["id"], expected_revision=1,
                              reviewer="synthetic reviewer", note="100 minus 4")
    app.apply_beam_amendment("P", amend["id"], expected_revision=1)
    app.store.close()
    reopened = StructuralProApp(tmp_path / "db")
    try:
        snapshot = reopened.open_project("P")
        assert snapshot["takeoffs"] == original
        assert Decimal(str(amend["delta"][source_id])) == -4
        assert Decimal(str(_source_rows(snapshot, "takeoff")[0]["quantity"])) == 96
        assert reopened.store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        reopened.store.close()


def test_rotated_marks_have_no_effect_on_page_bound_semantics(app, tmp_path):
    path = tmp_path / "rotated.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=100, height=200)
        page.draw_line((10, 10), (80, 10))
        page.set_rotation(90)
        doc.save(path)
    session = DrawingTakeoffSession(str(path))
    item = line(session, (280, 75), (380, 75))
    commit(app, save(app, session), item)
    assert Decimal(str(app.open_project("P")["boq"][0]["quantity"])) == 10


def test_non_linear_pdf_primitives_are_retained_as_review_evidence(tmp_path):
    path = tmp_path / "operators.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=200)
        page.draw_quad(pymupdf.Quad((12, 10), (42, 14), (10, 31), (40, 35)))
        page.draw_bezier((60, 20), (80, 10), (95, 55), (120, 70))
        doc.save(path)
    with pymupdf.open(path) as doc:
        expected = [item[0] for drawing in doc[0].get_drawings() for item in drawing["items"]]
    assert {"qu", "c"} <= set(expected)
    result = GraphicalPDFAdapter().read(path)
    actual = [p for p in result.primitives if p.properties.get("pdf_operator")]
    assert [p.properties["pdf_operator"] for p in actual] == expected
    assert all(p.properties["needs_confirmation"] and len(p.properties["points"]) == 4 for p in actual)


def test_unusable_dimension_strings_do_not_yield_positive_suffixes():
    page = PDFPageInfo(1, 200, 200, "L= ۰ متر\n−12.70 m\n− 10.70 m\n۱٬۲۳۴٫۵۶ متر\n۱٫۲۵ متر\n14.00 mm")
    assert [r.value for r in PDFTakeoffAdapter().measurements([page])] == [1.25, 0.014]


def test_pdf_two_views_use_separate_documented_scales(app, tmp_path):
    path = str(pdf(tmp_path / "two-views.pdf"))
    left = DrawingTakeoffSession(path)
    right = DrawingTakeoffSession(path)
    left.calibrate(1, 100, 5, pdf_view={"bounds": [10, 10, 160, 150],
                                       "reference_points": [[20, 20], [120, 20]]})
    right.calibrate(1, 100, 2, pdf_view={"bounds": [190, 190, 350, 350],
                                        "reference_points": [[210, 200], [310, 200]]})
    left_item = left.add_length([Point(20, 50), Point(120, 50)], takeoff_code="LEFT-VIEW")
    right_item = right.add_length([Point(210, 230), Point(310, 230)], takeoff_code="RIGHT-VIEW")
    for session, item in ((left, left_item), (right, right_item)):
        commit(app, save(app, session), item)
    proof = app.open_project("P")
    actual = {row["item_code"]: Decimal(str(row["quantity"])) for row in proof["boq"]}
    assert actual == {"LEFT-VIEW": Decimal("5"), "RIGHT-VIEW": Decimal("2")}
    bad_session = DrawingTakeoffSession.from_dict(left.to_dict())
    bad_session.add_length([Point(140, 60), Point(200, 60)], takeoff_code="CROSSES-VIEWS")
    before = unchanged(app)
    with pytest.raises(ValueError, match="محدوده"):
        save(app, bad_session)
    assert unchanged(app) == before


@pytest.fixture
def dialog(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from app.graphical_takeoff import GraphicalTakeoffDialog

    qt = QApplication.instance() or QApplication([])
    path = pdf(tmp_path / "plan.pdf")
    monkeypatch.setattr(GraphicalTakeoffDialog, "_queue_workflow_intake", lambda self: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    ui = GraphicalTakeoffDialog(pdf_path=str(path), project_id="P", app_service=app)
    ui.test_errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: ui.test_errors.append(args[-1]))
    try:
        yield ui, path
    finally:
        ui.engine.close()
        ui.close()
        qt.processEvents()


@pytest.mark.parametrize("action", ["cancel", "bad_source", "commit"])
def test_native_pdf_boq_action_is_one_atomic_write(dialog, app, action, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox

    ui, path = dialog
    item = line(ui.session, (60,60), (160,60))
    ui.refresh()
    ui.resize(1100, 850)
    ui.show()
    QApplication.processEvents()
    cell = ui.table.item(0, 1)
    QTest.mouseClick(ui.table.viewport(), Qt.MouseButton.LeftButton,
                     pos=ui.table.visualItemRect(cell).center())
    assert ui.table.selectionModel().selectedRows()
    confirmations = []

    def confirm(*args):
        confirmations.append(args[1])
        return QMessageBox.StandardButton.No if action == "cancel" else QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm)
    if action == "bad_source":
        path.unlink()
    before = unchanged(app)
    ui.commit_selected_to_boq()
    assert confirmations == ["تأیید انتقال به BOQ"]
    if action == "commit":
        assert not ui.test_errors, ui.test_errors
        result = app.open_project("P")
        assert result["_meta"]["version"] == before[1]["_meta"]["version"] + 1
        assert result["drawing_sessions"][ui.persisted_session_id]["committed_item_ids"] == [item.id]
        assert Decimal(str(result["boq"][0]["quantity"])) == 10
    else:
        assert unchanged(app) == before


def test_qt_does_not_reattach_measurements_to_replaced_pdf(dialog, app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    ui, path = dialog
    saved_session = DrawingTakeoffSession(str(path))
    line(saved_session, (60,60), (160,60))
    receipt = save(app, saved_session)
    ui.engine.close()
    pdf(tmp_path / "next.pdf", offset=1).replace(path)
    errors = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: (receipt["session_id"], True))
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    before = unchanged(app)
    ui.load_session_from_project()
    assert errors and "تغییر" in errors[0]
    assert ui.table.rowCount() == 0
    assert unchanged(app) == before


def test_csv_preserves_the_explicit_decimal_quantity_summary(tmp_path):
    import csv
    from core.reports.exporters import export_csv

    label = "جمع مقدار ـ m2"
    path = export_csv(
        [{"description": "مصنوعی A", "quantity": Decimal("0.1")},
         {"description": "مصنوعی B", "quantity": Decimal("0.2")}],
        tmp_path / "readback.csv",
        summary={"report_totals": {label: Decimal("0.3")}},
    )
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream, strict=True))
    assert [label, "0.3"] in rows
    assert ["مصنوعی A", "0.1"] in rows and ["مصنوعی B", "0.2"] in rows
