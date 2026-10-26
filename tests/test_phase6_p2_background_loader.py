"""P6-2: background IFC opening, cooperative cancellation and stale UI guards."""
from pathlib import Path
import hashlib
import threading

import pytest


def test_hash_uses_bounded_memory_and_obeys_cancel(tmp_path):
    from app.ifc_3d_loader import digest_file
    p = tmp_path / 'source.ifc'
    p.write_bytes(b'a' * (3 * 1024 * 1024 + 37))
    assert digest_file(p) == hashlib.sha256(p.read_bytes()).hexdigest()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError, match='لغو'):
        digest_file(p, cancel)


def test_cancelled_job_never_returns_partial_geometry(tmp_path):
    from app.ifc_3d_loader import IFC3DLoadJob
    job = IFC3DLoadJob(token=9, path=str(tmp_path/'not-loaded.ifc'),
                       revision='R1', expected_sha='0'*64)
    cancelled, finished, failed = [], [], []
    job.signals.cancelled.connect(cancelled.append)
    job.signals.finished.connect(lambda *_: finished.append('unwanted'))
    job.signals.failed.connect(lambda *_: failed.append('unwanted'))
    job.cancel()
    job.run()
    assert cancelled == [9]
    assert not finished and not failed


def test_wrong_digest_fails_before_ifc_parser_runs(tmp_path, monkeypatch):
    from app.ifc_3d_loader import IFC3DLoadJob
    from core.bim.ifc import DeepIFCAdapter
    p = tmp_path/'source.ifc'
    p.write_bytes(b'legitimate source')
    calls = []
    monkeypatch.setattr(DeepIFCAdapter, 'read_display_contract',
                        lambda *_args, **_kw: calls.append(True))
    job = IFC3DLoadJob(token=3, path=str(p), revision='R1',
                       expected_sha='0'*64)
    errors = []
    job.signals.failed.connect(lambda token, message: errors.append((token, message)))
    job.run()
    assert len(errors) == 1 and errors[0][0] == 3
    assert 'هش' in errors[0][1]
    assert not calls


def test_real_gui_cancel_ignores_late_worker_and_preserves_session(tmp_path, monkeypatch):
    pytest.importorskip('ifcopenshell')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from core.bim.ifc import DeepIFCAdapter
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from test_phase2_priority5_ifc import model_file

    path = tmp_path / 'model.ifc'
    model_file(path)
    qt = QApplication.instance() or QApplication([])
    dlg = GraphicalTakeoffDialog()
    dlg.open_drawing(str(path))
    dlg.ifc_revision.setText('R1')
    before = dlg.session.to_dict()
    entered, release = threading.Event(), threading.Event()
    original = DeepIFCAdapter.read_display_contract
    def slow_parse(adapter, *args, **kw):
        entered.set()
        release.wait(timeout=5)
        return original(adapter, *args, **kw)
    monkeypatch.setattr(DeepIFCAdapter, 'read_display_contract', slow_parse)
    try:
        dlg.open_ifc_3d()
        for _ in range(300):
            qt.processEvents()
            if entered.is_set():
                break
            QTest.qWait(10)
        assert entered.is_set()
        assert dlg._ifc_3d_loader is not None
        assert dlg.ifc_3d_cancel.isEnabled()
        assert dlg.cancel_ifc_3d_loading()
        assert dlg._ifc_3d_loader is None
        assert dlg.ifc_3d_button.isEnabled()
        assert dlg._ifc_3d_dialog is None
        release.set()
        for _ in range(50):
            qt.processEvents()
            QTest.qWait(10)
        assert dlg._ifc_3d_dialog is None
        assert dlg.session.to_dict() == before
        assert not dlg.cancel_ifc_3d_loading()
    finally:
        release.set()
        dlg.close()
