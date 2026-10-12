"""Professional Windows drawing takeoff workspace for StructuralPro."""
from __future__ import annotations

from pathlib import Path
import json

from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, QByteArray
from PySide6.QtGui import QPen, QBrush, QColor, QPixmap, QPolygonF, QFont, QTextOption, QPainterPath
from core.cad.persian_text_v1 import normalize_cad_text, is_rtl_cad_text, cad_text_height
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QComboBox,
    QLabel, QGraphicsView, QGraphicsScene, QDialog, QTableWidget,
    QTableWidgetItem, QSpinBox, QFileDialog, QMessageBox, QFrame,
    QDoubleSpinBox, QInputDialog, QHeaderView, QRubberBand, QGridLayout
)

from core.drawings.graphical_takeoff import Point
from core.drawings.pdf_engine import PDFDrawingEngine
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.viewer_model import DrawingViewerModel
from core.drawings.viewport_tools import ViewportRect
from core.drawings.region_takeoff import calibrated_rectangle_area, rectangle_to_points
from core.drawings.takeoff_bridge import build_takeoff_export_payload


class TakeoffCanvas(QGraphicsView):
    def __init__(self, session: DrawingTakeoffSession, on_change=None, on_note=None):
        super().__init__()
        self.session = session
        self.on_change = on_change
        self.on_note = on_note
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.points: list[Point] = []
        self.mode = "length"
        self.read_only_model = False
        self._previous_mode = "length"
        self._selection_origin = None
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        self._region_overlay = None
        self._selected_region_rect = None
        self.on_tool_status = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def set_mode(self, mode: str):
        if self.read_only_model and mode not in {"pan", "zoom_window", "region_select"}:
            mode = "pan"
        if mode in {"zoom_window", "region_select"} and self.mode not in {"zoom_window", "region_select"}:
            self._previous_mode = self.mode
        self.cancel_interaction(reset_tool=False, announce=False)
        self.mode = mode
        self.points = []
        if mode in {"zoom_window", "region_select"}:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.unsetCursor()

    def _announce_tool(self, message: str):
        if self.on_tool_status:
            self.on_tool_status(message)

    def _set_region_highlight(self, rect: QRectF):
        """Keep the selected drawing region highlighted in scene coordinates."""
        self.clear_region_selection()
        self._selected_region_rect = QRectF(rect)
        pen = QPen(QColor(190, 70, 0), 0)
        brush = QBrush(QColor(255, 190, 0, 58))
        self._region_overlay = self.scene.addRect(rect, pen, brush)
        # The overlay is visual only; it must not intercept later mouse tools.
        self._region_overlay.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._region_overlay.setZValue(1000)

    def clear_region_selection(self):
        if self._region_overlay is not None:
            self.scene.removeItem(self._region_overlay)
            self._region_overlay = None
        self._selected_region_rect = None

    def cancel_interaction(self, reset_tool: bool = True, announce: bool = True):
        self._selection_origin = None
        self._rubber_band.hide()
        self.points = []
        self.clear_region_selection()
        if reset_tool and self.mode in {"zoom_window", "region_select"}:
            self.mode = self._previous_mode
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.unsetCursor()
        if announce:
            self._announce_tool("عملیات انتخاب لغو شد؛ نمای نقشه تغییر نکرد.")

    def wheelEvent(self, event):
        self.scale_view(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)

    def scale_view(self, factor: float):
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.mode in {"zoom_window", "region_select"}:
            self.cancel_interaction()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        if self.mode in {"zoom_window", "region_select"}:
            self._selection_origin = event.position().toPoint()
            self._rubber_band.setGeometry(QRect(self._selection_origin, self._selection_origin))
            self._rubber_band.show()
            self.setFocus()
            return
        if self.read_only_model:
            return super().mousePressEvent(event)
        p = self.mapToScene(event.position().toPoint())
        page = self.session.current_page

        if self.mode == "note":
            if self.on_note:
                self.on_note(p.x(), p.y(), page)
            return

        point = Point(p.x(), p.y())
        self.points.append(point)
        self.scene.addEllipse(
            p.x() - 3, p.y() - 3, 6, 6,
            QPen(Qt.GlobalColor.darkBlue), QBrush(Qt.GlobalColor.darkBlue)
        )

        if self.mode == "count":
            self._commit_count()
            return

        if len(self.points) > 1:
            a, b = self.points[-2], self.points[-1]
            self.scene.addLine(
                a.x, a.y, b.x, b.y, QPen(Qt.GlobalColor.blue, 2)
            )

    def mouseMoveEvent(self, event):
        if self._selection_origin is not None:
            self._rubber_band.setGeometry(
                QRect(self._selection_origin, event.position().toPoint()).normalized()
            )
            return
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._selection_origin is not None:
            viewport_rect = QRect(self._selection_origin, event.position().toPoint()).normalized()
            self._selection_origin = None
            self._rubber_band.hide()
            top_left = self.mapToScene(viewport_rect.topLeft())
            bottom_right = self.mapToScene(viewport_rect.bottomRight())
            bounds = self.scene.sceneRect()
            selected = ViewportRect.from_points(
                top_left.x(), top_left.y(), bottom_right.x(), bottom_right.y()
            ).clamped(ViewportRect(bounds.left(), bounds.top(), bounds.right(), bounds.bottom()))
            if not selected.is_usable():
                self._announce_tool("ناحیه خیلی کوچک است؛ مستطیل بزرگ‌تری انتخاب کن یا لغو کن.")
                return
            scene_rect = QRectF(selected.left, selected.top, selected.width, selected.height)
            if self.mode == "zoom_window":
                self._set_region_highlight(scene_rect)
                self.fitInView(scene_rect, Qt.AspectRatioMode.KeepAspectRatio)
                self._announce_tool(
                    f"ناحیه زوم و هایلایت شد | عرض: {selected.width:.2f} | ارتفاع: {selected.height:.2f} واحد نقشه"
                )
            else:
                self._set_region_highlight(scene_rect)
                self._announce_tool(
                    f"ناحیه هایلایت شد | عرض: {selected.width:.2f} | ارتفاع: {selected.height:.2f} واحد نقشه"
                )
            return
        return super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_interaction()
            event.accept()
            return
        return super().keyPressEvent(event)

    def _commit_count(self):
        try:
            self.session.add_count(
                1, page=self.session.current_page, label="شمارش",
                source=f"page:{self.session.current_page}:count:{len(self.session.items)+1}"
            )
            self.points = []
            self._notify()
        except Exception as exc:
            QMessageBox.warning(self, "متره", str(exc))

    def finish(self):
        if self.read_only_model:
            return
        try:
            if self.mode == "length" and len(self.points) >= 2:
                self.session.add_length(
                    self.points, page=self.session.current_page, label="متره طولی",
                    source=f"page:{self.session.current_page}:length:{len(self.session.items)+1}"
                )
            elif self.mode == "area" and len(self.points) >= 3:
                self.session.add_area(
                    self.points, page=self.session.current_page, label="متره سطحی",
                    source=f"page:{self.session.current_page}:area:{len(self.session.items)+1}"
                )
            else:
                self.points = []
                return
            self.points = []
            self._notify()
        except Exception as exc:
            QMessageBox.warning(self, "ثبت متره", str(exc))

    def _draw_measurement(self, item):
        if item.kind == "length" and len(item.geometry) >= 2:
            pts = [QPointF(x, y) for x, y in item.geometry]
            for i in range(len(pts) - 1):
                self.scene.addLine(
                    pts[i].x(), pts[i].y(), pts[i + 1].x(), pts[i + 1].y(),
                    QPen(Qt.GlobalColor.blue, 3)
                )
        elif item.kind == "area" and len(item.geometry) >= 3:
            poly = QPolygonF([QPointF(x, y) for x, y in item.geometry])
            self.scene.addPolygon(
                poly, QPen(Qt.GlobalColor.darkBlue, 2),
                QBrush(Qt.GlobalColor.lightGray)
            )

    def _notify(self):
        if self.on_change:
            self.on_change()


