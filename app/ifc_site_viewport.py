"""Native Qt window for independently verified IFC4 IfcSite-only context.

No selectable BIM member, no BOQ link, no measurements or site geodetic claims.
"""
from __future__ import annotations
from PySide6.QtCore import QObject, QRunnable, Signal, Qt, QPointF, QTimer, QThreadPool
from PySide6.QtGui import QPainter, QPen, QBrush, QPolygonF, QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget, QLabel
from core.drawings.site_context import verified_site_context, file_digest


class SiteLoadSignals(QObject):
    completed = Signal(int, object)
    failed = Signal(int, str)


class SiteLoadJob(QRunnable):
    def __init__(self, *, token, path, revision, expected_sha256):
        super().__init__()
        self.signals = SiteLoadSignals()
        self.token, self.path, self.revision = token, path, revision
        self.expected_sha256 = expected_sha256
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            scene = verified_site_context(self.path, revision=self.revision,
                                          expected_sha256=self.expected_sha256)
            if not self.cancelled:
                self.signals.completed.emit(self.token, scene)
        except Exception as exc:
            if not self.cancelled:
                self.signals.failed.emit(self.token, str(exc))


class SiteTerrainCanvas(QWidget):
    def __init__(self, terrain_scene, parent=None):
        super().__init__(parent)
        self.scene = terrain_scene
        self.setObjectName("IFCSiteSpatialContextCanvas")
        self.setMinimumSize(520, 360)
        self.setAccessibleName("نمای صرفاً تصویری زمین IfcSite؛ بدون انتخاب عضو و متره")
        self._start = None
        self._button = None
        self.source_error = None
        self._source_timer = QTimer(self)
        self._source_timer.setInterval(1100)
        self._source_timer.timeout.connect(self.check_source)
        self._source_timer.start()

    def check_source(self):
        try:
            self.scene.validate_source()
        except (OSError, ValueError) as exc:
            self.source_error = "فایل منبع زمین تغییر کرده یا دیگر در دسترس نیست."
            self._source_timer.stop()
            self.update()

    def paintEvent(self,event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#102236"))
        if self.source_error:
            painter.setPen(QColor("white"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.source_error)
        else:
            painter.setPen(QPen(QColor("#668b9f"),1))
            painter.setBrush(QBrush(QColor("#6da99a")))
            for face in self.scene.projected_triangles(self.width(),self.height()):
                painter.drawPolygon(QPolygonF([QPointF(x,y) for x,y in face]))
        painter.end()

    def wheelEvent(self,event):
        if not self.source_error and event.angleDelta().y():
            self.scene.set_zoom(1.2 if event.angleDelta().y()>0 else 1/1.2)
            self.update()
        event.accept()

    def mousePressEvent(self,event):
        self.check_source()
        if not self.source_error and event.button() in (Qt.MouseButton.LeftButton,Qt.MouseButton.RightButton):
            self._start=event.position()
            self._button=event.button()
        event.accept()

    def mouseMoveEvent(self,event):
        if self._start is not None and not self.source_error:
            dx=event.position().x()-self._start.x()
            dy=event.position().y()-self._start.y()
            if self._button==Qt.MouseButton.LeftButton:
                self.scene.orbit(dx/180,dy/180)
            else:
                self.scene.pan(dx,dy)
            self.update()
            self._start=event.position()
        event.accept()

    def mouseReleaseEvent(self,event):
        self._start=None
        self._button=None
        event.accept()


class SiteTerrainDialog(QDialog):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.scene=scene
        self.setObjectName("IFCSiteSpatialContextDialog")
        self.setWindowTitle("زمین IFC4 — زمینه مکانی، فقط نمایش")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1000,680)
        layout=QVBoxLayout(self)
        self.caption=QLabel(
            "هندسهٔ واقعی IfcSite | زمینهٔ مکانی، نه IfcElement و نه عضو متره\n"
            "انتخاب عضو، محاسبه مقدار، BOQ و تبدیل GIS مجاز نیست.\n"
            + ("هشدار: GlobalId زمین غیرکانونی است؛ هویت تنها با SHA فایل است و اتصال عضو ممنوع است.\n"
               if not scene.site_identity_canonical else "")
            + "Revision: "+scene.revision+" | SHA-256: "+scene.source_sha256)
        self.caption.setObjectName("IFCSiteSpatialProvenance")
        self.caption.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.caption.setWordWrap(True)
        layout.addWidget(self.caption)
        self.canvas=SiteTerrainCanvas(scene,self)
        layout.addWidget(self.canvas,1)
