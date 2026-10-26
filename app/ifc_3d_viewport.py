"""Interactive 3D IFC viewport: actual validated world-coordinate triangles only.

This read-only QPainter renderer supports orbit/pan/zoom, floor filtering and
member selection. It does not generate, calculate, or register takeoff quantities.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QDoubleSpinBox,
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
        self._source_timer.timeout.connect(self.check_source)
        self._source_timer.start()
        self.setAccessibleName("نمای سه‌بعدی واقعی IFC با چرخش، جابه‌جایی و بزرگ‌نمایی")

    def choose_storey(self, storey_id):
        if storey_id is not None and storey_id not in self.scene.storeys:
            raise ValueError("طبقه در مدل مستند وجود ندارد.")
        self.storey_id = storey_id
        self.update()

    def choose_member(self, global_id):
        self.scene.validate_source()
        if global_id is not None and global_id not in {m.global_id for m in self.scene.meshes}:
            raise ValueError("عضو انتخابی در IFC موجود نیست.")
        self.selected_id = global_id
        self.update()

    def reset_camera(self):
        self.scene.reset_view()
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

    def __init__(self, scene: VerifiedScene3D, parent=None):
        super().__init__(parent)
        self.scene = scene
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
        reset = QPushButton("بازنشانی نما")
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
        self.storey.currentIndexChanged.connect(
            lambda _index: self.canvas.choose_storey(self.storey.currentData()))
        self.isolate.toggled.connect(self._isolate)
        reset.clicked.connect(self.canvas.reset_camera)
        self.canvas.memberSelected.connect(self.memberSelected)

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
