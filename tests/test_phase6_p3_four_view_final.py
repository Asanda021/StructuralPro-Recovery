"""P6-3 four-view acceptance against a real reviewed IFC/SQLite/BOQ project.

No fabricated quantity, synthetic approval, or database writes by navigation.
The committed fixture is the existing independently reviewed IFC specialist case.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from test_phase6_p3_full_verified_boq import committed_column_case


def _all_selected(window, model, panel, gid, member, linked_boq):
    assert window._ifc_selected_global_id == gid
    assert all(item.isSelected() for item in window._ifc_handle_items[gid])
    assert model.canvas.selected_id == gid
    assert [x.text(0) for x in panel.members.selectedItems()] == [member]
    assert len(panel.boq.selectionModel().selectedRows()) == linked_boq


def _all_cleared(window, model, panel):
    assert not window._ifc_selected_global_id
    assert not any(x.isSelected() for group in window._ifc_handle_items.values() for x in group)
    assert model.canvas.selected_id is None
    assert not panel.members.selectedItems()
    assert not panel.boq.selectionModel().selectedRows()


def test_real_native_qt_2d_3d_tree_boq_clicks_clear_and_revision(tmp_path):
    """One original persisted reviewed column, three real BOQ rows and 3D mesh."""
    from app.graphical_takeoff import GraphicalTakeoffDialog

    service, source, obj = committed_column_case(tmp_path)
    app = QApplication.instance() or QApplication([])
    window = GraphicalTakeoffDialog(app_service=service, project_id="P")
    panel_holder = None
    model = None
    try:
        window.show()
        window.open_drawing(str(source))
        window.ifc_revision.setText("R1")
        panel_holder = window.open_verified_crossview()
        assert panel_holder is not None, window.status.text()
        panel = window._verified_selection_panel
        assert panel.boq.rowCount() == 3
        original_digest = service.store.current_digest("P")
        original_boq = service.open_project("P")["boq"]
        gid = obj.GlobalId

        window.open_ifc_3d()
        for _ in range(2500):
            app.processEvents()
            if window._ifc_3d_dialog is not None:
                break
            if window._ifc_3d_loader is None:
                break
            QTest.qWait(10)
        model = window._ifc_3d_dialog
        assert model is not None, window.status.text()
        model.show()
        app.processEvents()

        # An actual mouse event on a projected verified IFC face.
        faces = [face for face in model.canvas._faces() if face.global_id == gid]
        assert faces, "The reviewed IFC column must have renderable geometry"
        picked = False
        for face in faces:
            px = sum(p[0] for p in face.points) / 3
            py = sum(p[1] for p in face.points) / 3
            if model.scene.pick(px, py, model.canvas.width(), model.canvas.height()) == gid:
                from PySide6.QtCore import QPoint
                QTest.mouseClick(model.canvas, Qt.MouseButton.LeftButton,
                                 pos=QPoint(round(px), round(py)))
                picked = True
                break
        assert picked, "No verifiable 3D pick position found"
        _all_selected(window, model, panel, gid, "C1", 3)

        # The 2D scene selection must activate the same three other views.
        panel.clear_selection()
        _all_cleared(window, model, panel)
        for item in window._ifc_handle_items[gid]:
            item.setSelected(True)
        app.processEvents()
        _all_selected(window, model, panel, gid, "C1", 3)

        # A real Qt click on the actual project member tree.
        panel.clear_selection()
        node = panel.members.topLevelItem(0)
        panel.members.scrollToItem(node)
        app.processEvents()
        QTest.mouseClick(panel.members.viewport(), Qt.MouseButton.LeftButton,
                         pos=panel.members.visualItemRect(node).center())
        _all_selected(window, model, panel, gid, "C1", 3)

        # A real Qt click on an independently committed, persisted BOQ row.
        panel.clear_selection()
        panel.boq.scrollToItem(panel.boq.item(0, 0))
        app.processEvents()
        QTest.mouseClick(panel.boq.viewport(), Qt.MouseButton.LeftButton,
                         pos=panel.boq.visualRect(panel.boq.model().index(0, 0)).center())
        _all_selected(window, model, panel, gid, "C1", 3)
        assert "مقدار ثبت‌شده" in panel.detail.text()
        assert "SHA-256:" in panel.detail.text()
        assert service.store.current_digest("P") == original_digest
        assert service.open_project("P")["boq"] == original_boq

        # Changing the visible revision revokes the existing four-way pick.
        window.ifc_revision.setText("R2")
        model.memberSelected.emit(gid)
        _all_cleared(window, model, panel)
        assert "Revision" in window.status.text() or "نسخه" in window.status.text()
        assert service.store.current_digest("P") == original_digest
    finally:
        if model is not None:
            model.close()
        if panel_holder is not None:
            panel_holder.close()
        window.close()
        app.processEvents()
        service.store.close()


def test_unlinked_boq_click_rejects_old_highlight_and_never_invents_ifc(tmp_path):
    """An unrelated manual takeoff must not inherit the reviewed column identity."""
    from app.graphical_takeoff import GraphicalTakeoffDialog

    service, source, obj = committed_column_case(tmp_path)
    service.add_takeoff(
        "P", "building", "slab", length=2, width=3,
        member_code="C1", source_id="manual:unlinked-boq",
        price_code="C1", unit_price=100,
    )
    app = QApplication.instance() or QApplication([])
    window = GraphicalTakeoffDialog(app_service=service, project_id="P")
    holder = None
    try:
        window.show()
        window.open_drawing(str(source))
        window.ifc_revision.setText("R1")
        holder = window.open_verified_crossview()
        assert holder is not None, window.status.text()
        panel = window._verified_selection_panel
        assert panel.boq.rowCount() == 4
        before = service.store.current_digest("P")
        boq_before = service.open_project("P")["boq"]
        gid = obj.GlobalId
        window.highlight_ifc_member(gid)
        assert len(panel.boq.selectionModel().selectedRows()) == 3

        # User chooses a real BOQ row whose source receipt has no IFC review.
        unlinked = [i for i in range(panel.boq.rowCount())
                    if panel.boq.item(i, 1).text() == "فاقد ارتباط"]
        assert len(unlinked) == 1
        panel.boq.clearSelection()
        panel.boq.scrollToItem(panel.boq.item(unlinked[0], 0))
        app.processEvents()
        QTest.mouseClick(
            panel.boq.viewport(), Qt.MouseButton.LeftButton,
            pos=panel.boq.visualRect(panel.boq.model().index(unlinked[0], 0)).center(),
        )
        assert not window._ifc_selected_global_id
        assert not panel.members.selectedItems()
        assert not panel.boq.selectionModel().selectedRows()
        assert all(not x.isSelected() for group in window._ifc_handle_items.values() for x in group)
        assert "حدسی" in panel.detail.text()
        assert service.store.current_digest("P") == before
        assert service.open_project("P")["boq"] == boq_before
    finally:
        if holder is not None:
            holder.close()
        window.close()
        app.processEvents()
        service.store.close()
