"""Real Qt interaction with reviewed member-tree and BOQ selection view."""
import pytest

from test_phase6_p3_verified_selection import SHA, record, make_index


def test_qt_member_tree_boq_and_geometry_navigate_only_approved_identity():
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.verified_selection_panel import VerifiedSelectionPanel

    app = QApplication.instance() or QApplication([])
    panel = VerifiedSelectionPanel(make_index())
    panel.resize(820, 440)
    panel.show()
    app.processEvents()
    ids, warnings = [], []
    panel.oneGlobalIdSelected.connect(ids.append)
    panel.selectionUnresolved.connect(warnings.append)
    try:
        approved_member = panel.members.topLevelItem(0)
        assert approved_member.text(0) == 'M-1'
        rect = panel.members.visualItemRect(approved_member)
        QTest.mouseClick(panel.members.viewport(), Qt.MouseButton.LeftButton,
                         pos=rect.center())
        assert ids == ['G-1']
        assert 'G-1' in panel.detail.text()
        # Actual BOQ grid selection emits the same approved identity.
        panel.boq.clearSelection()
        panel.boq.setCurrentCell(0, 0)
        app.processEvents()
        assert ids[-1] == 'G-1'
        # Selecting from the 2D view updates tree/BOQ, without a feedback loop.
        count = len(ids)
        result = panel.select_from_geometry('G-1', origin='2d')
        assert result.status == 'linked' and len(ids) == count
        assert panel.members.selectedItems()
        assert panel.boq.selectionModel().selectedRows()
        unlinked = panel.select_from_geometry('G-2', origin='3d')
        assert unlinked.status == 'unlinked'
        assert not panel.members.selectedItems()
        assert not panel.boq.selectionModel().selectedRows()
        # An unlinked BOQ row does not cause a fake model selection.
        old_count = len(ids)
        panel.boq.setCurrentCell(1, 0)
        app.processEvents()
        assert len(ids) == old_count
        assert warnings
    finally:
        panel.close()


def test_qt_multi_member_boq_row_is_not_silently_reduced_to_first_member():
    from PySide6.QtWidgets import QApplication
    from app.verified_selection_panel import VerifiedSelectionPanel
    app = QApplication.instance() or QApplication([])
    index = make_index([record(), record(member='M-2', global_id='G-2', shape='S-2')])
    panel = VerifiedSelectionPanel(index)
    panel.show()
    app.processEvents()
    chosen, warnings = [], []
    panel.oneGlobalIdSelected.connect(chosen.append)
    panel.selectionUnresolved.connect(warnings.append)
    try:
        panel.boq.setCurrentCell(0, 0)
        app.processEvents()
        assert not chosen
        assert warnings and '۲' in warnings[-1]
        result = panel.select_from_geometry('G-2', origin='3d')
        assert result.global_ids == ('G-2',)
        assert result.boq_row_ids == ('B-01',)
    finally:
        panel.close()
