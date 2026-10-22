"""Acceptance of the remaining IFC gates using real Qt, IFC and SQLite."""
import gc,weakref

def test_closed_drawing_window_releases_scene_and_model():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog();w.show();ref=weakref.ref(w)
    w.close();del w
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    app.processEvents();gc.collect()
    assert ref() is None, 'Closed drawing window is retained by Qt signal/parent cycles'
