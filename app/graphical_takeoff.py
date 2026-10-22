"""Professional Windows drawing takeoff workspace for StructuralPro."""
from __future__ import annotations

from pathlib import Path
import json

from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, QByteArray, QVariantAnimation, QEasingCurve, QProcess, QTimer
from PySide6.QtGui import QPen, QBrush, QColor, QPixmap, QPolygonF, QFont, QTextOption, QPainterPath, QFontMetricsF, QTransform
from core.cad.persian_text_v1 import normalize_cad_text, is_rtl_cad_text, cad_text_height
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QComboBox,
    QLabel, QGraphicsView, QGraphicsScene, QGraphicsItem, QDialog, QTableWidget,
    QTableWidgetItem, QSpinBox, QFileDialog, QMessageBox, QFrame,
    QDoubleSpinBox, QInputDialog, QHeaderView, QFormLayout, QRubberBand, QGridLayout, QSplitter, QScrollArea, QMainWindow, QDockWidget, QApplication, QTreeWidget, QTreeWidgetItem
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
        self.on_polygon_finish = None
        self._polygon_preview = None
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
        self._measurement_overlay = None
        self._highlighted_item_id = None
        self._highlight_animation = None
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
        if self._polygon_preview is not None:
            if self._polygon_preview.scene() is self.scene:self.scene.removeItem(self._polygon_preview)
            self._polygon_preview=None
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
        if self.mode=='cad_select':
            point=event.position().toPoint();hits=[i for i in self.items(QRect(point.x()-4,point.y()-4,9,9)) if i.data(0) and i.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable]
            if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:self.scene.clearSelection()
            if hits:
                hits[0].setSelected(not hits[0].isSelected() if event.modifiers() & Qt.KeyboardModifier.ControlModifier else True)
                self._announce_tool('جزء CAD انتخاب شد: '+str(hits[0].data(0)))
            event.accept();return
        if event.button() == Qt.MouseButton.RightButton and self.mode in {"zoom_window", "region_select"}:
            self.cancel_interaction()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        if self.mode == "pan":
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
        if self.mode in {'polygon','polygon_opening','rotated'} and self.points:
            self.preview_polygon(self.mapToScene(event.position().toPoint()))
        if self._selection_origin is not None:
            self._rubber_band.setGeometry(
                QRect(self._selection_origin, event.position().toPoint()).normalized()
            )
            return
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mode=="cad_select":event.accept();return
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
                source=f"page:{self.session.current_page}:count:{len(self.session.items)+1}",
                point=self.points[-1]
            )
            self.points = []
            self._notify()
        except Exception as exc:
            QMessageBox.warning(self, "متره", str(exc))

    def preview_polygon(self, cursor=None):
        if self._polygon_preview is not None and self._polygon_preview.scene() is self.scene:
            self.scene.removeItem(self._polygon_preview)
        self._polygon_preview=None
        if not self.points:return
        path=QPainterPath(QPointF(self.points[0].x,self.points[0].y))
        for p in self.points[1:]:path.lineTo(p.x,p.y)
        if cursor is not None:path.lineTo(cursor)
        path.closeSubpath()
        self._polygon_preview=self.scene.addPath(path,QPen(QColor('#087f8c'),2),QBrush(QColor(10,180,180,45)))
        self._polygon_preview.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def finish(self):
        if self.read_only_model:
            return
        if self.mode in {'polygon','polygon_opening','rotated'} and self.on_polygon_finish:
            self.on_polygon_finish()
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
        if (item.cad_evidence or {}).get('metric_contract')=='cad_analytic_v1':return
        if item.kind == "length" and len(item.geometry) >= 2:
            pts = [QPointF(x, y) for x, y in item.geometry]
            for i in range(len(pts) - 1):
                self.scene.addLine(
                    pts[i].x(), pts[i].y(), pts[i + 1].x(), pts[i + 1].y(),
                    QPen(Qt.GlobalColor.blue, 3)
                )
        elif item.kind == "area" and len(item.geometry) >= 3:
            path=QPainterPath();path.addPolygon(QPolygonF([QPointF(float(x),float(y)) for x,y in item.geometry]))
            for hole in item.holes:path.addPolygon(QPolygonF([QPointF(float(x),float(y)) for x,y in hole]))
            path.setFillRule(Qt.FillRule.OddEvenFill)
            self.scene.addPath(path,QPen(Qt.GlobalColor.darkBlue,2),QBrush(Qt.GlobalColor.lightGray))

    def clear_measurement_highlight(self):
        if self._highlight_animation is not None:
            self._highlight_animation.stop()
            self._highlight_animation.deleteLater()
            self._highlight_animation = None
        if self._measurement_overlay is not None:
            self.scene.removeItem(self._measurement_overlay)
        self._measurement_overlay = None
        self._highlighted_item_id = None

    def highlight_measurement(self, item):
        self.clear_measurement_highlight()
        self._highlighted_item_id = item.id
        if not item.geometry:
            self._announce_tool('این ردیف مختصات صریح ندارد؛ محل عضو حدس زده نمی‌شود.')
            return
        path = QPainterPath()
        points = [QPointF(x, y) for x, y in item.geometry]
        path.moveTo(points[0])
        for point in points[1:]: path.lineTo(point)
        if item.kind == 'area':
            path.closeSubpath()
            for hole in item.holes:
                poly = QPolygonF([QPointF(x,y) for x,y in hole])
                path.addPolygon(poly)
            path.setFillRule(Qt.FillRule.OddEvenFill)
        overlay = self.scene.addPath(path, QPen(QColor('#db6500'), 3), QBrush(QColor(255,190,0,65)) if item.kind == 'area' else QBrush(Qt.BrushStyle.NoBrush))
        overlay.setAcceptedMouseButtons(Qt.MouseButton.NoButton); overlay.setZValue(1100)
        self._measurement_overlay = overlay
        self.ensureVisible(overlay, 30, 30)
        if QApplication.instance().property('structuralproAnimationsEnabled') is not False:
            animation = QVariantAnimation(self)
            animation.setDuration(300); animation.setStartValue(0.35); animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            animation.valueChanged.connect(lambda value: overlay.setOpacity(float(value)))
            self._highlight_animation = animation; animation.start()

    def _notify(self):
        if self.on_change:
            self.on_change()


