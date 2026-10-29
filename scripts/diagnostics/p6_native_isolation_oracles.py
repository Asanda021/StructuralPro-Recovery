"""P6-P5 crash isolation: original 14 formulas, real SQLite, versus native Qt-only table.

Diagnostic-only test module, outside regular tests discovery. Original code,
report exporter and existing fivefloor acceptance test remain unmodified.
"""
import ast
from decimal import Decimal
from pathlib import Path


def _original_cases():
    path = Path(__file__).resolve().parents[2] / "tests" / "test_manual_formula_fivefloor_closure.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CASES" for target in node.targets)
    )
    cases = ast.literal_eval(assignment.value)
    assert len(cases) == 14
    return cases


def test_core_sqlite_full_fivefloor_without_qapplication(tmp_path):
    """The full 70-row service path, with original data, no Qt event loop/widgets."""
    from PySide6.QtCore import QCoreApplication
    assert QCoreApplication.instance() is None, "Core-only arm accidentally has Qt event loop"
    from core.platform.application import StructuralProApp
    from core.takeoff.manual_form_fields import canonical, expression
    from core.takeoff.manual_formula_register import catalog

    cases = _original_cases()
    assert len(catalog()) == 85
    s = StructuralProApp(tmp_path / "db")
    try:
        s.create_project("ساختمان پنج‌طبقه کاملاً مصنوعی", "P")
        explicit_units = {"طول": "m", "عرض": "m", "ارتفاع": "m",
                          "ضخامت": "m", "تعداد": "عدد", "وزن": "kg/m",
                          "بازشو": "m2"}
        for i, (label, family, unit, formula, vars_, expected) in enumerate(cases):
            variables = {canonical(k): v for k, v in vars_.items()}
            data = {
                "family": family, "title": label, "floor": "طبقه۱",
                "member": "عضو-" + label, "unit": unit,
                "expression": expression(formula),
                "variables": variables,
                "variable_units": {canonical(k): explicit_units[k] for k in vars_},
                "unit_policy": "dimensional_decimal_v1",
                "references": {}, "source_id": "synthetic:fivefloor:A" + str(i),
                "basis": "مصنوعی؛ ابعاد متر، تعداد عدد، وزن واحد کیلوگرم بر متر؛ بدون پرت یا دیتایل حدسی",
                "deductions": [],
            }
            row = s.save_manual_formula("P", "A" + str(i), data, expected_revision=0,
                                         reason="ورود صریح مصنوعی")
            assert Decimal(str(row["quantity"])) == Decimal(expected)
        original_keys = ["A" + str(i) for i in range(14)]
        for floor in ("طبقه۲", "طبقه۳", "طبقه۴", "طبقه۵"):
            before = s.load_manual_formulas("P")
            assert len([k for k in original_keys if k in before]) == 14
            mapping = s.copy_manual_formulas(
                "P", original_keys, floor=floor,
                expected_revisions={key: before[key]["revision"] for key in original_keys},
                reason="تکرار صریح اعضای مستقل در طبقه جدید",
            )
            assert len(mapping) == 14 and len(set(mapping.values())) == 14
        register = s.load_manual_formulas("P")
        assert len(register) == 70 and not s.open_project("P")["boq"]
        original = s.load_manual_formulas("P")
        from copy import deepcopy
        bad = deepcopy(original["A0"]["data"])
        bad["variables"] = {"length": "4"}
        try:
            s.save_manual_formula("P", "A0", bad, expected_revision=original["A0"]["revision"],
                                  reason="ورودی ناقص")
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError("Invalid formula was accepted")
        assert s.load_manual_formulas("P") == original
        for key in list(register):
            row = s.load_manual_formulas("P")[key]
            s.review_manual_formula(
                "P", key, expected_revision=row["revision"],
                reviewer="مهندس مصنوعی", note="مرجع مستقل هر فرمول و واحد کنترل شد",
            )
            assert s.load_manual_formulas("P")[key]["status"] == "reviewed"
            s.commit_manual_formula("P", key, expected_revision=row["revision"])
            assert s.load_manual_formulas("P")[key]["status"] == "committed"
        project = s.open_project("P")
        assert len(project["takeoffs"]) == len(project["boq"]) == 70
        assert len({r["source_id"] for r in project["boq"]}) == 70
        for label, family, unit, formula, vars_, expected in cases:
            matching = [r for r in project["boq"] if r["description"] == label]
            assert len(matching) == 5
            assert sum(Decimal(str(r["quantity"])) for r in matching) == Decimal(expected) * 5
        for fmt in ("xlsx", "pdf"):
            out = tmp_path / ("fivefloor-core." + fmt)
            s.export_manual_formula_report("P", out, format=fmt)
            assert out.is_file() and out.stat().st_size > 0
        assert QCoreApplication.instance() is None, "Qt event loop leaked into pure-core arm"
    finally:
        s.store.close()
    s = StructuralProApp(tmp_path / "db")
    try:
        reg = s.load_manual_formulas("P")
        assert len(reg) == 70
        assert all(row["status"] == "committed" for row in reg.values())
        assert all(row["data"]["unit_policy"] == "dimensional_decimal_v1" for row in reg.values())
        assert len(s.open_project("P")["boq"]) == 70
    finally:
        s.store.close()