class GraphicalTakeoffDialog(QDialog):
    def __init__(self, parent=None, pdf_path="", *, app_service=None, project_id=""):
        super().__init__(parent)
        self.setWindowTitle("متره گرافیکی — نقشه‌محور")
        self.resize(1450, 920)
        self.session = DrawingTakeoffSession(pdf_path)
        self.pdf_path = pdf_path
        self.app_service = app_service
        self.persisted_project_id = str(project_id or "").strip()
        self.persisted_session_id = None
        self.persisted_session_revision = None
        self.engine = None
        self.viewer = DrawingViewerModel()
        self.cad_document = None
        self.page = 1

        root = QVBoxLayout(self)
        toolbar = QFrame()
        toolbar.setObjectName("DashboardCard")
        toolbar_rows = QVBoxLayout(toolbar)
        header = QHBoxLayout()
        toolbar_rows.addLayout(header)
        header.setContentsMargins(12, 10, 12, 10)

        header.addWidget(QLabel("ابزار:"))
        self.mode = QComboBox()
        self.mode.addItems(["طول", "مساحت", "شمارش", "یادداشت"])
        header.addWidget(self.mode)

        self.scale_label = QLabel("مقیاس: هنوز کالیبره نشده")
        self.calibrate = QPushButton("کالیبراسیون")
        self.calibrate.setObjectName("SecondaryAction")
        header.addWidget(self.scale_label)
        header.addWidget(self.calibrate)

        self.open_pdf = QPushButton("بازکردن نقشه")
        self.prev = QPushButton("صفحه قبلی")
        self.next = QPushButton("صفحه بعدی")
        self.page_no = QSpinBox()
        self.page_no.setMinimum(1)
        self.page_no.setMaximum(9999)
        self.page_no.setPrefix("صفحه ")
        self.zoom_out = QPushButton("−")
        self.zoom_in = QPushButton("+")
        self.fit = QPushButton("نمایش کامل")
        self.zoom_window = QPushButton("بزرگ‌نمایی ناحیه")
        self.select_region = QPushButton("انتخاب ناحیه")
        self.cancel_selection = QPushButton("لغو انتخاب/هایلایت")
        self.region_to_takeoff = QPushButton("ثبت ناحیه در متره")
        self.source_label = QLabel("منبع: —")
        self.project_id_input = QLineEdit(self.persisted_project_id)
        self.project_id_input.setPlaceholderText("شناسه پروژه برای ذخیره دائمی")
        self.save_session_button = QPushButton("ذخیره نشست متره")
        self.load_session_button = QPushButton("بارگذاری نشست")
        self.commit_boq_button = QPushButton("انتقال انتخاب به BOQ")
        self.save_session_button.setToolTip("نشست نقشه، کالیبراسیون‌ها و ریزمتره‌ها را در پروژه ذخیره می‌کند.")
        self.load_session_button.setToolTip("نشست ذخیره‌شده را از پروژه بازیابی می‌کند.")
        self.commit_boq_button.setToolTip("فقط ردیف‌های انتخاب‌شده، پس از تأیید، به BOQ منتقل می‌شوند.")
        self.save_session_button.setEnabled(self.app_service is not None)
        self.load_session_button.setEnabled(self.app_service is not None)
        self.commit_boq_button.setEnabled(self.app_service is not None)
        self.export_boq = QPushButton("خروجی متره برای بازبینی")
        self.finish = QPushButton("ثبت متره")
        self.undo = QPushButton("↶ واگرد")
        self.redo = QPushButton("↷ تکرار")
        self.delete = QPushButton("حذف انتخاب")
        actions = QGridLayout()
        toolbar_rows.addLayout(actions)
        for index, x in enumerate([
            self.open_pdf, self.prev, self.next, self.page_no,
            self.zoom_out, self.zoom_in, self.fit, self.zoom_window,
            self.select_region, self.cancel_selection, self.region_to_takeoff, self.undo, self.redo,
            self.delete, self.finish, self.project_id_input, self.save_session_button,
            self.load_session_button, self.commit_boq_button, self.export_boq
        ]):
            actions.addWidget(x, index // 6, index % 6)
        toolbar_rows.addWidget(self.source_label)
        root.addWidget(toolbar)

        self.canvas = TakeoffCanvas(self.session, self.refresh, self.add_note)
        self.canvas.setFrameShape(QFrame.Shape.StyledPanel)
        root.addWidget(self.canvas, 5)

        table_title = QLabel("متره‌های ثبت‌شده — قابل بازبینی و اتصال به BOQ")
        table_title.setObjectName("SectionTitle")
        root.addWidget(table_title)

        self.table = QTableWidget(0, 8)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels([
            "شناسه", "صفحه", "نوع", "شرح", "مقدار", "واحد", "کد BOQ", "منبع"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 2)

        self.status = QLabel("برای شروع، نقشه را باز کنید و مقیاس را کالیبره کنید.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.canvas.on_tool_status = self.status.setText

        self.mode.currentTextChanged.connect(self.apply_tool)
        self.calibrate.clicked.connect(self.calibrate_scale)
        self.open_pdf.clicked.connect(self.select_drawing)
        self.prev.clicked.connect(lambda: self.load_page(self.page - 1))
        self.next.clicked.connect(lambda: self.load_page(self.page + 1))
        self.page_no.valueChanged.connect(self.load_page)
        self.zoom_in.clicked.connect(lambda: self.canvas.scale_view(1.25))
        self.zoom_out.clicked.connect(lambda: self.canvas.scale_view(0.8))
        self.fit.clicked.connect(self.reset_zoom)
        self.zoom_window.clicked.connect(
            lambda: self._activate_view_tool("zoom_window", "مستطیل ناحیه بزرگ‌نمایی را با ماوس بکش؛ Esc یا کلیک راست لغو می‌کند.")
        )
        self.select_region.clicked.connect(
            lambda: self._activate_view_tool("region_select", "مستطیل ناحیه موردنظر را با ماوس بکش؛ Esc یا کلیک راست لغو می‌کند.")
        )
        self.cancel_selection.clicked.connect(lambda: self.canvas.cancel_interaction())
        self.region_to_takeoff.clicked.connect(self.register_selected_region)
        self.finish.clicked.connect(self.canvas.finish)
        self.export_boq.clicked.connect(self.export_takeoff_for_boq)
        self.undo.clicked.connect(self.undo_session)
        self.redo.clicked.connect(self.redo_session)
        self.delete.clicked.connect(self.delete_selected)
        self.save_session_button.clicked.connect(self.save_session_to_project)
        self.load_session_button.clicked.connect(self.load_session_from_project)
        self.commit_boq_button.clicked.connect(self.commit_selected_to_boq)

        if pdf_path:
            try:
                self.open_drawing(pdf_path)
            except Exception as exc:
                QMessageBox.warning(self, "نقشه", "فایل برای نمایش گرافیکی باز نشد: " + str(exc))

    def save_session_to_project(self):
        if self.app_service is None:
            QMessageBox.warning(self, "ذخیره نشست", "سرویس پروژه در این پنجره در دسترس نیست.")
            return False
        project_id = self.project_id_input.text().strip()
        if not project_id:
            QMessageBox.warning(self, "شناسه پروژه", "برای ذخیره دائمی، شناسه پروژه را وارد کنید.")
            return False
        try:
            result = self.app_service.save_drawing_takeoff_session(
                project_id, self.session, session_id=self.persisted_session_id,
                expected_revision=self.persisted_session_revision,
            )
            self.persisted_project_id = project_id
            self.persisted_session_id = result["session_id"]
            self.persisted_session_revision = result["revision"]
            self.status.setText(
                f"🟢 نشست نقشه ذخیره شد | نسخه {result['revision']} | "
                f"متره‌ها: {result['item_count']} | شناسه نشست: {result['session_id']}"
            )
            return True
        except Exception as exc:
            QMessageBox.critical(self, "ذخیره نشست متره", "ذخیره انجام نشد؛ داده موجود حفظ شد.\n" + str(exc))
            return False

    def load_session_from_project(self):
        if self.app_service is None:
            QMessageBox.warning(self, "بارگذاری نشست", "سرویس پروژه در این پنجره در دسترس نیست.")
            return
        project_id = self.project_id_input.text().strip()
        if not project_id:
            QMessageBox.warning(self, "شناسه پروژه", "ابتدا شناسه پروژه را وارد کنید.")
            return
        session_id, accepted = QInputDialog.getText(
            self, "بارگذاری نشست متره", "شناسه نشست ذخیره‌شده:"
        )
        if not accepted or not session_id.strip():
            return
        try:
            from core.drawings.viewer_model import DrawingViewerModel
            record = self.app_service.load_drawing_takeoff_session(project_id, session_id.strip())
            restored = DrawingTakeoffSession.from_dict(record["session"])
            source = Path(restored.drawing_source)
            if not source.is_file():
                raise FileNotFoundError("فایل نقشه اصلی در این مسیر در دسترس نیست؛ نشست ذخیره‌شده تغییر نکرد.")
            new_viewer = DrawingViewerModel()
            new_viewer.open(source)
            new_engine = PDFDrawingEngine(source) if new_viewer.kind == "pdf" else None
            self.viewer = new_viewer
            self.engine = new_engine
            self.cad_document = new_viewer.cad_document
            self.session = restored
            self.canvas.session = restored
            self.pdf_path = str(source)
            self.persisted_project_id = project_id
            self.persisted_session_id = record["id"]
            self.persisted_session_revision = int(record["revision"])
            self.source_label.setText(f"منبع: {new_viewer.source_name} | {new_viewer.kind.upper()}")
            self.page_no.setMaximum(max(1, new_viewer.page_count))
            self.load_page(min(restored.current_page, max(1, new_viewer.page_count)))
            self.status.setText(
                f"🟢 نشست بازیابی شد | نسخه {self.persisted_session_revision} | "
                f"متره‌ها: {len(restored.items)}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "بارگذاری نشست", "بازیابی انجام نشد؛ نشست ذخیره‌شده تغییر نکرد.\n" + str(exc))

    def commit_selected_to_boq(self):
        if self.viewer.kind == "ifc":
            self._ifc_status()
            return
        if self.app_service is None:
            QMessageBox.warning(self, "انتقال به BOQ", "سرویس پروژه در این پنجره در دسترس نیست.")
            return
        selected_rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        if not selected_rows:
            QMessageBox.information(self, "انتقال به BOQ", "ابتدا ردیف‌های متره موردنظر را در جدول انتخاب کنید.")
            return
        selected_ids = [self.table.item(row, 0).text() for row in selected_rows if self.table.item(row, 0)]
        if not selected_ids:
            QMessageBox.warning(self, "انتقال به BOQ", "شناسه ردیف انتخاب‌شده قابل خواندن نیست.")
            return
        if not self.save_session_to_project():
            return
        answer = QMessageBox.question(
            self, "تأیید انتقال به BOQ",
            f"تعداد {len(selected_ids)} متره از نشست «{self.persisted_session_id}» به پروژه "
            f"«{self.persisted_project_id}» منتقل شود؟\n"
            "منبع نقشه، صفحه، هندسه و فرمول حفظ می‌شود. ثبت تکراری رد خواهد شد.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status.setText("انتقال به BOQ لغو شد؛ هیچ ردیفی منتقل نشد.")
            return
        try:
            result = self.app_service.commit_drawing_takeoff_to_boq(
                self.persisted_project_id, self.persisted_session_id, selected_ids,
                expected_session_revision=self.persisted_session_revision,
            )
            self.persisted_session_revision = result["revision"]
            self.status.setText(
                f"🟢 انتقال به BOQ انجام شد | ردیف جدید: {len(result['takeoffs_added'])} | "
                f"BOQ: {result['boq_count']} ردیف | نشست نسخه {result['revision']}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "انتقال به BOQ", "انتقال انجام نشد؛ BOQ بدون تغییر باقی ماند.\n" + str(exc))

    def select_drawing(self):
        path = QFileDialog.getOpenFileName(
            self, "انتخاب نقشه", "", "نقشه‌ها (*.pdf *.dwg *.dxf *.ifc);;PDF (*.pdf);;CAD (*.dwg *.dxf);;مدل ساختمان (*.ifc);;همه فایل‌ها (*)"
        )[0]
        if not path:
            return
        try:
            self.open_drawing(path)
        except Exception as exc:
            QMessageBox.critical(self, "خطای نقشه", str(exc))

    def select_pdf(self):
        self.select_drawing()

    def open_drawing(self, path):
        candidate = str(path)
        changed_source = bool(self.session.drawing_source and self.session.drawing_source != candidate)
        if changed_source and self.session.items:
            answer = QMessageBox.question(
                self, "تغییر نقشه",
                "نشست فعلی دارای متره است. بازکردن نقشه جدید، متره‌های موجود را از این پنجره جدا می‌کند؛ "
                "در صورت ذخیره قبلی، نشست قبلی در پروژه باقی می‌ماند. ادامه می‌دهید؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        # Open first: if parsing fails, retain the currently displayed drawing/session.
        self.viewer.open(candidate)
        new_engine = PDFDrawingEngine(candidate) if self.viewer.kind == "pdf" else None
        if self.engine is not None:
            self.engine.close()
        if self.session.drawing_source != candidate:
            self.session = DrawingTakeoffSession(candidate)
            self.canvas.session = self.session
            self.persisted_session_id = None
            self.persisted_session_revision = None
        self.pdf_path = candidate
        self.source_label.setText(f"منبع: {self.viewer.source_name} | {self.viewer.kind.upper()}")
        self.page_no.setMaximum(max(1, self.viewer.page_count))
        self.cad_document = self.viewer.cad_document
        self.engine = new_engine
        self.load_page(1)

    def load_page(self, page):
        if not self.viewer.path or page < 1 or page > max(1, self.viewer.page_count):
            return
        try:
            self.page = int(page)
            self.session.set_page(self.page)
            self.page_no.blockSignals(True)
            self.page_no.setValue(self.page)
            self.page_no.blockSignals(False)

            self.canvas.scene.clear()
            self.canvas._region_overlay = None
            self.canvas._selected_region_rect = None
            self.canvas.points = []
            model_view = self.viewer.kind == "ifc"
            calibration = self.session.calibration
            self.scale_label.setText(
                "نمای مدل؛ متره از تصویر غیرفعال است" if model_view else
                (f"مقیاس: {calibration.meters_per_pixel:.6f} متر بر واحد نمایش"
                 if calibration else "مقیاس: هنوز کالیبره نشده")
            )
            self.canvas.read_only_model = model_view
            for control in (self.mode, self.calibrate, self.region_to_takeoff, self.finish):
                control.setEnabled(not model_view)
            self.commit_boq_button.setEnabled(not model_view and self.app_service is not None)
            self.export_boq.setEnabled(not model_view)
            self.canvas.set_mode("pan" if model_view else {
                "طول": "length", "مساحت": "area", "شمارش": "count", "یادداشت": "note"
            }[self.mode.currentText()])
            if self.viewer.kind == "pdf":
                data = self.engine.render(self.page, 150)
                pix = QPixmap()
                if not pix.loadFromData(QByteArray(data), "PNG"):
                    raise RuntimeError("رندر PDF ناموفق بود.")
                self.canvas.scene.addPixmap(pix)
                self.canvas.setSceneRect(0, 0, pix.width(), pix.height())
                for item in self.session.for_page(self.page):
                    self.canvas._draw_measurement(item)
            elif model_view:
                self._render_ifc()
            else:
                self._render_cad()
            self.refresh()
            if model_view:
                self._ifc_status()
            self.reset_zoom()
        except Exception as exc:
            QMessageBox.critical(self, "خطای نمایش PDF", str(exc))

    def _render_cad(self):
        doc = self.cad_document
        if doc is None:
            raise RuntimeError("سند CAD برای نمایش آماده نیست.")
        coords=[]
        for entity in doc.entities:
            data=entity.data
            coords.extend((float(x),float(y)) for x,y in data.get("display_points", data.get("points",[])))
            if entity.entity_type == "CIRCLE" and data.get("center") and data.get("radius"):
                x, y = data["center"]; r = data["radius"]
                coords.extend([(x-r, y-r), (x+r, y+r)])
            for key in ("start","end","center","insert"):
                if key in data and data[key] is not None:
                    coords.append((float(data[key][0]),float(data[key][1])))
        if not coords:
            self.canvas.scene.addText("CAD فاقد هندسه قابل نمایش است.")
            self.canvas.setSceneRect(0,0,1000,700)
            return
        min_x=min(x for x,_ in coords); max_x=max(x for x,_ in coords)
        min_y=min(y for _,y in coords); max_y=max(y for _,y in coords)
        margin=max(max_x-min_x,max_y-min_y,1.0)*0.05
        min_x-=margin; max_x+=margin; min_y-=margin; max_y+=margin
        def sx(x): return x-min_x
        def sy(y): return max_y-y
        pen=QPen(Qt.GlobalColor.darkBlue,0)
        for entity in doc.entities:
            d=entity.data
            if entity.entity_type=="LINE" and d.get("start") and d.get("end"):
                a,b=d["start"],d["end"]
                self.canvas.scene.addLine(sx(a[0]),sy(a[1]),sx(b[0]),sy(b[1]),pen)
            elif entity.entity_type in {"LWPOLYLINE","POLYLINE", "ARC"} and len(d.get("display_points", d.get("points",[])))>=2:
                pts=[QPointF(sx(x),sy(y)) for x,y in d.get("display_points", d.get("points",[]))]
                path = QPainterPath(pts[0])
                for point in pts[1:]:
                    path.lineTo(point)
                if d.get("closed", False):
                    path.closeSubpath()
                self.canvas.scene.addPath(path, pen)
            elif entity.entity_type=="CIRCLE" and d.get("center") and d.get("radius"):
                x,y=d["center"]; r=float(d["radius"])
                self.canvas.scene.addEllipse(sx(x-r),sy(y+r),2*r,2*r,pen)
            elif entity.entity_type in {"TEXT","MTEXT"} and d.get("text"):
                text = normalize_cad_text(d["text"])
                if not text:
                    continue
                pos = d.get("insert", d.get("start", (0, 0)))
                height = cad_text_height(d)
                font = QFont("Tahoma")
                font.setPixelSize(max(1, min(1000, round(height))))
                item = self.canvas.scene.addText(text, font)
                item.setDefaultTextColor(QColor(20, 35, 70))
                option = item.document().defaultTextOption()
                option.setTextDirection(
                    Qt.LayoutDirection.RightToLeft
                    if is_rtl_cad_text(text)
                    else Qt.LayoutDirection.LeftToRight
                )
                item.document().setDefaultTextOption(option)
                # CAD insertion points usually refer to the text baseline;
                # Qt graphics text items are positioned from their top edge.
                item.setPos(sx(pos[0]), sy(pos[1]) - height)
        self.canvas.setSceneRect(0,0,max_x-min_x,max_y-min_y)
        self.status.setText(f"🟢 CAD نمایش داده شد | {len(doc.entities)} المان | لایه‌ها: {len(doc.layers)} | واحد: {doc.units}")

    def _ifc_status(self):
        doc = self.viewer.ifc_document
        self.status.setText(
            f"نمای ایزومتریک مدل | {len(doc.meshes)} عنصر | "
            f"نمایش‌داده‌نشده: {len(doc.omitted_ids)} عنصر | "
            "متره از تصویر مدل مجاز نیست؛ کمیت‌های مدل در بخش بررسی نقشه بازبینی می‌شوند."
        )

    def _render_ifc(self):
        """Project actual mesh triangles; display coordinates are never takeoff input."""
        doc = self.viewer.ifc_document
        if doc is None:
            raise RuntimeError("مدل برای نمایش آماده نیست.")
        triangles = []
        for mesh in doc.meshes:
            for indices in mesh.triangles:
                points = [mesh.vertices[i] for i in indices]
                projected = [QPointF((x-y)*0.866025403784, (x+y)*0.5-z) for x,y,z in points]
                depth = sum(x+y+z for x,y,z in points) / 3
                triangles.append((depth, mesh, projected))
        pen = QPen(QColor(42, 75, 110), 0)
        for _, mesh, points in sorted(triangles, key=lambda row: row[0]):
            item = self.canvas.scene.addPolygon(QPolygonF(points), pen, QBrush(QColor(155, 190, 215)))
            item.setToolTip(f"{mesh.name}\nشناسه: {mesh.global_id}\nاثر انگشت: {doc.source_sha256}")
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        bounds = self.canvas.scene.itemsBoundingRect()
        margin = max(bounds.width(), bounds.height(), 1.0) * 0.05
        self.canvas.setSceneRect(bounds.adjusted(-margin, -margin, margin, margin))
        self._ifc_status()

    def _activate_view_tool(self, mode: str, instruction: str):
        self.canvas.set_mode(mode)
        self.status.setText(instruction)

    def reset_zoom(self):
        self.canvas.cancel_interaction(reset_tool=True, announce=False)
        self.canvas.clear_region_selection()
        self.canvas.resetTransform()
        if self.canvas.scene.sceneRect().isValid():
            self.canvas.fitInView(
                self.canvas.scene.sceneRect(),
                Qt.AspectRatioMode.KeepAspectRatio
            )

    def register_selected_region(self):
        """Convert the highlighted rectangle into a traceable area takeoff item."""
        if self.viewer.kind == "ifc":
            self._ifc_status()
            return
        rect = self.canvas._selected_region_rect
        if rect is None or not rect.isValid() or rect.width() <= 0 or rect.height() <= 0:
            QMessageBox.information(self, "ثبت ناحیه", "ابتدا با «انتخاب ناحیه» یا «Zoom Window» یک ناحیه معتبر مشخص کنید.")
            return
        if self.session.calibration is None:
            QMessageBox.warning(self, "کالیبراسیون لازم است", "برای تبدیل پیکسل به مترمربع، ابتدا مقیاس همین نقشه را کالیبره کنید.")
            return
        label, ok = QInputDialog.getText(self, "شرح متره ناحیه", "شرح آیتم (مثلاً کف اتاق ۱۰۱):", text="متره سطحی از ناحیه انتخاب‌شده")
        if not ok or not label.strip():
            return
        code, ok = QInputDialog.getText(self, "کد BOQ (اختیاری)", "کد ردیف فهرست‌بها / BOQ:")
        if not ok:
            return
        try:
            points = rectangle_to_points(rect.left(), rect.top(), rect.right(), rect.bottom())
            calibration = self.session.calibration
            preview_area = calibrated_rectangle_area(
                rect.left(), rect.top(), rect.right(), rect.bottom(),
                calibration.meters_per_pixel,
            )
            source = (f"region:page={self.page}:left={rect.left():.6f}:top={rect.top():.6f}:"
                      f"right={rect.right():.6f}:bottom={rect.bottom():.6f}")
            confirmation = (
                f"پیش‌نمایش متره ناحیه\n\n"
                f"صفحه: {self.page}\nشرح: {label.strip()}\n"
                f"مقدار محاسبه‌شده: {preview_area:.4f} مترمربع\n"
                f"کالیبراسیون: {calibration.meters_per_pixel:.8f} متر/پیکسل\n"
                f"کد BOQ: {code.strip() or '—'}\n\n"
                "این مقدار فقط از مستطیل انتخاب‌شده و کالیبراسیون ثبت‌شده محاسبه شده است. "
                "قبل از تأیید، محدوده و مقیاس نقشه را بررسی کنید. آیا در متره ثبت شود؟"
            )
            answer = QMessageBox.question(
                self, "تأیید مقدار متره", confirmation,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.status.setText("ثبت ناحیه لغو شد؛ هیچ آیتم متره‌ای اضافه نشد.")
                return
            item = self.session.add_area(
                [Point(x, y) for x, y in points], page=self.page, label=label.strip(),
                takeoff_code=code.strip(), source=source,
            )
            selected_rect = QRectF(rect)
            self.redraw_current_page()
            self.canvas._set_region_highlight(selected_rect)
            self.refresh()
            self.status.setText(
                f"🟢 ناحیه به متره ثبت شد | {item.id} | {item.quantity:.4f} m² | صفحه {item.page} | کد BOQ: {item.takeoff_code or '—'}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "ثبت ناحیه", str(exc))

    def apply_tool(self):
        mapping = {
            "طول": "length", "مساحت": "area",
            "شمارش": "count", "یادداشت": "note"
        }
        self.canvas.set_mode(mapping[self.mode.currentText()])
        self.status.setText(
            f"ابزار فعال: {self.mode.currentText()} | صفحه {self.page}"
        )

    def calibrate_scale(self):
        if self.viewer.kind == "ifc":
            self._ifc_status()
            return
        px, ok = QInputDialog.getDouble(
            self, "کالیبراسیون مقیاس",
            "فاصله روی نقشه (پیکسل):", 1000.0, 0.001, 100000000.0, 3
        )
        if not ok:
            return
        meters, ok = QInputDialog.getDouble(
            self, "کالیبراسیون مقیاس",
            "فاصله واقعی (متر):", 10.0, 0.001, 100000000.0, 3
        )
        if not ok:
            return
        try:
            cal = self.session.calibrate(self.page, px, meters)
            self.scale_label.setText(
                f"مقیاس: {cal.meters_per_pixel:.6f} m/px"
            )
            self.status.setText(
                f"کالیبراسیون ثبت شد | {px:g} px = {meters:g} m"
            )
            self.undo.setEnabled(self.session.can_undo)
        except Exception as exc:
            QMessageBox.warning(self, "کالیبراسیون", str(exc))

    def add_note(self, x, y, page):
        text, ok = QInputDialog.getText(self, "یادداشت نقشه", "متن یادداشت:")
        if not ok or not text.strip():
            return
        try:
            self.session.add_note(text, x, y, page=page)
            self.status.setText(f"یادداشت در صفحه {page} ثبت شد.")
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "یادداشت", str(exc))

    def undo_session(self):
        if self.session.undo():
            self.redraw_current_page()
            self.refresh()

    def redo_session(self):
        if self.session.redo():
            self.redraw_current_page()
            self.refresh()

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            self.status.setText("یک متره را از جدول انتخاب کنید.")
            return
        item_id = self.table.item(row, 0)
        if not item_id:
            return
        if self.session.remove(item_id.text()):
            self.redraw_current_page()
            self.refresh()

    def redraw_current_page(self):
        if not self.viewer.path:
            return
        self.canvas.scene.clear()
        self.canvas._region_overlay = None
        self.canvas._selected_region_rect = None
        if self.viewer.kind == "pdf":
            data = self.engine.render(self.page, 150)
            pix = QPixmap()
            pix.loadFromData(QByteArray(data), "PNG")
            self.canvas.scene.addPixmap(pix)
            self.canvas.setSceneRect(0, 0, pix.width(), pix.height())
            for item in self.session.for_page(self.page):
                self.canvas._draw_measurement(item)
        elif self.viewer.kind == "ifc":
            self._render_ifc()
        else:
            self._render_cad()

    def export_takeoff_for_boq(self):
        """Export a reviewable, source-linked JSON handoff; never auto-approve BOQ rows."""
        if self.viewer.kind == "ifc":
            self._ifc_status()
            return
        if not self.session.items:
            QMessageBox.information(self, "خروجی متره", "هنوز هیچ ردیف متره‌ای برای خروجی ثبت نشده است.")
            return
        try:
            payload = build_takeoff_export_payload(self.session)
        except Exception as exc:
            QMessageBox.warning(self, "خروجی متره", str(exc))
            return
        answer = QMessageBox.question(
            self,
            "تأیید خروجی متره",
            f"{len(payload['items'])} ردیف متره با ارجاع نقشه آماده خروجی است.\n"
            "همه ردیف‌ها نیازمند بازبینی و تأیید جداگانه‌اند؛ این عملیات آن‌ها را مستقیماً در BOQ ثبت نمی‌کند.\n\n"
            "آیا فایل تبادل JSON ساخته شود؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        path = QFileDialog.getSaveFileName(
            self, "ذخیره خروجی متره برای BOQ", "drawing-takeoff.json",
            "StructuralPro Takeoff JSON (*.json)",
        )[0]
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.status.setText(f"خروجی قابل بازبینی ذخیره شد: {path}")
            QMessageBox.information(
                self, "خروجی متره",
                "فایل تبادل ذخیره شد. ردیف‌ها هنوز تأییدنشده‌اند و باید در سرویس پروژه/BOQ بازبینی و ثبت شوند.",
            )
        except OSError as exc:
            QMessageBox.critical(self, "خطای ذخیره خروجی", str(exc))

    def refresh(self):
        self.table.setRowCount(0)
        for i, item in enumerate(self.session.items):
            self.table.insertRow(i)
            values = [
                item.id, item.page, item.kind, item.label or item.takeoff_code,
                round(item.quantity, 4), item.unit, item.takeoff_code or "—",
                item.source_ref,
            ]
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))

        valid = self.session.validate()
        state = "🟢 معتبر" if valid["valid"] else "🟠 نیازمند بررسی"
        self.status.setText(
            f"{state} | متره‌ها: {len(self.session.items)} | "
            f"واگرد: {'فعال' if self.session.can_undo else '—'} | "
            f"تکرار: {'فعال' if self.session.can_redo else '—'}"
        )
        self.undo.setEnabled(self.session.can_undo)
        self.redo.setEnabled(self.session.can_redo)