class GraphicalTakeoffDialog(QDialog):
    def __init__(self, parent=None, pdf_path="", *, app_service=None, project_id=""):
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle("متره گرافیکی — نقشه‌محور")
        self.resize(1450, 920)
        self.cad_loading=False
        self._cad_job=None
        self.session = DrawingTakeoffSession(pdf_path)
        self.pdf_path = pdf_path
        self.app_service = app_service
        self.persisted_project_id = str(project_id or "").strip()
        self.persisted_session_id = None
        self.persisted_session_revision = None
        self.engine = None
        self.viewer = DrawingViewerModel()
        self.cad_document = None
        self._cad_scene_origin = None
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
        self.mode.addItems(["طول", "مساحت", "شمارش", "یادداشت", "چندضلعی دقیق", "ناحیه چرخیده", "بازشوی چندضلعی", "بازشوی مرزی و چندقسمتی"])
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
        self.pan = QPushButton("جابجایی نقشه")
        self.zoom_window = QPushButton("بزرگ‌نمایی ناحیه")
        self.select_region = QPushButton("انتخاب ناحیه")
        self.cancel_selection = QPushButton("لغو انتخاب/هایلایت")
        self.region_to_takeoff = QPushButton("ثبت ناحیه در متره")
        self.region_to_takeoff.setToolTip("فقط متره سطح عمومی؛ برای اجزای سقف از دکمه سقف تخصصی استفاده کنید")
        self.opening_button = QPushButton("کسر بازشو از سطح انتخابی")
        self.edit_button = QPushButton("ویرایش شرح متره")
        self.back_vertex = QPushButton('حذف رأس آخر')
        self.cancel_polygon = QPushButton('لغو چندضلعی')
        self.edit_vertices = QPushButton('ویرایش رأس‌های سطح')
        self.remove_opening=QPushButton('حذف بازشوی مستند')
        self.drawing_amendment_button=QPushButton('اصلاحیه برداشت قطعی')
        self.drawing_amendment_button.setEnabled(self.app_service is not None)
        self.drawing_amendment_button.setToolTip('اصل نشست حفظ می‌شود؛ درخواست مستند، بازبینی مستقل و قفل مالی الزامی است')
        self.geometry_components=QComboBox();self.geometry_components.addItem('تمام اجزای سطح',None)
        self.back_vertex.setToolTip('فقط رأس‌های انتخاب در حال ترسیم را اصلاح می‌کند')
        self.edit_vertices.setToolTip('مختصات مرجع صفحه به صورت JSON؛ تغییر مقدار فقط از هندسه معتبر')
        self.region_to_roof = QPushButton("سقف تخصصی از ناحیه")
        self.region_to_roof.setEnabled(self.app_service is not None)
        self.region_to_roof.setToolTip("انتخاب صریح نوع سقف؛ دیتایل مصالح از مساحت حدس زده نمی‌شود")
        self.polygon_floor = QLineEdit();self.polygon_floor.setPlaceholderText('شناسه طبقه صریح')
        self.polygon_member = QLineEdit();self.polygon_member.setPlaceholderText('شناسه عضو صریح')
        self.polygon_owner = QLineEdit();self.polygon_owner.setPlaceholderText('مالک مقدار و مرجع؛ برای BOQ الزامی')
        for field in (self.polygon_floor,self.polygon_member,self.polygon_owner):header.addWidget(field)
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
            self.zoom_out, self.zoom_in, self.fit, self.pan, self.zoom_window,
            self.select_region, self.cancel_selection, self.region_to_takeoff, self.region_to_roof, self.opening_button, self.edit_button, self.undo, self.redo,
            self.delete, self.finish, self.back_vertex, self.cancel_polygon, self.edit_vertices, self.remove_opening, self.geometry_components, self.drawing_amendment_button, self.project_id_input, self.save_session_button,
            self.load_session_button, self.commit_boq_button, self.export_boq
        ]):
            actions.addWidget(x, index // 6, index % 6)
        self.cad_layers=QComboBox();self.cad_layer_toggle=QPushButton('نمایش/پنهان لایه')
        self.cad_handle=QLineEdit();self.cad_handle.setPlaceholderText('Handle یا مسیر بلوک')
        self.cad_find=QPushButton('یافتن جزء CAD');self.cad_select=QPushButton('انتخاب اجزای CAD')
        self.cad_metric=QComboBox();self.cad_metric.addItem('طول / محیط معتبر','length');self.cad_metric.addItem('سطح بسته معتبر','area')
        self.cad_report=QPushButton('وضعیت اجزای CAD');self.cad_report.clicked.connect(self.show_cad_capabilities)
        self.cad_unit_button=QPushButton('واحد مستند CAD');self.cad_unit_button.clicked.connect(self.open_cad_unit_dialog)
        self.cad_cancel=QPushButton('لغو بارگذاری CAD');self.cad_cancel.clicked.connect(self.cancel_cad_loading)
        self.cad_measure=QPushButton('متره جزء CAD');self.cad_review=QPushButton('بازبینی متره CAD')
        self.cad_measure.setToolTip('خط، چندضلعی مستقیم، دایره و کمان تحلیلی یا جمع اجزای بلوک؛ بدون حدس مصالح')
        self._cad_items={};self._cad_handle_items={}
        cad_row=QHBoxLayout()
        for control in (self.cad_layers,self.cad_layer_toggle,self.cad_handle,self.cad_find,self.cad_select,self.cad_metric,self.cad_measure,self.cad_review,self.cad_cancel,self.cad_unit_button,self.cad_report):cad_row.addWidget(control)
        self.cad_controls=QWidget();self.cad_controls.setLayout(cad_row);self.cad_controls.hide();toolbar_rows.addWidget(self.cad_controls)
        self.cad_layer_toggle.clicked.connect(self.toggle_cad_layer);self.cad_find.clicked.connect(self.find_cad_handle)
        self.cad_select.clicked.connect(lambda:self.canvas.set_mode('cad_select'))
        self.cad_measure.clicked.connect(self.measure_cad_selection);self.cad_review.clicked.connect(self.review_cad_selection)
        self.ifc_revision=QLineEdit();self.ifc_revision.setPlaceholderText('Revision صریح IFC')
        self.ifc_inspect_button=QPushButton('طبقات، هویت و کمیت IFC')
        self.ifc_inspect_button.clicked.connect(self.open_ifc_inspector)
        ifc_row=QHBoxLayout();ifc_row.addWidget(self.ifc_revision);ifc_row.addWidget(self.ifc_inspect_button)
        self.ifc_controls=QWidget();self.ifc_controls.setLayout(ifc_row);self.ifc_controls.hide();toolbar_rows.addWidget(self.ifc_controls)
        toolbar_rows.addWidget(self.source_label)
        root.addWidget(toolbar)

        self.canvas = TakeoffCanvas(self.session, self.refresh, self.add_note)
        self.canvas.setFrameShape(QFrame.Shape.StyledPanel)
        self.beam_detail_panel = None
        if self.app_service is not None:
            # Keep the drawing visible while the engineer reviews beam details.
            from app.beam_detail_panel import BeamDetailPanel
            self.beam_detail_panel = BeamDetailPanel(
                self.app_service, lambda: self.project_id_input.text(),
                self.beam_drawing_context, self
            )
            self.drawing_workspace = QMainWindow(self)
            self.drawing_workspace.setWindowFlags(Qt.WindowType.Widget)
            self.drawing_workspace.setCentralWidget(self.canvas)
            self.beam_dock = QDockWidget('دیتایل تیر؛ زمینه انتخاب‌شده از نقشه', self.drawing_workspace)
            self.beam_dock.setObjectName('BeamDetailDock')
            self.beam_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
            beam_scroll = QScrollArea(); beam_scroll.setWidgetResizable(True)
            beam_scroll.setMinimumWidth(380); beam_scroll.setWidget(self.beam_detail_panel)
            self.beam_dock.setWidget(beam_scroll)
            self.drawing_workspace.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.beam_dock)
            self.panel_toggle = QPushButton('پنل دیتایل تیر'); self.panel_toggle.setCheckable(True)
            self.panel_float = QPushButton('شناور / اتصال پنل تیر')
            actions.addWidget(self.panel_toggle, 4, 0, 1, 2)
            actions.addWidget(self.panel_float, 4, 2, 1, 2)
            self.panel_toggle.toggled.connect(self.beam_dock.setVisible)
            def sync_panel(visible):
                self.panel_toggle.blockSignals(True); self.panel_toggle.setChecked(visible); self.panel_toggle.blockSignals(False)
            self.beam_dock.visibilityChanged.connect(sync_panel)
            def float_panel():
                self.beam_dock.show(); self.beam_dock.setFloating(not self.beam_dock.isFloating())
            self.panel_float.clicked.connect(float_panel)
            self.beam_dock.hide()
            root.addWidget(self.drawing_workspace, 5)
        else:
            root.addWidget(self.canvas, 5)

        table_title = QLabel("متره‌های ثبت‌شده — قابل بازبینی و اتصال به BOQ")
        table_title.setObjectName("SectionTitle")
        root.addWidget(table_title)

        self.table = QTableWidget(0, 8)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.highlight_selected_measurement)
        self.table.setHorizontalHeaderLabels([
            "شناسه", "صفحه", "نوع", "شرح", "مقدار", "واحد", "کد BOQ", "منبع"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 2)

        self.status = QLabel("برای شروع، نقشه را باز کنید و مقیاس را کالیبره کنید.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.canvas.on_tool_status = self.status.setText

        self.canvas.on_polygon_finish = self.finish_polygon
        self.back_vertex.clicked.connect(self.remove_pending_vertex)
        self.cancel_polygon.clicked.connect(self.cancel_pending_polygon)
        self.edit_vertices.clicked.connect(self.edit_polygon_vertices)
        self.remove_opening.clicked.connect(self.remove_selected_opening)
        self.drawing_amendment_button.clicked.connect(self.open_drawing_correction)
        self.geometry_components.currentIndexChanged.connect(self.highlight_component)
        self.mode.currentTextChanged.connect(self.apply_tool)
        self.calibrate.clicked.connect(self.calibrate_scale)
        self.open_pdf.clicked.connect(self.select_drawing)
        self.prev.clicked.connect(lambda: self.load_page(self.page - 1))
        self.next.clicked.connect(lambda: self.load_page(self.page + 1))
        self.page_no.valueChanged.connect(self.load_page)
        self.zoom_in.clicked.connect(lambda: self.canvas.scale_view(1.25))
        self.zoom_out.clicked.connect(lambda: self.canvas.scale_view(0.8))
        self.fit.clicked.connect(self.reset_zoom)
        self.pan.clicked.connect(
            lambda: self._activate_view_tool("pan", "برای جابجایی نقشه، ماوس را نگه دارید و بکشید؛ متره تغییر نمی‌کند.")
        )
        self.zoom_window.clicked.connect(
            lambda: self._activate_view_tool("zoom_window", "مستطیل ناحیه بزرگ‌نمایی را با ماوس بکش؛ Esc یا کلیک راست لغو می‌کند.")
        )
        self.select_region.clicked.connect(
            lambda: self._activate_view_tool("region_select", "مستطیل ناحیه موردنظر را با ماوس بکش؛ Esc یا کلیک راست لغو می‌کند.")
        )
        self.cancel_selection.clicked.connect(lambda: self.canvas.cancel_interaction())
        self.region_to_takeoff.clicked.connect(self.register_selected_region)
        self.region_to_roof.clicked.connect(self.open_region_roof)
        self.opening_button.clicked.connect(self.apply_opening)
        self.edit_button.clicked.connect(self.edit_measurement)
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
                self.open_cad_async(pdf_path) if Path(pdf_path).suffix.lower()=='.ifc' or (Path(pdf_path).suffix.lower() in {'.dxf','.dwg'} and Path(pdf_path).stat().st_size>512_000) else self.open_drawing(pdf_path)
            except Exception as exc:
                QMessageBox.warning(self, "نقشه", "فایل برای نمایش گرافیکی باز نشد: " + str(exc))

    def _cad_busy(self, busy):
        self.cad_loading=busy
        if busy:
            self._cad_enabled={c:c.isEnabled() for c in self.findChildren(QWidget) if isinstance(c,(QPushButton,QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox,QTableWidget))}
            for c in self._cad_enabled:c.setEnabled(c in (self.open_pdf,self.cad_cancel))
            self.canvas.setEnabled(False);self.cad_controls.show()
        else:
            for c,v in getattr(self,'_cad_enabled',{}).items():c.setEnabled(v)
            self.canvas.setEnabled(True)

    def cancel_cad_loading(self):
        job=self._cad_job
        if not job:return
        self._cad_job=None;p=job['process'];p.blockSignals(True)
        if 'old_ifc_items' in job:self._ifc_handle_items=job['old_ifc_items']
        if p.state()!=QProcess.ProcessState.NotRunning:p.kill();p.waitForFinished(1000)
        if job.get('old'):
            self.cad_document,self.canvas.scene,self._cad_items,self._cad_handle_items,self._cad_scene_origin=job['old'];job['scene'].deleteLater()
        self.cad_layers.clear()
        for label,value in job['layers']:self.cad_layers.addItem(label,value)
        self.cad_layers.setCurrentIndex(job['layer_index'])
        if job.get('stream'):job['stream'].close()
        job['temp'].cleanup();p.deleteLater();self._cad_busy(False);self.cad_controls.setVisible(self.viewer.kind=='cad');self.status.setText('بارگذاری CAD لغو شد؛ نقشه و متره قبلی محفوظ است')

    def open_cad_async(self,path):
        import tempfile,sys
        self.cancel_cad_loading()
        if self.session.items and str(path)!=self.session.drawing_source:
            if QMessageBox.question(self,'تغییر نقشه','نشست دارای متره است؛ پیش از تغییر، ذخیره را بررسی کنید. ادامه؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        p=QProcess(self);temp=tempfile.TemporaryDirectory(prefix='structuralpro-cad-')
        job={'process':p,'temp':temp,'result':str(Path(temp.name)/'result'),'old':None,'layers':[(self.cad_layers.itemText(i),self.cad_layers.itemData(i)) for i in range(self.cad_layers.count())],'layer_index':self.cad_layers.currentIndex()}
        self._cad_job=job;self._cad_busy(True);self.status.setText('در حال تحلیل CAD در پردازش مستقل؛ لغو فعال است')
        def failed(message):
            if self._cad_job is not job:return
            self.cancel_cad_loading();self.status.setText('خطای بارگذاری CAD؛ نقشه قبلی محفوظ است: '+message)
        def parsed(code,status):
            if self._cad_job is not job:return
            if code!=0:failed(bytes(p.readAllStandardError()).decode('utf-8','replace')[-1500:]);return
            try:
                import pickle
                # Parent-created private result, produced only by our parser.
                job['stream']=open(job['result'],'rb');job['document']=pickle.load(job['stream'])
                QTimer.singleShot(0,receive)
            except Exception as exc:failed(str(exc))
        def receive():
            if self._cad_job is not job:return
            try:
                import pickle
                doc=job['document']
                if len(doc.entities)<doc._entity_count:
                    chunk=pickle.load(job['stream'])
                    if not isinstance(chunk,list) or not chunk or len(doc.entities)+len(chunk)>doc._entity_count:raise ValueError('بسته مدل CAD نامعتبر است')
                    doc.entities.extend(chunk);self.status.setText(f'دریافت مدل CAD: {len(doc.entities)} از {doc._entity_count} جزء؛ متره مسدود است');QTimer.singleShot(0,receive);return
                job['stream'].close();job['stream']=None
                job['old']=(self.cad_document,self.canvas.scene,self._cad_items,self._cad_handle_items,self._cad_scene_origin)
                scene=QGraphicsScene(self);scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex);job['scene']=scene
                self.canvas.scene=scene
                if hasattr(doc,'_ifc_header'):
                    from core.bim.ifc import IFCDisplayDocument
                    source,sha,omitted=doc._ifc_header
                    job['ifc_document']=IFCDisplayDocument(source,sha,tuple(doc.entities),tuple(omitted))
                    job['old_ifc_items']=getattr(self,'_ifc_handle_items',{})
                    job['steps']=self._render_ifc_steps(job['ifc_document'])
                else:
                    self.cad_document=doc;job['steps']=self._render_cad_steps()
                QTimer.singleShot(0,batch)
            except Exception as exc:failed(str(exc))
        def batch():
            if self._cad_job is not job:return
            try:
                n=next(job['steps']);self.status.setText(f"ساخت نمایش نقشه: {n} از {job['document']._entity_count} جزء؛ متره مسدود است");QTimer.singleShot(0,batch)
            except StopIteration:
                if self.engine is not None:self.engine.close()
                self.engine=None;self.pdf_path=str(path)
                if self.session.drawing_source!=str(path):
                    # The parser already hashed the full file off the GUI thread.
                    # Re-reading a large CAD/IFC here creates an unbounded final
                    # I/O/allocation pause. Financial commit rechecks the bytes.
                    self.session=DrawingTakeoffSession()
                    self.session.drawing_source=str(path)
                    self.session.source_sha256=job['ifc_document'].source_sha256 if 'ifc_document' in job else self.cad_document.source_sha256
                    self.canvas.session=self.session;self.persisted_session_id=None;self.persisted_session_revision=None
                if 'ifc_document' in job:
                    self.viewer.path=Path(path);self.viewer.kind='ifc';self.viewer.page_count=1;self.viewer.current_page=1
                    self.viewer.ifc_document=job['ifc_document'];self.viewer.cad_document=None;self.cad_document=None
                    self.page=1;self.canvas.read_only_model=True;self.canvas.setScene(job['scene']);job['old'][1].deleteLater()
                    self._cad_job=None;temp.cleanup();p.deleteLater();self._cad_busy(False)
                    self.ifc_controls.show();self.cad_controls.hide()
                    for control in (self.mode,self.calibrate,self.region_to_takeoff,self.finish,self.region_to_roof,self.commit_boq_button,self.export_boq):control.setEnabled(False)
                    self.canvas.set_mode('pan');self.scale_label.setText('نمای مدل؛ متره از تصویر غیرفعال است')
                    self.source_label.setText('منبع IFC: '+Path(path).name);self.refresh();self.reset_zoom();self._ifc_status();return
                self.viewer.ifc_document=None;self.ifc_controls.hide()
                self.viewer.path=Path(path);self.viewer.kind='cad';self.viewer.page_count=1;self.viewer.current_page=1;self.viewer.cad_document=self.cad_document
                self.page=1;self.canvas.read_only_model=False;self.canvas.setScene(job['scene']);job['old'][1].deleteLater()
                self._cad_job=None;temp.cleanup();p.deleteLater();self._cad_busy(False);self.source_label.setText('منبع CAD: '+Path(path).name);self.refresh();self.reset_zoom();self.status.setText(f'CAD آماده است؛ {len(self.cad_document.entities)} جزء حفظ شد؛ واحد: {self.cad_document.units}')
            except Exception as exc:failed(str(exc))
        p.finished.connect(parsed);p.errorOccurred.connect(lambda error:failed(p.errorString()));p.setWorkingDirectory(str(Path(__file__).resolve().parents[1]));p.start(sys.executable,['-m','core.drawings.cad_import_worker',str(Path(path).resolve()),job['result']])

    def closeEvent(self,event):
        self.cancel_cad_loading()
        if self.engine is not None:self.engine.close()
        super().closeEvent(event)

    def show_cad_capabilities(self):
        if self.cad_loading or not self.cad_document:return
        dialog=QDialog(self);dialog.setWindowTitle('قرارداد اجزای CAD و هشدار فونت');dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(900,500)
        layout=QVBoxLayout(dialog);layout.addWidget(QLabel('نوع پشتیبانی‌نشده، واحد نامعلوم یا مدرک ناقص مجوز BOQ ندارد؛ فونت جایگزین ممکن است چیدمان را تغییر دهد'))
        shown=self.cad_document.entities[:200]
        layout.addWidget(QLabel(f'این گزارش نخستین {len(shown)} جزء از {len(self.cad_document.entities)} را نشان می‌دهد؛ همه اجزا در مدل و جست‌وجوی Handle محفوظ‌اند'))
        table=QTableWidget(len(shown),3);table.setHorizontalHeaderLabels(['نوع جزء','Handle و لایه','وضعیت و علت'])
        for row,e in enumerate(shown):
            reason=e.data.get('unsupported_measurement') or e.data.get('font_notice') or 'هندسه قابل بررسی؛ ثبت فقط پس از مدرک و بازبینی مستقل'
            for col,value in enumerate((e.entity_type,str(e.handle)+' | '+e.layer,reason)):table.setItem(row,col,QTableWidgetItem(value))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);layout.addWidget(table);dialog.exec()

    def open_cad_unit_dialog(self):
        if self.cad_loading or not self.cad_document:return
        dialog=QDialog(self);dialog.setWindowTitle('واحد مستند CAD — مدرک و بازبینی مستقل');dialog.setLayoutDirection(Qt.RightToLeft)
        form=QFormLayout(dialog);form.addRow(QLabel('واحد فایل: '+self.cad_document.units+'؛ انتخاب دلخواه واحد مجوز مالی نیست'))
        path=QLineEdit();path.setObjectName('cad_unit_document');browse=QPushButton('انتخاب مدرک JSON مستقل واحد');summary=QLabel();summary.setWordWrap(True);apply=QPushButton('بررسی مدرک و تأیید صریح واحد');apply.setObjectName('cad_unit_apply')
        form.addRow('مسیر مدرک',path);form.addRow(browse);form.addRow(summary);form.addRow(apply)
        browse.clicked.connect(lambda:path.setText(QFileDialog.getOpenFileName(dialog,'مدرک مستقل واحد','','JSON (*.json)')[0]))
        def accept():
            try:
                if self.session.items:raise ValueError('متره قبلی نباید بازتفسیر شود؛ نشست یا اصلاحیه مستقل لازم است')
                import hashlib
                from core.drawings.dwg_takeoff import apply_documented_units
                p=Path(path.text());e={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()};doc=apply_documented_units(self.cad_document,e);proof=json.loads(p.read_text(encoding='utf-8-sig'))
                labels={'unit':'واحد پیشنهادی','reference_handle':'شناسه هندسه مرجع','cad_length':'طول مرجع در CAD','real_length_m':'طول معلوم واقعی (متر)','author':'ثبت‌کننده','reviewer':'بازبین مستقل','reference':'نوع و مرجع مدرک','source_sha256':'SHA-256 منبع'}
                summary.setText('\n'.join(label+': '+str(proof.get(k,'')) for k,label in labels.items())+'\nSHA-256 مدرک: '+e['sha256'])
                if QMessageBox.question(dialog,'تأیید واحد',summary.text()+'\nواحد مستند اعمال شود؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
                self.cad_document=self.session.set_cad_units(self.cad_document,e);self.viewer.cad_document=self.cad_document;self.load_page(1);dialog.accept()
            except Exception as exc:summary.setText('واحد اعمال نشد: '+str(exc))
        apply.clicked.connect(accept);dialog.exec()

    def beam_drawing_context(self):
        """Context link only: a selected rectangle does not imply a parsed beam detail."""
        rect = self.canvas._selected_region_rect
        region = None
        if rect is not None and rect.isValid() and rect.width() > 0 and rect.height() > 0:
            region = (rect.left(), rect.top(), rect.width(), rect.height())
        return {
            "path": str(self.viewer.path) if self.viewer.path else "",
            "page": self.page, "region": region,
            "cad_document": self.cad_document if self.viewer.kind == "cad" else None,
            "cad_scene_origin": self._cad_scene_origin if self.viewer.kind == "cad" else None,
            "pdf_engine": self.engine if self.viewer.kind == "pdf" else None,
        }

    def save_session_to_project(self):
        if self.cad_loading:self.status.setText('بارگذاری CAD هنوز کامل نشده است؛ متره و BOQ مسدودند');return False
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
        if self.cad_loading:return
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
            if restored.cad_unit_evidence:
                from core.drawings.dwg_takeoff import apply_documented_units
                new_viewer.cad_document=apply_documented_units(new_viewer.cad_document,restored.cad_unit_evidence)
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
        if self.cad_loading:self.status.setText('بارگذاری CAD هنوز کامل نشده است؛ متره و BOQ مسدودند');return False
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
            self.open_cad_async(path) if Path(path).suffix.lower() in {'.dwg','.dxf','.ifc'} else self.open_drawing(path)
        except Exception as exc:
            QMessageBox.critical(self, "خطای نقشه", str(exc))

    def select_pdf(self):
        self.select_drawing()

    def open_drawing(self, path):
        self.cancel_cad_loading()
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
        self._cad_scene_origin = None  # Never reuse a prior drawing's CAD coordinate transform.
        self.engine = new_engine
        self.load_page(1)

    def load_page(self, page):
        if self.cad_loading:return
        self.ifc_controls.setVisible(self.viewer.kind=="ifc")
        self.cad_controls.setVisible(self.viewer.kind=="cad")
        if not self.viewer.path or page < 1 or page > max(1, self.viewer.page_count):
            return
        try:
            self.page = int(page)
            self.session.set_page(self.page)
            self.page_no.blockSignals(True)
            self.page_no.setValue(self.page)
            self.page_no.blockSignals(False)

            self.canvas.clear_measurement_highlight()
            self.canvas._polygon_preview = None
            self.canvas.scene.clear()
            self.canvas._region_overlay = None
            self.canvas._selected_region_rect = None
            self._cad_scene_origin = None
            self.canvas.points = []
            model_view = self.viewer.kind == "ifc"
            calibration = self.session.calibration
            self.scale_label.setText(
                "نمای مدل؛ متره از تصویر غیرفعال است" if model_view else
                (f"مقیاس: {calibration.meters_per_pixel} متر بر واحد نمایش"
                 if calibration else "مقیاس: هنوز کالیبره نشده")
            )
            self.canvas.read_only_model = model_view
            for control in (self.mode, self.calibrate, self.region_to_takeoff, self.finish):
                control.setEnabled(not model_view)
            self.region_to_roof.setEnabled(self.viewer.kind=="pdf" and self.app_service is not None)
            self.commit_boq_button.setEnabled(not model_view and self.app_service is not None)
            self.export_boq.setEnabled(not model_view)
            self.canvas.set_mode("pan" if model_view else {
                "طول": "length", "مساحت": "area", "شمارش": "count", "یادداشت": "note",
            "چندضلعی دقیق":"polygon", "ناحیه چرخیده":"rotated", "بازشوی چندضلعی":"polygon_opening", "بازشوی مرزی و چندقسمتی":"polygon_opening"
            }[self.mode.currentText()])
            if self.viewer.kind == "pdf":
                self._render_pdf_background()
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

    def _render_pdf_background(self):
        """Lower bitmap resolution for large sheets; retain the 150-DPI scene grid.

        This is a display transform, never an engineering scale/calibration.
        Existing sessions and measured coordinates keep their original meaning.
        """
        import math
        page=self.engine.pages()[self.page-1]
        dpi=next((d for d in (150,100,72,36)
                  if math.ceil(page.width_pt*d/72)*math.ceil(page.height_pt*d/72)<=40_000_000),None)
        if dpi is None:raise ValueError("ابعاد صفحه حتی در وضوح پایین از بودجه حافظه نمایش بیشتر است")
        data=self.engine.render(self.page,dpi);pix=QPixmap()
        if not pix.loadFromData(QByteArray(data),"PNG"):raise RuntimeError("رندر PDF ناموفق بود")
        image=self.canvas.scene.addPixmap(pix);image.setScale(150/dpi)
        self.canvas.setSceneRect(0,0,math.ceil(page.width_pt*150/72),math.ceil(page.height_pt*150/72))
        self.display_dpi=dpi
        self.source_label.setText(f"منبع: {self.viewer.source_name} | PDF | وضوح نمایش {dpi} DPI؛ مختصات ثابت مرجع ۱۵۰ DPI")

    def measure_cad_selection(self):
        if self.cad_loading:self.status.setText('بارگذاری CAD هنوز کامل نشده است؛ متره و BOQ مسدودند');return False
        selected=self.canvas.scene.selectedItems()
        root_handle=getattr(self,'_selected_cad_root',None)
        if root_handle:
            expected={h for h in self._cad_handle_items if h.startswith(root_handle+'/') or h.startswith(root_handle+'@')}
            if {str(i.data(0)) for i in selected}!=expected:root_handle=None
        if len(selected)!=1 and not root_handle:
            self.status.setText('یک جزء CAD را انتخاب کنید؛ هر عضو و مالکیت مستقل ثبت می‌شود');return
        values=[]
        for prompt in ('کد عملیات متره','سازنده برداشت','مرجع مستقل هندسه و مالکیت'):
            value,ok=QInputDialog.getText(self,'متره جزء CAD',prompt)
            if not ok or not value.strip():return
            values.append(value.strip())
        try:
            item=self.session.add_cad_entity(self.cad_document,root_handle or str(selected[0].data(0)),self.cad_metric.currentData(),takeoff_code=values[0],created_by=values[1],reference=values[2],floor_id=self.polygon_floor.text().strip(),member_id=self.polygon_member.text().strip(),quantity_owner=self.polygon_owner.text().strip(),scene_origin=self._cad_scene_origin)
            self.refresh();self.table.selectRow(len(self.session.items)-1)
            self.status.setText('پیش‌نویس CAD ثبت شد؛ بازبینی مستقل پیش از BOQ لازم است | '+item.id)
        except Exception as exc:QMessageBox.warning(self,'متره CAD مسدود شد',str(exc))

    def review_cad_selection(self):
        if self.cad_loading:self.status.setText('بارگذاری CAD هنوز کامل نشده است؛ متره و BOQ مسدودند');return False
        row=self.table.currentRow()
        if row<0:self.status.setText('ابتدا یک ردیف متره CAD انتخاب کنید');return
        reviewer,ok=QInputDialog.getText(self,'بازبینی CAD','نام بازبین مستقل')
        if not ok:return
        note,ok=QInputDialog.getText(self,'بازبینی CAD','یادداشت کنترل مقدار، واحد و مالکیت')
        if not ok:return
        try:
            self.session.review_cad_entity(self.table.item(row,0).text(),reviewer=reviewer,note=note)
            self.status.setText('بازبینی مستقل CAD ثبت شد؛ ذخیره و کنترل نسخه برای انتقال الزامی است')
        except Exception as exc:QMessageBox.warning(self,'بازبینی CAD مسدود شد',str(exc))

    def toggle_cad_layer(self):
        layer=self.cad_layers.currentData();items=self._cad_items.get(layer,[])
        visible=not any(item.isVisible() for item in items)
        for item in items:item.setVisible(visible)
        self.status.setText(('لایه نمایش داده شد: ' if visible else 'لایه پنهان شد: ')+str(layer)+'؛ وضعیت نمایش مجوز متره نیست')

    def find_cad_handle(self):
        key=self.cad_handle.text().strip();item=self._cad_handle_items.get(key)
        self.canvas.scene.clearSelection()
        self._selected_cad_root=None
        if item is None:
            children=[item for handle,item in self._cad_handle_items.items() if handle.startswith(key+'/') or handle.startswith(key+'@')]
            if not children:self.status.setText('جزء قابل نمایش یافت نشد؛ XREF حل‌نشده یا نوع پشتیبانی‌نشده مجوز متره ندارد');return
            for child in children:child.setVisible(True);child.setSelected(True)
            self._selected_cad_root=key;self.canvas.centerOn(children[0]);self.status.setText('بلوک انتخاب شد: '+key+'؛ اجزا برای جمع کنترل‌شده بازبینی شوند');return
        item.setVisible(True);item.setSelected(True);self.canvas.centerOn(item)
        self.status.setText('جزء CAD: '+key+' | '+str(item.data(1)))

    def _render_cad(self):
        for _ in self._render_cad_steps():pass

    def _render_cad_steps(self):
        doc = self.cad_document
        if doc is None:
            raise RuntimeError("سند CAD برای نمایش آماده نیست.")
        self.cad_controls.show();self._cad_items={};self._cad_handle_items={};self.cad_layers.clear()
        from collections import Counter
        for layer,count in sorted((doc._layer_counts if hasattr(doc,'_layer_counts') else Counter(e.layer for e in doc.entities)).items()):self.cad_layers.addItem(layer+" | "+str(count),layer)
        coords=[]
        for entity in ([] if hasattr(doc,'_render_bounds') else doc.entities):
            data=entity.data
            coords.extend((float(x),float(y)) for x,y in data.get("display_points", data.get("points",[])))
            if entity.entity_type == "CIRCLE" and data.get("center") and data.get("radius"):
                x, y = data["center"]; r = data["radius"]
                coords.extend([(x-r, y-r), (x+r, y+r)])
            for key in ("start","end","center","insert"):
                if key in data and data[key] is not None:
                    coords.append((float(data[key][0]),float(data[key][1])))
        if not coords and not hasattr(doc,'_render_bounds'):
            self.canvas.scene.addText("CAD فاقد هندسه قابل نمایش است.")
            self.canvas.setSceneRect(0,0,1000,700)
            return
        min_x,max_x,min_y,max_y=doc._render_bounds if hasattr(doc,'_render_bounds') else (min(x for x,_ in coords),max(x for x,_ in coords),min(y for _,y in coords),max(y for _,y in coords))
        margin=max(max_x-min_x,max_y-min_y,1.0)*0.05
        min_x-=margin; max_x+=margin; min_y-=margin; max_y+=margin
        # Evidence matching must use the same model -> scene transform as rendering.
        self._cad_scene_origin = (min_x, max_y)
        def sx(x): return x-min_x
        def sy(y): return max_y-y
        pen=QPen(Qt.GlobalColor.darkBlue,0)
        render_bounds=QRectF(0,0,max_x-min_x,max_y-min_y)
        unsupported_count=0
        for entity_index,entity in enumerate(doc.entities):
            if entity_index%128==0:yield entity_index
            item=None
            d=entity.data
            unsupported_count+=bool(d.get('unsupported_measurement'))
            if entity.entity_type=="LINE" and d.get("start") and d.get("end"):
                a,b=d["start"],d["end"]
                item=self.canvas.scene.addLine(sx(a[0]),sy(a[1]),sx(b[0]),sy(b[1]),pen)
            elif entity.entity_type in {"LWPOLYLINE","POLYLINE", "ARC"} and len(d.get("display_points", d.get("points",[])))>=2:
                pts=[QPointF(sx(x),sy(y)) for x,y in d.get("display_points", d.get("points",[]))]
                path = QPainterPath(pts[0])
                for point in pts[1:]:
                    path.lineTo(point)
                if d.get("closed", False):
                    path.closeSubpath()
                item=self.canvas.scene.addPath(path, pen)
            elif entity.entity_type=="CIRCLE" and d.get("center") and d.get("radius"):
                x,y=d["center"]; r=float(d["radius"])
                item=self.canvas.scene.addEllipse(sx(x-r),sy(y+r),2*r,2*r,pen)
            elif entity.entity_type in {"TEXT","MTEXT","DIMENSION"} and d.get("text"):
                text = normalize_cad_text(d["text"])
                if not text:
                    continue
                pos = d.get("insert", d.get("start", (0, 0)))
                height = cad_text_height(d)
                font = QFont("Tahoma")
                font.setPixelSize(100)
                item = self.canvas.scene.addText(text, font)
                item.setDefaultTextColor(QColor(20, 35, 70))
                option = item.document().defaultTextOption()
                option.setTextDirection(
                    Qt.LayoutDirection.RightToLeft
                    if is_rtl_cad_text(text)
                    else Qt.LayoutDirection.LeftToRight
                )
                item.document().setDefaultTextOption(option)
                item.document().setDocumentMargin(0)
                # CAD insertion points usually refer to the text baseline;
                # Qt graphics text items are positioned from their top edge.
                metrics=QFontMetricsF(font);scale=height/max(metrics.capHeight(),1)
                if entity.entity_type=='MTEXT':
                    if d.get('text_width',0)>0:item.setTextWidth(d['text_width']/scale)
                    rect=item.boundingRect();anchor=max(1,min(9,int(d.get('attachment_point',1))))-1
                    ax=rect.left()+rect.width()*(anchor%3)/2;ay=rect.top()+rect.height()*(anchor//3)/2
                else:ax=0;ay=metrics.ascent()
                item.setTransform(QTransform().rotate(-float(d.get("rotation",0))).scale(scale,scale).translate(-ax,-ay))
                item.setPos(sx(pos[0]),sy(pos[1]))
            if item is not None:
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,True)
                item.setData(0,entity.handle);item.setData(1,entity.entity_type+' | '+entity.layer+' | '+doc.units)
                item.setToolTip(str(entity.handle)+' | '+entity.entity_type+' | '+entity.layer+'‏ | '+doc.units+'\n'+str(d.get('unsupported_measurement') or ('طول: '+str(d.get('length','—'))+'؛ سطح: '+str(d.get('area','—'))))+'\n'+str(d.get('font_notice',''))+' '+str(d.get('font_name','')))
                item.setVisible(d.get('layer_visible',True));self._cad_items.setdefault(entity.layer,[]).append(item);self._cad_handle_items[entity.handle]=item
                render_bounds=render_bounds.united(item.sceneBoundingRect())
        yield len(doc.entities)  # Yield before publishing the completed scene.
        self.canvas.setSceneRect(render_bounds)
        self.status.setText(f"🟢 CAD نمایش داده شد | {len(doc.entities)} المان | لایه‌ها: {len(doc.layers)} | واحد: {doc.units} | اجزای فاقد قرارداد متره: {unsupported_count} | هشدار: {len(doc.warnings)}")

    def _render_ifc_steps(self,doc):
        """One selectable path per real mesh; all source triangles retained.

        Grouping display primitives avoids twelve or more Qt objects per solid.
        It never computes or simplifies an engineering quantity.
        """
        self._ifc_handle_items={};self._ifc_selected_global_id=None
        for n,mesh in enumerate(doc.meshes,1):
            path=QPainterPath()
            for triangle in mesh.triangles:
                points=[QPointF((x-y)*0.866025403784,(x+y)*.5-z) for x,y,z in (mesh.vertices[i] for i in triangle)]
                path.addPolygon(QPolygonF(points));path.closeSubpath()
            path.setFillRule(Qt.WindingFill)
            item=self.canvas.scene.addPath(path,QPen(QColor(42,75,110),0),QBrush(QColor(155,190,215)))
            item.setData(0,mesh.global_id);item.setFlag(QGraphicsItem.ItemIsSelectable,True)
            item.setToolTip(mesh.name+'\nGlobalId: '+mesh.global_id+'\nSHA-256: '+doc.source_sha256)
            self._ifc_handle_items[mesh.global_id]=[item]
            if n%32==0:yield n
        self.canvas.scene.selectionChanged.connect(self._ifc_scene_selection)
        self.canvas.setSceneRect(self.canvas.scene.itemsBoundingRect())
        yield len(doc.meshes)

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
        self._ifc_handle_items={}
        self._ifc_selected_global_id=None
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
            item.setData(0,mesh.global_id)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,True)
            item.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
            self._ifc_handle_items.setdefault(mesh.global_id,[]).append(item)
        self.canvas.scene.selectionChanged.connect(self._ifc_scene_selection)
        bounds = self.canvas.scene.itemsBoundingRect()
        margin = max(bounds.width(), bounds.height(), 1.0) * 0.05
        self.canvas.setSceneRect(bounds.adjusted(-margin, -margin, margin, margin))
        self._ifc_status()

    def _ifc_scene_selection(self):
        if self.viewer.kind!='ifc':return
        selected=self.canvas.scene.selectedItems()
        if selected:self._ifc_selected_global_id=selected[0].data(0)

    def highlight_ifc_member(self,gid):
        if self.viewer.kind!='ifc':return
        self.canvas.scene.blockSignals(True)
        try:
            self.canvas.scene.clearSelection()
            for key,items in self._ifc_handle_items.items():
                for item in items:
                    item.setSelected(key==gid)
                    item.setBrush(QBrush(QColor(245,165,55) if key==gid else QColor(155,190,215)))
            self._ifc_selected_global_id=gid
        finally:self.canvas.scene.blockSignals(False)

    def open_ifc_inspector(self):
        if self.viewer.kind!='ifc' or self.cad_loading:return
        try:
            from core.drawings.bim_adapter import BIMAdapter
            doc=BIMAdapter().read_document(self.viewer.path,revision=self.ifc_revision.text())
            if doc['source_sha256']!=self.viewer.ifc_document.source_sha256:
                raise ValueError('مدل پس از نمایش تغییر کرده است؛ دوباره باز کنید')
        except Exception as exc:
            self.status.setText('بررسی IFC انجام نشد: '+str(exc));return
        dialog=QDialog(self);self._ifc_inspector=dialog
        dialog.setAttribute(Qt.WA_DeleteOnClose);dialog.setWindowTitle('بررسی مهندسی IFC — پیشنهاد هویت، بدون مجوز مالی')
        dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1000,700)
        layout=QVBoxLayout(dialog)
        title=QLabel(doc['schema']+' | '+doc['parser']+' | '+doc['project_name']+'\nSHA-256: '+doc['source_sha256']+'\nضرایب SI: '+str(doc['unit_factors_si']))
        title.setTextInteractionFlags(Qt.TextSelectableByMouse);title.setWordWrap(True);layout.addWidget(title)
        search=QLineEdit();search.setObjectName('ifc_search');search.setPlaceholderText('جست‌وجوی دقیق GlobalId یا نام عضو')
        types=QComboBox();types.addItem('تمام انواع','')
        for t in sorted({x['ifc_type'] for x in doc['elements']}):types.addItem(t,t)
        layout.addWidget(search);layout.addWidget(types)
        tree=QTreeWidget();tree.setObjectName('ifc_tree');tree.setHeaderLabels(['طبقه / عضو','نوع و GlobalId']);layout.addWidget(tree)
        detail=QLabel('یک عضو را انتخاب کنید؛ QTO صریح، مقدار مصالح یا مجوز پرداخت نیست')
        detail.setObjectName('ifc_detail');detail.setWordWrap(True);detail.setTextInteractionFlags(Qt.TextSelectableByMouse);layout.addWidget(detail)
        selected={}
        def populate():
            tree.clear();needle=search.text().strip();roots={}
            for e in doc['elements']:
                if types.currentData() and e['ifc_type']!=types.currentData():continue
                if needle and needle not in e['global_id'] and needle not in e['name']:continue
                sid=e['storey_id'] or ''
                if sid not in roots:
                    st=next((x for x in doc['storeys'] if x['global_id']==sid),{})
                    roots[sid]=QTreeWidgetItem(tree,[st.get('name','فاقد طبقه'),str(st.get('elevation_m',''))+' m'])
                leaf=QTreeWidgetItem(roots[sid],[e['name'],e['ifc_type']+' | '+e['global_id']]);leaf.setData(0,Qt.UserRole,e['global_id'])
            tree.expandAll()
        def choose(item):
            gid=item.data(0,Qt.UserRole) if item else None
            if not gid:return
            e=next(x for x in doc['elements'] if x['global_id']==gid);selected['element']=e;self.highlight_ifc_member(gid)
            qs='\n'.join(q['name']+': '+q['value_si']+' '+q['unit']+' | '+q['basis']+' | '+q['qset_name'] for q in e['quantities']) or 'فاقد QTO؛ مصالح تخمین زده نمی‌شود'
            detail.setText('GlobalId: '+gid+'\nمبدأ SI: '+str(e['origin_m'])+'\n'+qs+'\n'+'؛ '.join(e['warnings'])+'\nثبت مالی مسدود: هویت و Crosswalk بازبینی‌شده و پل مالی IFC تکمیل نشده است')
        tree.currentItemChanged.connect(lambda current,previous:choose(current))
        search.textChanged.connect(populate);types.currentIndexChanged.connect(populate);populate()
        form=QFormLayout();layout.addLayout(form)
        floors=QComboBox();members=QComboBox();author=QLineEdit();reference=QLineEdit()
        author.setObjectName('ifc_author');reference.setObjectName('ifc_reference')
        pid=self.project_id_input.text().strip();project=self.app_service.open_project(pid) if self.app_service and pid else None
        digest=self.app_service.store.current_digest(pid) if project else None
        for f in (project or {}).get('floors',[]):floors.addItem(f['name']+' | '+f['id'],f['id'])
        def member_list():
            members.clear()
            from core.projects.project_model import _identity
            for m in (project or {}).get('members',[]):
                if _identity(m.get('floor_id'))==_identity(floors.currentData()):members.addItem(m['id'],m['id'])
        floors.currentIndexChanged.connect(member_list);member_list()
        for label,field in [('طبقه واقعی پروژه',floors),('عضو واقعی پروژه',members),('ثبت‌کننده پیشنهاد',author),('مرجع تطبیق صریح',reference)]:form.addRow(label,field)
        save=QPushButton('ذخیره پیشنهاد هویت در پروژه؛ فاقد تأیید مالی');save.setObjectName('ifc_save_proposal');save.setEnabled(project is not None);layout.addWidget(save)
        outcome=QLabel();outcome.setWordWrap(True);layout.addWidget(outcome)
        def persist():
            nonlocal digest
            try:
                if 'element' not in selected:raise ValueError('ابتدا عضو IFC را انتخاب کنید')
                self.app_service.save_ifc_identity_proposal(pid,str(self.viewer.path),revision=doc['revision'],global_id=selected['element']['global_id'],floor_id=floors.currentData(),member_id=members.currentData(),author=author.text(),reference=reference.text(),expected_digest=digest,source_sha256=doc['source_sha256'])
                digest=self.app_service.store.current_digest(pid);outcome.setText('پیشنهاد هویت ذخیره شد؛ بازبینی و ثبت مالی هنوز مجاز نیست')
            except Exception as exc:outcome.setText('ذخیره انجام نشد: '+str(exc))
        save.clicked.connect(persist);dialog.show()

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

    def edit_measurement(self):
        row=self.table.currentRow()
        if row<0:return
        ident=self.table.item(row,0).text();item=self.session.find(ident)
        text,ok=QInputDialog.getText(self,"شرح متره","شرح اصلاح‌شده؛ مقدار فقط از هندسه محاسبه می‌شود:",text=item.label)
        if ok:
            self.session.edit(ident,label=text.strip());self.refresh()

    def apply_opening(self):
        from core.drawings.roof_region import add_rectangular_opening
        try:
            row=self.table.currentRow();rect=self.canvas._selected_region_rect
            if row<0 or rect is None:raise ValueError("ابتدا سطح مالک را در جدول و مستطیل بازشو را در نقشه انتخاب کنید")
            ident=self.table.item(row,0).text()
            if self.session.find(ident).page!=self.page:raise ValueError("بازشو باید در همان صفحه سطح مالک باشد")
            reference,ok=QInputDialog.getText(self,"مدرک بازشو","مرجع صریح ابعاد بازشو (اجباری):")
            if not ok:return
            add_rectangular_opening(self.session,ident,rectangle_to_points(rect.left(),rect.top(),rect.right(),rect.bottom()),reference)
            self.redraw_current_page();self.refresh()
            self.status.setText("بازشو از همان سطح کسر شد؛ عضو جدید یا ردیف پرداخت دوم ساخته نشد")
        except Exception as exc:QMessageBox.warning(self,"کسر بازشو",str(exc))

    def open_region_roof(self):
        """Bind a selected PDF rectangle to the existing three-roof editor."""
        from core.drawings.roof_region import KINDS, bind_source
        from core.takeoff.reviewed_aec import SPECS
        from app.roof_detail_editor import open_roof_editor,ask_local_frame
        try:
            rect=self.canvas._selected_region_rect
            selected_item=None;needs_frame=False
            selected_row=self.table.currentRow()
            if selected_row>=0:
                candidate=self.session.find(self.table.item(selected_row,0).text())
                if candidate.geometry_evidence:
                    from core.drawings.roof_region import _rectangle
                    try:xs,ys=_rectangle(candidate.geometry)
                    except ValueError:
                        xs=[min(p[0] for p in candidate.geometry),max(p[0] for p in candidate.geometry)];ys=[min(p[1] for p in candidate.geometry),max(p[1] for p in candidate.geometry)];needs_frame=True
                    if candidate.holes or candidate.geometry_evidence.get('policy')=='exact_planar_region_v2':needs_frame=True
                    selected_item=candidate
                    rect=QRectF(float(xs[0]),float(ys[0]),float(xs[1]-xs[0]),float(ys[1]-ys[0]))
            if self.viewer.kind!='pdf' or rect is None:
                raise ValueError("ابتدا یک ناحیه مستطیلی در PDF انتخاب کنید")
            if self.app_service is None or not self.project_id_input.text().strip():
                raise ValueError("پروژه واقعی برای ثبت سقف لازم است")
            self.session._factor_for(self.page)
            labels=[SPECS[k].title for k in KINDS]
            label,ok=QInputDialog.getItem(self,"انتخاب عملیات سقف","نوع سقف را طبق نقشه تأیید کنید:",labels,0,False)
            if not ok:return
            kind=KINDS[labels.index(label)]
            frame=ask_local_frame(self) if needs_frame else None
            if needs_frame and frame is None:return
            points=rectangle_to_points(rect.left(),rect.top(),rect.right(),rect.bottom())
            item=selected_item or next((x for x in self.session.for_page(self.page)
                       if x.kind=='area' and tuple(x.geometry)==tuple(points)),None)
            if item is None:
                item=self.session.add_area([Point(x,y) for x,y in points],page=self.page,
                     label="ناحیه سقف؛ نوع مصالح نیازمند دیتایل",source="roof-region:"+str((self.page,points)))
                self.refresh()
            pid=self.project_id_input.text().strip()
            if self.persisted_session_id:
                record=self.app_service.load_drawing_takeoff_session(pid,self.persisted_session_id)
                if record['revision']!=self.persisted_session_revision:
                    raise RuntimeError("نسخه نشست تغییر کرده است؛ پیش از اتصال سقف بازگشایی کنید")
                if json.dumps(record['session'],sort_keys=True)!=json.dumps(self.session.to_dict(),sort_keys=True):
                    if not self.save_session_to_project():return
            elif not self.save_session_to_project():return
            record=self.app_service.load_drawing_takeoff_session(pid,self.persisted_session_id)
            source=bind_source(record,item.id,local_frame=frame)
            open_roof_editor(self.app_service,parent=self,project_id=pid,floor_id=(item.geometry_evidence or {}).get('floor_id',''),kind=kind,drawing_source=source)
            self.status.setText("فرم تخصصی بسته شد؛ انتقال فقط از بازبینی و ثبت مجاز همان فرم انجام می‌شود")
        except Exception as exc:
            QMessageBox.warning(self,"سقف از ناحیه",str(exc))

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
                f"مقدار محاسبه‌شده: {preview_area} مترمربع\n"
                f"کالیبراسیون: {calibration.meters_per_pixel} متر/پیکسل\n"
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
                f"🟢 ناحیه به متره ثبت شد | {item.id} | {item.quantity} m² | صفحه {item.page} | کد BOQ: {item.takeoff_code or '—'}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "ثبت ناحیه", str(exc))

    def cancel_pending_polygon(self):
        self.canvas.points=[]
        self.redraw_current_page()
        self.status.setText('انتخاب چندضلعی لغو شد؛ متره ثبت‌شده تغییر نکرد')

    def remove_pending_vertex(self):
        if self.canvas.points:self.canvas.points.pop()
        self.redraw_current_page()
        self.canvas.preview_polygon()

    def finish_polygon(self):
        from core.drawings.planar_geometry import ring,cross
        try:
            points=[(p.x,p.y) for p in self.canvas.points]
            if self.canvas.mode=='polygon_opening':
                row=self.table.currentRow()
                if row<0:raise ValueError('سطح مالک را در جدول انتخاب کنید')
                ident=self.table.item(row,0).text();item=self.session.find(ident)
                if item.page!=self.page:raise ValueError('صفحه بازشو و مالک باید یکسان باشد')
                reference,ok=QInputDialog.getText(self,'مدرک مستقل بازشو','مرجع صریح هندسه بازشو:')
                if not ok:return
                # Validate before explicit confirmation, without mutating the session.
                refs=list((item.geometry_evidence or {}).get('opening_refs',[]))+[reference]
                policy='exact_planar_region_v2' if self.mode.currentText()=='بازشوی مرزی و چندقسمتی' else (item.geometry_evidence or {}).get('policy','exact_simple_polygon_v1')
                checked=self.session._polygon_evidence(item.geometry,item.holes+(tuple(points),),self.page,refs,topology=policy)
            else:
                r=ring(points)
                if self.canvas.mode=='rotated':
                    if len(r)!=4 or any(r[0][i]+r[2][i]!=r[1][i]+r[3][i] for i in (0,1)) or sum((r[1][i]-r[0][i])*(r[2][i]-r[1][i]) for i in (0,1))!=0:
                        raise ValueError('چهار رأس باید مستطیل چرخیده دقیق تشکیل دهند')
                checked=self.session._polygon_evidence(points,(),self.page,[])
            if QMessageBox.question(self,'بازبینی سطح هندسی',
                    f"ناخالص: {checked['gross_m2']} مترمربع\nکسورات: {checked['deducted_m2']}\nخالص: {checked['net_m2']}\nاین مقدار فقط سطح هندسی است؛ مصالح حدس زده نمی‌شوند. ثبت شود؟",
                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            if self.canvas.mode=='polygon_opening':self.session.add_polygon_opening(ident,points,reference,topology=policy)
            else:self.session.add_polygon([Point(*p) for p in points],page=self.page,label='سطح چندضلعی مستند',source=f'polygon:{self.page}:{self.session._counter+1}',floor_id=self.polygon_floor.text().strip(),member_id=self.polygon_member.text().strip(),quantity_owner=self.polygon_owner.text().strip())
            self.canvas.points=[];self.redraw_current_page();self.refresh()
            self.status.setText(f"ناخالص: {checked['gross_m2']} | کسورات: {checked['deducted_m2']} | خالص: {checked['net_m2']} مترمربع | صفحه {self.page}")
        except Exception as exc:QMessageBox.warning(self,'هندسه چندضلعی',str(exc))

    def open_drawing_correction(self):
        """Use the existing correction journal; the original session stays immutable."""
        from hashlib import sha256
        from core.takeoff.manual_formula_amendments import beam_current,digest,beam_effective_takeoffs
        from core.drawings.takeoff_bridge import validate_session_payload
        from core.commercial.exact_values import number,exact
        try:
            row=self.table.currentRow();pid=self.project_id_input.text().strip()
            if row<0 or not self.persisted_session_id:raise ValueError('یک برداشت قطعی از نشست ذخیره‌شده را انتخاب کنید')
            selected=self.table.item(row,0).text();project=self.app_service.open_project(pid)
            originals=[r for r in project.get('takeoffs',[]) if r.get('drawing_session_id')==self.persisted_session_id and r.get('drawing_takeoff_id')==selected]
            if len(originals)!=1:raise ValueError('این ردیف هنوز برداشت قطعی یکتا نیست')
            root=originals[0]['source_id'];base=beam_current(project,root);session_revision=project['drawing_sessions'][self.persisted_session_id]['revision']
            child=QDialog(self);child.setObjectName('DrawingPolygonCorrection');child.setWindowTitle('اصلاحیه مستند برداشت قطعی — اصل و تاریخچه محفوظ');child.setLayoutDirection(Qt.RightToLeft);child.resize(850,550)
            layout=QVBoxLayout(child);form=QFormLayout();layout.addLayout(form);controls={}
            for key,label in [('path','فایل مدرک اصلاحیه (JSON)'),('reference','مرجع مدرک'),('author','ایجادکننده درخواست'),('reason','دلیل اصلاح'),('reviewer','بازبین مستقل'),('note','یادداشت کنترل'),('id','شناسه اصلاحیه برای بازگشایی')]:
                field=QLineEdit();form.addRow(label,field);controls[key]=field
            summary=QLabel('نسخه مؤثر مبنا: '+str(base['revision'])+'؛ نسخه نشست: '+str(session_revision)+'؛ اصل نشست و ریزمتره هرگز بازنویسی نمی‌شود.');summary.setWordWrap(True);layout.addWidget(summary);controls['summary']=summary
            actions=QGridLayout();layout.addLayout(actions)
            def selected_amendment():
                a=self.app_service.open_project(pid).get('beam_amendments',{}).get(controls['id'].text().strip())
                if not a or a.get('kind')!='drawing_polygon_amendment' or a['beam_key']!=root:raise ValueError('اصلاحیه متعلق به برداشت انتخاب‌شده نیست')
                return a
            @exact
            def document():
                path=Path(controls['path'].text().strip())
                if not path.is_file():raise ValueError('فایل مدرک اصلاحیه انتخاب نشده است')
                doc=json.loads(path.read_text(encoding='utf-8-sig'));payload=doc.get('proposed_session',{})
                expected=self.app_service.drawing_amendment_document(pid,root,payload,expected_revision=base['revision'],expected_session_revision=session_revision)
                if digest(expected)!=digest(doc):raise ValueError('مدرک با نسخه و منبع مبنا مطابقت ندارد')
                report=validate_session_payload(payload)
                if not report['valid']:raise ValueError('؛ '.join(report['issues']))
                proposed=DrawingTakeoffSession.from_dict(payload);item=proposed.find(selected)
                effective=next(r for r in beam_effective_takeoffs(project,project['takeoffs']) if r['source_id']==root)
                previous=number(effective['quantities'][0]['amount'],'مقدار مبنا');quantity=number(item.geometry_evidence['net_m2'],'مقدار پیشنهاد')
                summary.setText('مبنا: '+str(previous)+'؛ پیشنهاد: '+str(quantity)+'؛ اختلاف: '+str(quantity-previous)+' مترمربع؛ صفحه '+str(item.page)+'؛ منبع: '+proposed.drawing_source+'؛ SHA-256: '+proposed.source_sha256)
                return path,payload
            def create():
                path,payload=document()
                if QMessageBox.question(child,'ثبت درخواست اصلاحیه','درخواست با این مدرک ثبت شود؟ این اقدام تأیید مهندسی یا اعمال مالی نیست.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
                a=self.app_service.create_drawing_amendment(pid,root,payload,expected_revision=base['revision'],expected_session_revision=session_revision,created_by=controls['author'].text(),reason=controls['reason'].text(),evidence={'evidence_path':str(path),'evidence_sha256':sha256(path.read_bytes()).hexdigest(),'evidence_reference':controls['reference'].text()})
                controls['id'].setText(a['id']);load()
            def load():
                a=selected_amendment();summary.setText('نسخه مبنا: '+str(a['base_revision'])+'؛ نسخه جدید: '+str(a['base_revision']+1)+'؛ اختلاف مقدار: '+str(a['delta'][root])+' مترمربع؛ وضعیت: '+{'draft':'پیش‌نویس','reviewed':'بازبینی‌شده','applied':'اعمال‌شده'}[a['status']]+'؛ اصل نشست محفوظ است.')
            def review():
                a=selected_amendment();self.app_service.review_beam_amendment(pid,a['id'],expected_revision=a['revision'],reviewer=controls['reviewer'].text(),note=controls['note'].text());load()
            def apply():
                a=selected_amendment();self.app_service.apply_beam_amendment(pid,a['id'],expected_revision=a['revision']);load()
                self.status.setText('اثر اصلاحیه در BOQ ثبت شد؛ جدول نشست، اصل تاریخی است. هندسه مؤثر از پنجره اصلاحیه قابل مشاهده است.')
            def highlight():
                a=selected_amendment();payload=a['proposal']['proposed_session'];proposed=DrawingTakeoffSession.from_dict(payload);item=proposed.find(selected)
                if proposed.drawing_source!=self.session.drawing_source:
                    viewer=GraphicalTakeoffDialog(child,proposed.drawing_source);viewer.session=proposed;viewer.canvas.session=proposed;viewer.load_page(item.page);viewer.canvas.highlight_measurement(item);viewer.exec()
                else:
                    if item.page!=self.page:self.load_page(item.page)
                    self.canvas.highlight_measurement(item)
            def run(fn):
                try:fn()
                except Exception as exc:QMessageBox.warning(child,'کنترل اصلاحیه برداشت',str(exc))
            for index,(key,label,fn) in enumerate([('preview','پیش‌نمایش مدرک',document),('create','ثبت درخواست',create),('load','بازگشایی اصلاحیه',load),('review','بازبینی مستقل',review),('apply','اعمال مجاز به BOQ',apply),('highlight','هایلایت هندسه پیشنهادی/مؤثر',highlight)]):
                button=QPushButton(label);button.clicked.connect(lambda _=False,f=fn:run(f));actions.addWidget(button,index//3,index%3);controls[key]=button
            child.correction_controls=controls;child.exec()
        except Exception as exc:QMessageBox.warning(self,'اصلاحیه برداشت',str(exc))

    def remove_selected_opening(self):
        try:
            row=self.table.currentRow()
            if row<0:raise ValueError('ابتدا سطح مالک را انتخاب کنید')
            item=self.session.find(self.table.item(row,0).text());meta=item.geometry_evidence or {}
            refs=meta.get('opening_refs',[])
            if len(refs)!=len(item.holes) or not refs:raise ValueError('بازشوی دارای مرجع مستقل یافت نشد')
            labels=[str(i+1)+' | '+ref for i,ref in enumerate(refs)]
            label,ok=QInputDialog.getItem(self,'حذف بازشو','بازشوی دارای مدرک اصلاحی را انتخاب کنید:',labels,0,False)
            if not ok:return
            index=labels.index(label)
            self.session.edit_polygon(item.id,item.geometry,holes=[h for i,h in enumerate(item.holes) if i!=index],opening_refs=[r for i,r in enumerate(refs) if i!=index])
            self.redraw_current_page();self.refresh()
            self.status.setText('بازشو از پیش‌نویس حذف شد؛ برداشت قطعی فقط با اصلاحیه رسمی تغییر می‌کند')
        except Exception as exc:QMessageBox.warning(self,'حذف بازشو',str(exc))

    def highlight_component(self):
        component=self.geometry_components.currentData()
        if component is None:return
        row=self.table.currentRow()
        if row<0:return
        from dataclasses import replace
        item=self.session.find(self.table.item(row,0).text())
        display=replace(item,geometry=tuple(tuple(float(v) for v in p) for p in component['outer']),holes=tuple(tuple(tuple(float(v) for v in p) for p in h) for h in component['holes']))
        self.canvas.highlight_measurement(display)
        self.status.setText(component['id']+' | سطح جزء: '+component['net_m2']+' مترمربع | صفحه '+str(item.page))

    def edit_polygon_vertices(self):
        try:
            row=self.table.currentRow()
            if row<0:raise ValueError('یک سطح را انتخاب کنید')
            ident=self.table.item(row,0).text();item=self.session.find(ident)
            text,ok=QInputDialog.getMultiLineText(self,'ویرایش رأس‌ها','مختصات مرجع صفحه؛ آرایه زوج‌های x و y:',json.dumps(item.geometry))
            if not ok:return
            self.session.edit_polygon(ident,json.loads(text))
            self.redraw_current_page();self.refresh()
        except Exception as exc:QMessageBox.warning(self,'ویرایش هندسه',str(exc))

    def apply_tool(self):
        mapping = {
            "طول": "length", "مساحت": "area",
            "شمارش": "count", "یادداشت": "note",
            "چندضلعی دقیق":"polygon", "ناحیه چرخیده":"rotated", "بازشوی چندضلعی":"polygon_opening", "بازشوی مرزی و چندقسمتی":"polygon_opening"
        }
        self.canvas.set_mode(mapping[self.mode.currentText()])
        self.status.setText(
            f"ابزار فعال: {self.mode.currentText()} | صفحه {self.page}"
        )

    def calibrate_scale(self):
        if self.viewer.kind == "ifc":
            self._ifc_status()
            return
        if self.canvas.mode == 'length' and len(self.canvas.points) == 2:
            from math import hypot
            first, second = self.canvas.points
            px = hypot(second.x-first.x, second.y-first.y)
            prompt = f"فاصله معلوم بین دو نقطه انتخابی ({px:g} پیکسل مرجع) طبق مدرک (متر):"
        else:
            px, ok = QInputDialog.getText(self,"کالیبراسیون مقیاس","فاصله اندازه‌گیری‌شده روی صفحه (پیکسل؛ مقدار صریح):")
            if not ok:return
            prompt = "فاصله معلوم طبق مدرک (متر؛ مقدار صریح):"
        meters, ok = QInputDialog.getText(self,"کالیبراسیون مقیاس",prompt)
        if not ok:return
        try:
            cal = self.session.calibrate(self.page, px, meters)
            px,meters=float(px),float(meters)
            self.scale_label.setText(
                f"مقیاس: {cal.meters_per_pixel} m/px"
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
        if self.cad_loading:return
        if self.session.undo():
            self.redraw_current_page()
            self.refresh()

    def redo_session(self):
        if self.cad_loading:return
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
        self.canvas.clear_measurement_highlight()
        self.canvas._polygon_preview = None
        self.canvas.scene.clear()
        self.canvas._region_overlay = None
        self.canvas._selected_region_rect = None
        if self.viewer.kind == "pdf":
            self._render_pdf_background()
            for item in self.session.for_page(self.page):
                self.canvas._draw_measurement(item)
        elif self.viewer.kind == "ifc":
            self._render_ifc()
        else:
            self._render_cad()

    def export_takeoff_for_boq(self):
        if self.cad_loading:return
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

    def highlight_selected_measurement(self):
        if self.cad_loading:return
        row = self.table.currentRow()
        cell = self.table.item(row, 0) if row >= 0 else None
        if cell is None:
            self.canvas.clear_measurement_highlight()
            return
        item = next((x for x in self.session.items if x.id == cell.text()), None)
        if item is None: return
        if item.page != self.page: self.load_page(item.page)
        if item.cad_evidence:
            self.cad_handle.setText(item.cad_evidence['handle']);self.find_cad_handle()
        else:self.canvas.highlight_measurement(item)
        self.geometry_components.blockSignals(True);self.geometry_components.clear();self.geometry_components.addItem('تمام اجزای سطح',None)
        for component in (item.geometry_evidence or {}).get('components',[]):self.geometry_components.addItem(component['id'][:15]+' | '+component['net_m2']+' مترمربع',component)
        self.geometry_components.setEnabled(self.geometry_components.count()>1);self.geometry_components.blockSignals(False)
        if self.beam_detail_panel is not None: self.beam_dock.show()

    def refresh(self):
        self.table.blockSignals(True)
        self.canvas.clear_measurement_highlight()
        self.table.setRowCount(0)
        for i, item in enumerate(self.session.items):
            self.table.insertRow(i)
            values = [
                item.id, item.page, {"length":"طول","area":"مساحت","count":"شمارش"}.get(item.kind,item.kind), item.label or item.takeoff_code,
                item.geometry_evidence["net_m2"] if item.geometry_evidence else str(item.quantity), item.unit, item.takeoff_code or "—",
                item.source_ref,
            ]
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))

        self.table.blockSignals(False)
        valid = self.session.validate()
        state = "🟢 معتبر" if valid["valid"] else "🟠 نیازمند بررسی"
        self.status.setText(
            f"{state} | متره‌ها: {len(self.session.items)} | "
            f"واگرد: {'فعال' if self.session.can_undo else '—'} | "
            f"تکرار: {'فعال' if self.session.can_redo else '—'}"
        )
        self.undo.setEnabled(self.session.can_undo)
        self.redo.setEnabled(self.session.can_redo)
