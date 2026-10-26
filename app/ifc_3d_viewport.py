"""Interactive 3D IFC viewport: actual validated world-coordinate triangles only.

This read-only QPainter renderer supports orbit/pan/zoom, floor filtering and
member selection. It does not generate, calculate, or register takeoff quantities.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer, QObject, QRunnable, QThreadPool, QSignalBlocker
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QDoubleSpinBox, QLineEdit,
)
from PySide6.QtCore import QPointF

from core.drawings.source_mesh3d import VerifiedScene3D


_COLORS = {
    "IFCWALL": "#77a4c2", "IFCSLAB": "#b5c9cf", "IFCCOLUMN": "#7393ba",
    "IFCBEAM": "#6b88b3", "IFCDOOR": "#d4b08c", "IFCWINDOW": "#74b5b9",
    "IFCDUCTSEGMENT": "#66b5a1", "IFCPIPESEGMENT": "#78c2b1",
    "IFCFLOWTERMINAL": "#c3a7cf", "IFCSTAIR": "#b8a0c3",
    "IFCCOVERING": "#dbc6a1", "IFCROOF": "#b5c9cf",
}


class _SourceCheckSignals(QObject):
    completed = Signal(str)


class _SourceCheck(QRunnable):
    def __init__(self, scene):
        super().__init__()
        self.scene = scene
        self.signals = _SourceCheckSignals()

    def run(self):
        error = ''
        try:
            self.scene.validate_source()
        except ValueError as exc:
            error = str(exc)
        self.signals.completed.emit(error)


class IFC3DCanvas(QWidget):
    memberSelected = Signal(str)

    def __init__(self, scene: VerifiedScene3D, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.storey_id = None
        self.selected_id = None
        self.isolate_selection = False
        self.transparent = False
        self._drag_origin = None
        self._drag_button = None
        self._dragged = False
        self.setObjectName("VerifiedIFC3DCanvas")
        self.setMinimumSize(460, 320)
        self.setMouseTracking(True)
        self.source_error = None
        self._source_timer = QTimer(self)
        self._source_timer.setInterval(1000)
        self._source_check = None
        self._source_timer.timeout.connect(self.schedule_source_check)
        self._source_timer.start()
        self.setAccessibleName("نمای سه‌بعدی واقعی IFC با چرخش، جابه‌جایی و بزرگ‌نمایی")

    def choose_storey(self, storey_id):
        if storey_id is not None and storey_id not in self.scene.storeys:
            raise ValueError("طبقه در مدل مستند وجود ندارد.")
        self.storey_id = storey_id
        self.scene.fit_storey(storey_id)
        self.update()

    def choose_member(self, global_id):
        self.scene.validate_source()
        if global_id is not None and global_id not in {m.global_id for m in self.scene.meshes}:
            raise ValueError("عضو انتخابی در IFC موجود نیست.")
        self.selected_id = global_id
        self.update()

    def reset_camera(self):
        self.scene.reset_view()
        self.scene.fit_storey(self.storey_id)
        self.update()

    def _faces(self):
        if self.source_error:
            return ()
        return self.scene.visible_faces(
            self.width(), self.height(), storey_id=self.storey_id,
            selected_id=self.selected_id if self.isolate_selection else None)

    def check_source(self):
        try:
            self.scene.validate_source()
        except ValueError as exc:
            self.source_error = str(exc)
            self.selected_id = None
            self._source_timer.stop()
            self.update()

    def schedule_source_check(self):
        if self._source_check is not None or self.source_error:
            return
        task = _SourceCheck(self.scene)
        self._source_check = task
        task.signals.completed.connect(self._checked_source)
        QThreadPool.globalInstance().start(task)

    def _checked_source(self, error):
        self._source_check = None
        if error:
            self.source_error = error
            self.selected_id = None
            self._source_timer.stop()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101f34"))
        if self.source_error:
            painter.setPen(QColor('white'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.source_error)
        for face in self._faces():
            highlighted = face.global_id == self.selected_id
            fill = QColor("#efa849" if highlighted else
                          _COLORS.get(face.ifc_type.upper(), "#849bb8"))
            if self.transparent:
                fill.setAlpha(90)
            points = QPolygonF([QPointF(x, y) for x, y in face.points])
            painter.setPen(QPen(QColor("#f7d1a1" if highlighted else "#223b58"), 1))
            painter.setBrush(QBrush(fill))
            painter.drawPolygon(points)
        painter.end()

    def wheelEvent(self, event):
        if event.angleDelta().y():
            self.scene.set_zoom(1.2 if event.angleDelta().y() > 0 else 1/1.2)
            self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self._drag_button = event.button()
            self._drag_origin = event.position()
            self._dragged = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is None:
            return super().mouseMoveEvent(event)
        dx = event.position().x() - self._drag_origin.x()
        dy = event.position().y() - self._drag_origin.y()
        if abs(dx) + abs(dy) > 3:
            self._dragged = True
        if self._dragged:
            if self._drag_button == Qt.MouseButton.LeftButton:
                self.scene.orbit(dx / 180, dy / 180)
            else:
                self.scene.pan(dx, dy)
            self.update()
        self._drag_origin = event.position()
        event.accept()

    def mouseReleaseEvent(self, event):
        self.check_source()
        if self.source_error:
            self._drag_origin = None
            event.accept()
            return
        if self._drag_origin is not None and self._drag_button == Qt.MouseButton.LeftButton and not self._dragged:
            gid = self.scene.pick(event.position().x(), event.position().y(),
                                  self.width(), self.height(), storey_id=self.storey_id,
                                  selected_id=self.selected_id if self.isolate_selection else None)
            if gid:
                self.choose_member(gid)
                self.memberSelected.emit(gid)
        self._drag_origin = None
        self._drag_button = None
        self._dragged = False
        event.accept()


class IFC3DDialog(QDialog):
    memberSelected = Signal(str)

    def __init__(self, scene: VerifiedScene3D, parent=None, *,
                 app_service=None, project_id=""):
        super().__init__(parent)
        self.scene = scene
        self.app_service = app_service
        self.project_id = str(project_id or "").strip()
        self.setObjectName("IFC3DDocumentView")
        self.setWindowTitle("نمای سه‌بعدی واقعی IFC — فقط نمایش، بدون متره")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1140, 760)
        outer = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.storey = QComboBox()
        self.storey.setObjectName("IFC3DFloorFilter")
        self.storey.addItem("تمام طبقات مستند", None)
        for floor in scene.storeys:
            self.storey.addItem(floor, floor)
        bar.addWidget(QLabel("طبقه:"))
        bar.addWidget(self.storey)
        self.isolate = QCheckBox("ایزوله عضو انتخاب‌شده")
        bar.addWidget(self.isolate)
        reset = QPushButton("بازنشانی نما / نمایش کامل طبقه")
        reset.setObjectName("IFC3DResetCamera")
        bar.addWidget(reset)
        bar.addStretch()
        outer.addLayout(bar)
        self.canvas = IFC3DCanvas(scene, self)
        outer.addWidget(self.canvas, 1)
        tools = QHBoxLayout()
        self.section = QCheckBox('برش افقی')
        self.section_height = QDoubleSpinBox()
        self.section_height.setObjectName('IFC3DSectionHeight')
        self.section_height.setRange(-1e12, 1e12)
        self.section_height.setDecimals(4)
        self.section_height.setValue(scene.center[2])
        tools.addWidget(self.section)
        tools.addWidget(self.section_height)
        self.transparency = QCheckBox('نمای شفاف')
        tools.addWidget(self.transparency)
        self.type_filter = QComboBox()
        self.type_filter.addItem('تمام انواع مستند', None)
        for kind in sorted({m.ifc_type for m in scene.meshes}):
            self.type_filter.addItem(kind, kind)
        tools.addWidget(self.type_filter)
        self.hide_floor = QCheckBox('پنهان‌کردن طبقه انتخابی')
        tools.addWidget(self.hide_floor)
        outer.addLayout(tools)
        self.section.toggled.connect(self._section)
        self.section_height.valueChanged.connect(self._section)
        self.transparency.toggled.connect(self._transparency)
        self.type_filter.currentIndexChanged.connect(self._type_filter)
        self.hide_floor.toggled.connect(self._hide_floor)
        status = QLabel(
            f"IFC واقعی | {len(scene.meshes)} عضو | {len(scene.storeys)} طبقه دارای هندسه | "
            f"{len(scene.omitted_ids)} عضو نمایش‌داده‌نشده | Revision: {scene.revision}\n"
            f"SHA-256: {scene.source_sha256} | هندسه فقط برای نمایش است؛ متره خودکار ممنوع.")
        status.setObjectName("IFC3DProvenance")
        status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(status)
        session_row = QHBoxLayout()
        self.snapshot_id = QLineEdit()
        self.snapshot_id.setObjectName('IFC3DSnapshotId')
        self.snapshot_id.setPlaceholderText('شناسه نشست E2 ثبت‌شده')
        self.save_view = QPushButton('ذخیره نمای سه‌بعدی در E2')
        self.save_view.setObjectName('SaveIFC3DView')
        self.restore_view = QPushButton('بازیابی نمای سه‌بعدی از E2')
        self.restore_view.setObjectName('RestoreIFC3DView')
        self.save_view.setEnabled(self.app_service is not None and bool(self.project_id))
        self.restore_view.setEnabled(self.save_view.isEnabled())
        self.session_status = QLabel('نشست نمای سه‌بعدی فقط‌خواندنی؛ BOQ تغییر نمی‌کند.')
        self.session_status.setObjectName('IFC3DSessionStatus')
        self.session_status.setWordWrap(True)
        for ctrl in (self.snapshot_id, self.save_view, self.restore_view):
            session_row.addWidget(ctrl)
        outer.addLayout(session_row)
        outer.addWidget(self.session_status)
        self.save_view.clicked.connect(self.save_e2_view)
        self.restore_view.clicked.connect(self.restore_e2_view)
        self.storey.currentIndexChanged.connect(self._on_storey_changed)
        self._on_storey_changed()
        self.isolate.toggled.connect(self._isolate)
        reset.clicked.connect(self.canvas.reset_camera)
        self.canvas.memberSelected.connect(self.memberSelected)

    def save_e2_view(self):
        if not self.app_service or not self.project_id:
            self.session_status.setText('سرویس و شناسه معتبر پروژه در دسترس نیست.')
            return False
        try:
            from core.drawings.ifc3d_session_state import save_to_e2
            receipt = save_to_e2(self.app_service, self.project_id, self.scene, self.canvas)
            self.snapshot_id.setText(receipt['snapshot_id'])
            self.session_status.setText('نمای سه‌بعدی با تأیید منشأ و نسخه، در نشست E2 ذخیره شد.')
            return True
        except Exception as exc:
            self.session_status.setText('ذخیره نما انجام نشد: ' + str(exc))
            return False

    def restore_e2_view(self):
        if not self.app_service or not self.project_id:
            self.session_status.setText('سرویس و شناسه معتبر پروژه در دسترس نیست.')
            return False
        try:
            from core.drawings.ifc3d_session_state import restore_from_e2
            state = restore_from_e2(self.app_service, self.project_id,
                                    self.snapshot_id.text().strip(), self.scene, self.canvas)
            with QSignalBlocker(self.storey):
                self.storey.setCurrentIndex(self.storey.findData(state['storey_id']))
            with QSignalBlocker(self.isolate):
                self.isolate.setChecked(state['isolate'])
            with QSignalBlocker(self.transparency):
                self.transparency.setChecked(state['transparent'])
            with QSignalBlocker(self.section):
                self.section.setChecked(state['section_z'] is not None)
            if state['section_z'] is not None:
                with QSignalBlocker(self.section_height):
                    self.section_height.setValue(state['section_z'])
            visible_types = {m.ifc_type for m in self.scene.meshes} - set(state['hidden_types'])
            if len(visible_types) == 1:
                with QSignalBlocker(self.type_filter):
                    self.type_filter.setCurrentIndex(
                        self.type_filter.findData(next(iter(visible_types))))
            elif not state['hidden_types']:
                with QSignalBlocker(self.type_filter):
                    self.type_filter.setCurrentIndex(0)
            with QSignalBlocker(self.hide_floor):
                floor = state['storey_id']
                self.hide_floor.setEnabled(floor is not None)
                self.hide_floor.setChecked(floor in self.scene.hidden_storeys if floor else False)
            # E2 restores the validated 3D selection directly without
            # mouse events. Publish its exact GlobalID so the existing
            # checked 3D->2D/tree/BOQ path can synchronize; empty clears all.
            self.memberSelected.emit(state['global_id'] or '')
            self.session_status.setText('نشست E2 منطبق با منبع و Revision فعلی بازیابی شد.')
            return True
        except Exception as exc:
            self.session_status.setText('بازیابی نما رد شد: ' + str(exc))
            return False

    def _on_storey_changed(self, *_):
        floor = self.storey.currentData()
        # The checkbox edits only the selected floor; never affect a previous floor
        # when its checked state is synchronized programmatically.
        with QSignalBlocker(self.hide_floor):
            self.hide_floor.setEnabled(floor is not None)
            self.hide_floor.setChecked(floor in self.scene.hidden_storeys if floor is not None else False)
        self.canvas.choose_storey(floor)

    def _isolate(self, on):
        self.canvas.isolate_selection = bool(on)
        self.canvas.update()

    def _section(self, *_):
        self.scene.set_section(self.section_height.value() if self.section.isChecked() else None)
        self.canvas.update()

    def _transparency(self, on):
        self.canvas.transparent = bool(on)
        self.canvas.update()

    def _type_filter(self, *_):
        selected = self.type_filter.currentData()
        self.scene.hidden_types = {m.ifc_type for m in self.scene.meshes
                                   if selected is not None and m.ifc_type != selected}
        self.canvas.update()

    def _hide_floor(self, on):
        floor = self.storey.currentData()
        if floor is not None:
            if on:
                self.scene.hidden_storeys.add(floor)
            else:
                self.scene.hidden_storeys.discard(floor)
        self.canvas.update()