def test_native_qt_table_events_without_service_or_sqlite():
    """Native QApplication/QTableWidget clicks, sorting, selection, no project open."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

    # No StructuralProApp or repository storage is instantiated in this arm.
    app = QApplication.instance() or QApplication([])
    table = QTableWidget()
    table.setColumnCount(3)
    table.setRowCount(70)
    for n in range(70):
        table.setItem(n, 0, QTableWidgetItem("A" + str(n)))
        table.setItem(n, 1, QTableWidgetItem("طبقه" + str(n // 14 + 1)))
        table.setItem(n, 2, QTableWidgetItem("عضو مصنوعی " + str(n)))
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.resize(900, 500)
    table.show()
    app.processEvents()
    try:
        for pass_no in range(4):
            table.sortItems(0, Qt.SortOrder.AscendingOrder if pass_no % 2 == 0
                            else Qt.SortOrder.DescendingOrder)
            app.processEvents()
            for row in range(70):
                cell = table.item(row, 0)
                table.scrollToItem(cell)
                app.processEvents()
                rect = table.visualItemRect(cell)
                assert rect.isValid()
                QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
                app.processEvents()
                assert table.selectionModel().selectedRows()
                assert table.item(table.selectionModel().selectedRows()[0].row(), 0).text() == cell.text()
        assert table.rowCount() == 70
    finally:
        table.close()
        table.deleteLater()
        app.processEvents()



def _seed_draft_fivefloor(directory):
    """Same 14 original synthetic cases and 70 revisioned rows, without a Qt event loop."""
    from PySide6.QtCore import QCoreApplication
    from core.platform.application import StructuralProApp
    from core.takeoff.manual_form_fields import canonical, expression
    from core.takeoff.manual_formula_register import catalog
    assert QCoreApplication.instance() is None
    assert len(catalog()) == 85
    s = StructuralProApp(directory)
    try:
        s.create_project("ساختمان پنج‌طبقه کاملاً مصنوعی", "P")
        units = {"طول": "m", "عرض": "m", "ارتفاع": "m", "ضخامت": "m",
                 "تعداد": "عدد", "وزن": "kg/m", "بازشو": "m2"}
        for i, (label, family, unit, formula, variables, expected) in enumerate(_original_cases()):
            data = {
                "family": family, "title": label, "floor": "طبقه۱",
                "member": "عضو-" + label, "unit": unit,
                "expression": expression(formula),
                "variables": {canonical(k): v for k, v in variables.items()},
                "variable_units": {canonical(k): units[k] for k in variables},
                "unit_policy": "dimensional_decimal_v1",
                "references": {}, "source_id": "synthetic:fivefloor:A" + str(i),
                "basis": "مصنوعی؛ ابعاد متر، تعداد عدد، وزن واحد کیلوگرم بر متر؛ بدون پرت یا دیتایل حدسی",
                "deductions": [],
            }
            actual = s.save_manual_formula("P", "A" + str(i), data,
                                           expected_revision=0, reason="ورود صریح مصنوعی")
            assert Decimal(str(actual["quantity"])) == Decimal(expected)
        keys = ["A" + str(i) for i in range(14)]
        for floor in ("طبقه۲", "طبقه۳", "طبقه۴", "طبقه۵"):
            versions = s.load_manual_formulas("P")
            s.copy_manual_formulas(
                "P", keys, floor=floor,
                expected_revisions={key: versions[key]["revision"] for key in keys},
                reason="تکرار صریح اعضای مستقل در طبقه جدید",
            )
        reg = s.load_manual_formulas("P")
        assert len(reg) == 70
        assert all(r["status"] == "draft" for r in reg.values())
        assert not s.open_project("P")["boq"]
        return sorted(reg)
    finally:
        s.store.close()


def _select_real_formula_row(dialog, key, app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    table = dialog.formula_table
    positions = [
        n for n in range(table.rowCount())
        if table.item(n, 0) is not None and table.item(n, 0).text() == key
    ]
    assert len(positions) == 1, f"Expected exactly one visible real formula row: {key}"
    row = positions[0]
    assert not table.isRowHidden(row)
    item = table.item(row, 0)
    assert item.data(Qt.ItemDataRole.UserRole) == "formula"
    table.scrollToItem(item)
    app.processEvents()
    rect = table.visualItemRect(item)
    assert rect.isValid(), key
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    app.processEvents()
    selected = table.selectionModel().selectedRows()
    assert selected and table.item(selected[0].row(), 0).text() == key


def test_native_real_manual_dialog_readonly_70_rows(tmp_path):
    """Native production dialog, real SQLite and 70 draft rows, no review/commit mutations."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from app.manual_takeoff import ManualTakeoffDialog
    from core.platform.application import StructuralProApp

    db = tmp_path / "db"
    keys = _seed_draft_fivefloor(db)
    app = QApplication.instance() or QApplication([])
    service = StructuralProApp(db)
    dialog = None
    try:
        before = service.store.current_digest("P")
        dialog = ManualTakeoffDialog(service, "P")
        dialog.show()
        dialog.manual_tabs.setCurrentIndex(1)
        app.processEvents()
        assert dialog.formula_table.rowCount() == 70
        for iteration in range(2):
            dialog.formula_table.sortItems(
                0, Qt.SortOrder.AscendingOrder if iteration == 0
                else Qt.SortOrder.DescendingOrder
            )
            app.processEvents()
            for key in keys:
                _select_real_formula_row(dialog, key, app)
            dialog.refresh_formula_rows()
            app.processEvents()
            assert dialog.formula_table.rowCount() == 70
        assert service.store.current_digest("P") == before, "View-only test changed persisted data"
        assert len(service.load_manual_formulas("P")) == 70
        assert not service.open_project("P")["boq"]
    finally:
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
            app.processEvents()
        service.store.close()


