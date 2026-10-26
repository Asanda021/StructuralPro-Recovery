"""Verified, read-only member/BOQ selection panel.

The project must supply a reviewed crosswalk and real project identity sets.
No BOQ line, member or quantity is created by this widget.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSignalBlocker, QItemSelectionModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QAbstractItemView,
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView,
)

from core.drawings.verified_selection import VerifiedSelectionCrosswalk


class VerifiedSelectionPanel(QWidget):
    oneGlobalIdSelected = Signal(str)
    selectionUnresolved = Signal(str)

    def __init__(self, index: VerifiedSelectionCrosswalk, parent=None, *, verified_project=None):
        super().__init__(parent)
        self.index = index
        self.verified_project = verified_project
        self.setObjectName('VerifiedCrossViewSelection')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        main = QVBoxLayout(self)
        main.addWidget(QLabel('انتخاب مبتنی بر شناسه و مدرک تأییدشده؛ بدون تغییر متره یا BOQ'))
        views = QHBoxLayout()
        self.members = QTreeWidget()
        self.members.setObjectName('VerifiedMemberTree')
        self.members.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.members.setHeaderLabels(['عضو موجود در پروژه', 'وضعیت ارتباط'])
        for member in sorted(index.allowed['member_id']):
            linked = any(item.member_id == member for item in index.links)
            row = QTreeWidgetItem([member, 'مستند' if linked else 'فاقد ارتباط'])
            row.setData(0, Qt.ItemDataRole.UserRole, member)
            self.members.addTopLevelItem(row)
        views.addWidget(self.members)
        self.boq = QTableWidget()
        self.boq.setObjectName('VerifiedBOQSelection')
        self.boq.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.boq.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.boq.setColumnCount(2)
        self.boq.setHorizontalHeaderLabels(['ردیف واقعی BOQ', 'وضعیت ارتباط'])
        all_boq = sorted(index.allowed['boq_row_id'])
        self.boq.setRowCount(len(all_boq))
        for row, identifier in enumerate(all_boq):
            cell = QTableWidgetItem(
                verified_project.boq_labels.get(identifier,identifier)
                if verified_project is not None else identifier)
            cell.setData(0x0100,identifier)  # Qt.UserRole: immutable snapshot row key
            self.boq.setItem(row, 0, cell)
            if verified_project is not None:
                cell.setToolTip('نمای نسخه‌ای BOQ؛ شناسه پایدار مالی نیست.')
            linked = any(item.boq_row_id == identifier for item in index.links)
            self.boq.setItem(row, 1, QTableWidgetItem('مستند' if linked else 'فاقد ارتباط'))
        self.boq.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        views.addWidget(self.boq)
        main.addLayout(views)
        self.detail = QLabel('یک عضو یا ردیف BOQ واقعی را انتخاب کنید.')
        self.detail.setObjectName('VerifiedSelectionStatus')
        self.detail.setWordWrap(True)
        main.addWidget(self.detail)
        self.members.itemClicked.connect(self._clicked_member)
        self.boq.itemSelectionChanged.connect(self._clicked_boq)

    def _resolve(self, origin, identifier):
        if self.verified_project is not None:
            return self.verified_project.resolve(
                origin=origin,identifier=identifier,
                source_sha256=self.index.source_sha256,revision=self.index.revision)
        return self.index.resolve(origin=origin,identifier=identifier,
            project_id=self.index.project_id,source_sha256=self.index.source_sha256,
            revision=self.index.revision)

    def _fail_stale(self, error):
        with QSignalBlocker(self.members), QSignalBlocker(self.boq):
            self.members.clearSelection()
            self.boq.clearSelection()
        message='پیوند نسخه‌ای نامعتبر شد؛ پروژه/IFC را مجدداً باز کنید: '+str(error)
        self.detail.setText(message)
        self.selectionUnresolved.emit(message)

    def _lookup(self, origin, identifier):
        try:
            result=self._resolve(origin,identifier)
        except (ValueError, RuntimeError, PermissionError) as exc:
            self._fail_stale(exc)
            return None
        if result.status != 'linked':
            message = 'ارتباط تأییدشده با نقشه/BOQ وجود ندارد؛ انتخاب حدسی ممنوع است.'
            self.detail.setText(message)
            self.selectionUnresolved.emit(message)
            return result
        if len(result.global_ids) != 1:
            persian_count = str(len(result.global_ids)).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
            message = f'این ردیف به {persian_count} عضو معتبر مرتبط است؛ عضو مشخص را انتخاب کنید.'
            self.detail.setText(message)
            self.selectionUnresolved.emit(message)
            return result
        self.detail.setText(
            'شناسه IFC: ' + result.global_ids[0] +
            ' | عضو: ' + '، '.join(result.member_ids or ('فاقد پیوند',)) +
            ' | ردیف BOQ: ' + '، '.join(result.boq_row_ids or ('فاقد پیوند',)) +
            ' | فقط نمایش')
        self.oneGlobalIdSelected.emit(result.global_ids[0])
        return result

    def _clicked_member(self, item, _column):
        self._lookup('tree', item.data(0, Qt.ItemDataRole.UserRole))

    def _clicked_boq(self):
        rows = self.boq.selectionModel().selectedRows()
        if len(rows) == 1:
            value = self.boq.item(rows[0].row(), 0)
            if value is not None:
                self._lookup('boq', value.data(Qt.ItemDataRole.UserRole) or value.text())

    def select_from_geometry(self, global_id: str, *, origin='2d'):
        """2D or 3D selection highlights existing rows without selection loops."""
        try:
            result=self._resolve(origin,global_id)
        except (ValueError, RuntimeError, PermissionError) as exc:
            self._fail_stale(exc)
            return None
        with QSignalBlocker(self.members), QSignalBlocker(self.boq):
            self.members.clearSelection()
            self.boq.clearSelection()
            if result.status == 'linked':
                member_set = set(result.member_ids)
                for row in range(self.members.topLevelItemCount()):
                    item = self.members.topLevelItem(row)
                    if item.data(0, Qt.ItemDataRole.UserRole) in member_set:
                        item.setSelected(True)
                boq_set = set(result.boq_row_ids)
                for row in range(self.boq.rowCount()):
                    cell=self.boq.item(row,0)
                    if (cell.data(Qt.ItemDataRole.UserRole) or cell.text()) in boq_set:
                        self.boq.selectionModel().select(
                            self.boq.model().index(row, 0),
                            QItemSelectionModel.SelectionFlag.Select |
                            QItemSelectionModel.SelectionFlag.Rows)
        if result.status != 'linked':
            self.detail.setText('عضو در IFC وجود دارد، اما پیوند تأییدشده به عضو/BOQ یافت نشد.')
        else:
            self.detail.setText('عضو سه‌بعدی/دوبعدی: ' + global_id + ' | پیوند‌های تأییدشده: ' +
                                str(len(result.boq_row_ids)) + ' ردیف BOQ')
        return result
