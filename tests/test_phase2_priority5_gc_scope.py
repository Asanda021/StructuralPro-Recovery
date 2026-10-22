"""Automatic full-heap scans are deferred only while a Qt import is active."""
import gc
import pytest
from test_phase2_priority4_closure import fixture, qt, wait

@pytest.mark.parametrize('finish', ['cancel', 'success', 'error', 'close'])
def test_import_gc_policy_restored_on_every_terminal_path(tmp_path, finish):
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from PySide6.QtCore import QCoreApplication, QEvent
    qt()
    path = fixture(tmp_path, 30)
    if finish == 'error':
        path.write_text('corrupt DXF')
    original = gc.get_threshold()
    enabled = gc.isenabled()
    window = GraphicalTakeoffDialog()
    window.show()
    try:
        window.open_cad_async(str(path))
        current = gc.get_threshold()
        assert current[:2] == original[:2]
        assert current[2] > original[2], 'full-heap collection still scheduled in GUI load'
        assert gc.isenabled() == enabled
        if finish == 'cancel': window.cancel_cad_loading()
        elif finish == 'close': window.close()
        else: wait(lambda: not window.cad_loading)
        assert gc.get_threshold() == original
        assert gc.isenabled() == enabled
    finally:
        window.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        assert gc.get_threshold() == original


def test_overlapping_windows_release_policy_after_last_import(tmp_path):
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt(); path = fixture(tmp_path, 30); original = gc.get_threshold()
    a, b = GraphicalTakeoffDialog(), GraphicalTakeoffDialog()
    try:
        a.open_cad_async(str(path)); b.open_cad_async(str(path))
        a.cancel_cad_loading()
        assert gc.get_threshold()[2] > original[2]
        b.cancel_cad_loading()
        assert gc.get_threshold() == original
    finally:
        a.close(); b.close()