def test_native_real_manual_dialog_review_commit_70_rows(tmp_path):
    """Native review and commit buttons, preseeded 70 rows, no Qt edit/copy during setup."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.manual_takeoff import ManualTakeoffDialog
    from core.platform.application import StructuralProApp

    db = tmp_path / "db"
    keys = _seed_draft_fivefloor(db)
    app = QApplication.instance() or QApplication([])
    service = StructuralProApp(db)
    dialog = None
    try:
        dialog = ManualTakeoffDialog(service, "P")
        dialog.show()
        dialog.manual_tabs.setCurrentIndex(1)
        app.processEvents()
        assert dialog.formula_table.rowCount() == 70
        dialog.formula_reviewer.setText("مهندس مصنوعی")
        dialog.formula_review_note.setText("مرجع مستقل هر فرمول و واحد کنترل شد")
        for number, key in enumerate(keys, start=1):
            _select_real_formula_row(dialog, key, app)
            QTest.mouseClick(dialog.formula_review_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert service.load_manual_formulas("P")[key]["status"] == "reviewed", key
            _select_real_formula_row(dialog, key, app)
            QTest.mouseClick(dialog.formula_commit_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert service.load_manual_formulas("P")[key]["status"] == "committed", key
            assert len(service.open_project("P")["boq"]) == number
        project = service.open_project("P")
        assert len(project["takeoffs"]) == len(project["boq"]) == 70
        assert len({r["source_id"] for r in project["boq"]}) == 70
        for label, family, unit, formula, variables, expected in _original_cases():
            matching = [r for r in project["boq"] if r["description"] == label]
            assert len(matching) == 5
            assert sum(Decimal(str(row["quantity"])) for row in matching) == Decimal(expected) * 5
    finally:
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
            app.processEvents()
        service.store.close()
    reopened = StructuralProApp(db)
    try:
        assert len(reopened.load_manual_formulas("P")) == 70
        assert all(row["status"] == "committed" for row in reopened.load_manual_formulas("P").values())
        assert len(reopened.open_project("P")["boq"]) == 70
    finally:
        reopened.store.close()


def test_native_real_dialog_destroy_reopen_every_fourteen_commits(tmp_path):
    """Lifecycle diagnostic: real Qt dialogs and SQLite reopened between five 14-row batches.

    All engineering values are from the unchanged synthetic fivefloor oracle.
    This is diagnostic coverage, not proof that the intermittent AV is repaired.
    """
    from PySide6.QtCore import Qt, QCoreApplication, QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid
    from app.manual_takeoff import ManualTakeoffDialog
    from core.platform.application import StructuralProApp
    from scripts.diagnostics.p6_lifecycle_checkpoint import mark as checkpoint

    db = tmp_path / "db"
    keys = _seed_draft_fivefloor(db)
    assert len(keys) == 70
    checkpoint("CASE_READY")
    app = QApplication.instance() or QApplication([])
    destroyed_notifications = []
    for cycle in range(5):
        checkpoint("DIALOG_ENTER", cycle=cycle, committed=14 * cycle)
        service = StructuralProApp(db)
        dialog = None
        try:
            assert len(service.load_manual_formulas("P")) == 70
            assert len(service.open_project("P")["boq"]) == 14 * cycle
            dialog = ManualTakeoffDialog(service, "P")
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            # Keep observer callback independent of the dialog object.
            dialog.destroyed.connect(
                lambda *_args, i=cycle: destroyed_notifications.append(i)
            )
            dialog.show()
            dialog.manual_tabs.setCurrentIndex(1)
            app.processEvents()
            assert dialog.formula_table.rowCount() == 70
            assert isValid(dialog)
            checkpoint("DIALOG_READY", cycle=cycle, committed=14 * cycle)
            dialog.formula_reviewer.setText("مهندس مصنوعی")
            dialog.formula_review_note.setText("مرجع مستقل هر فرمول و واحد کنترل شد")
            chunk = keys[14 * cycle:14 * (cycle + 1)]
            assert len(chunk) == 14
            for offset, key in enumerate(chunk, start=1):
                _select_real_formula_row(dialog, key, app)
                QTest.mouseClick(dialog.formula_review_button, Qt.MouseButton.LeftButton)
                app.processEvents()
                assert service.load_manual_formulas("P")[key]["status"] == "reviewed"
                _select_real_formula_row(dialog, key, app)
                QTest.mouseClick(dialog.formula_commit_button, Qt.MouseButton.LeftButton)
                app.processEvents()
                assert service.load_manual_formulas("P")[key]["status"] == "committed"
                assert len(service.open_project("P")["boq"]) == 14 * cycle + offset
            checkpoint("BATCH_COMMITTED", cycle=cycle, committed=14 * (cycle + 1))
            checkpoint("SORT_FILTER_ENTER", cycle=cycle, committed=14 * (cycle + 1))
            # Exercise real refresh/sort/search after the last UI write.
            dialog.formula_table.sortItems(0, Qt.SortOrder.DescendingOrder)
            dialog.formula_search.setText("طبقه" + str(cycle + 1))
            app.processEvents()
            dialog.formula_search.clear()
            checkpoint("SORT_FILTER_EXIT", cycle=cycle, committed=14 * (cycle + 1))
            checkpoint("REFRESH_ENTER", cycle=cycle, committed=14 * (cycle + 1))
            dialog.refresh_formula_rows()
            app.processEvents()
            assert dialog.formula_table.rowCount() == 70
            checkpoint("REFRESH_EXIT", cycle=cycle, committed=14 * (cycle + 1))
        finally:
            if dialog is not None:
                checkpoint("DIALOG_DELETE_ENTER", cycle=cycle, committed=14 * (cycle + 1))
                dialog.close()
                dialog.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()
                assert not isValid(dialog), "Native dialog wrapper survived DeferredDelete"
                assert destroyed_notifications.count(cycle) == 1, "Dialog destroyed != exactly once"
                checkpoint("DIALOG_DELETE_EXIT", cycle=cycle, committed=14 * (cycle + 1))
            checkpoint("STORE_CLOSE_ENTER", cycle=cycle, committed=14 * (cycle + 1))
            service.store.close()
            checkpoint("STORE_CLOSE_EXIT", cycle=cycle, committed=14 * (cycle + 1))
        # Reopen SQLite after widget and store teardown, before next UI construction.
        checkpoint("REOPEN_ENTER", cycle=cycle, committed=14 * (cycle + 1))
        reopened = StructuralProApp(db)
        try:
            project = reopened.open_project("P")
            assert len(project["takeoffs"]) == len(project["boq"]) == 14 * (cycle + 1)
            reg = reopened.load_manual_formulas("P")
            assert sum(row["status"] == "committed" for row in reg.values()) == 14 * (cycle + 1)
        finally:
            reopened.store.close()
        checkpoint("REOPEN_EXIT", cycle=cycle, committed=14 * (cycle + 1))
    assert destroyed_notifications == [0, 1, 2, 3, 4]
    final = StructuralProApp(db)
    try:
        project = final.open_project("P")
        assert len(project["boq"]) == len(project["takeoffs"]) == 70
        assert len({r["source_id"] for r in project["boq"]}) == 70
        for label, family, unit, formula, variables, expected in _original_cases():
            matching = [row for row in project["boq"] if row["description"] == label]
            assert len(matching) == 5
            assert sum(Decimal(str(row["quantity"])) for row in matching) == Decimal(expected) * 5
        assert all(row["status"] == "committed" for row in final.load_manual_formulas("P").values())
    finally:
        final.store.close()
    checkpoint("ALL_DONE", cycle=4, committed=70)
