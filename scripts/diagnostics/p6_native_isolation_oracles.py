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
