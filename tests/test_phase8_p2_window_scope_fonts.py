"""P8/P2: window-zoom-scoped takeoff, bilingual CAD labels, legacy SHX gates.

Synthetic scene for interaction tests, independent public drawing tests run in
existing source-backed workflows; private user DWG stays out of GitHub.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QApplication, QGraphicsItem
from PySide6.QtTest import QTest

from core.cad.persian_text_v1 import normalize_cad_text, is_rtl_cad_text
from core.drawings.viewport_tools import ViewportRect
from core.drawings.takeoff_session import DrawingTakeoffSession
from app.graphical_takeoff import TakeoffCanvas


@pytest.fixture(scope="module")
def qapp():
    app=QApplication.instance() or QApplication(["StructuralPro window test"])
    yield app


def test_scene_window_handles_small_real_cad_drawing_units():
    scope=ViewportRect.from_points(.15,.4,.65,.2)
    assert scope.is_usable(0)
    assert not scope.is_usable(8)  # threshold is SCREEN pixels, not scene metres.
    inside=ViewportRect.from_points(.2,.21,.45,.22)
    crossing=ViewportRect.from_points(.5,.22,.8,.25)
    outside=ViewportRect.from_points(.7,.22,.9,.25)
    assert scope.classify_rect(inside)=="inside"
    assert scope.classify_rect(crossing)=="crossing"
    assert scope.classify_rect(outside)=="outside"
    assert scope.classify_rect(ViewportRect(.3,.25,.55,.25))=="inside"  # LINE with 0-height bbox


def test_invalid_numeric_windows_are_not_accepted():
    assert not ViewportRect(0,0,float("nan"),1).is_usable(0)
    assert not ViewportRect(0,0,float("inf"),1).is_usable(0)
    with pytest.raises(ValueError):
        ViewportRect.from_points(0,0,10,10).is_usable(float("nan"))


def test_real_qt_window_zoom_keeps_scope_when_switching_to_takeoff_selection(qapp):
    canvas=TakeoffCanvas(DrawingTakeoffSession())
    try:
        canvas.resize(560,450)
        canvas.scene.setSceneRect(0,0,1,1)
        canvas.show()
        canvas.fitInView(QRectF(0,0,1,1),Qt.AspectRatioMode.KeepAspectRatio)
        qapp.processEvents()
        canvas.set_mode("zoom_window")
        top=canvas.mapFromScene(QPointF(.1,.1))
        bottom=canvas.mapFromScene(QPointF(.6,.6))
        assert abs(bottom.x()-top.x())>8 and abs(bottom.y()-top.y())>8
        QTest.mousePress(canvas.viewport(),Qt.MouseButton.LeftButton,pos=top)
        QTest.mouseMove(canvas.viewport(),pos=bottom)
        QTest.mouseRelease(canvas.viewport(),Qt.MouseButton.LeftButton,pos=bottom)
        qapp.processEvents()
        rect=canvas._selected_region_rect
        assert rect is not None
        assert rect.width()<8 and rect.height()<8  # raw drawing units are <1
        canvas.set_mode("cad_select")
        assert canvas._selected_region_rect == rect
        # Assert against the ACTUAL scene rectangle returned by Qt after
        # integer-pixel drag rounding; Windows/Wayland differ by a pixel.
        x0,y0,w,h=rect.left(),rect.top(),rect.width(),rect.height()
        inside=canvas.scene.addLine(x0+.15*w,y0+.3*h,x0+.35*w,y0+.3*h)
        cross=canvas.scene.addLine(x0+.8*w,y0+.5*h,x0+1.2*w,y0+.5*h)
        outside=canvas.scene.addLine(x0+1.3*w,y0+1.3*h,x0+1.5*w,y0+1.5*h)
        assert canvas._scope_relation(inside) == "inside"
        assert canvas._scope_relation(cross) == "crossing"
        assert canvas._scope_relation(outside) == "outside"
        canvas.cancel_interaction()
        assert canvas._selected_region_rect is None
    finally:
        canvas.close()
        canvas.deleteLater()


def test_can_select_inside_window_but_not_crossing_or_outside(qapp):
    canvas=TakeoffCanvas(DrawingTakeoffSession())
    try:
        canvas.resize(550,450)
        canvas.scene.setSceneRect(0,0,500,400)
        inside=canvas.scene.addLine(100,100,150,100)
        cross=canvas.scene.addLine(150,130,300,130)
        outside=canvas.scene.addLine(300,250,370,250)
        for item,handle in ((inside,"inside"),(cross,"cross"),(outside,"outside")):
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            item.setData(0,handle)
        canvas.show();qapp.processEvents()
        canvas._set_region_highlight(QRectF(90,85,105,75))
        canvas.set_mode("cad_select")
        def pick(pos):
            p=canvas.mapFromScene(QPointF(*pos))
            QTest.mouseClick(canvas.viewport(),Qt.MouseButton.LeftButton,pos=p)
            qapp.processEvents()
        pick((120,100))
        assert inside.isSelected()
        pick((220,130))
        assert not cross.isSelected()
        pick((340,250))
        assert not outside.isSelected()
    finally:
        canvas.close();canvas.deleteLater()


def test_unicode_persian_and_english_are_preserved_without_fake_shx_decoding():
    assert normalize_cad_text(r"\U+0633\U+062A\U+0648\U+0646 A-1") == "ستون A-1"
    assert is_rtl_cad_text("ستون A-1")
    assert not is_rtl_cad_text("BEAM B-1")
    raw = "`ë¢ f__—¥"   # actual legacy type of encoded source text
    assert normalize_cad_text(raw)==raw  # decoding needs original font mapping
