"""Actual PySide6 menu and draft-amendment clicks against StructuralProApp/SQLite."""
from copy import deepcopy
from contextlib import contextmanager
from time import monotonic
import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QDialog

from app.reviewed_structural_manual_editor import open_manual_structural_editor
from core.platform.application import StructuralProApp
from test_bored_pile_draft_amendment_real_application import _changed_document
from test_bored_pile_real_application_controller import _setup, _document, _ownership


@contextmanager
def _expected_modal(qt, object_name, title, button, *, parent=None, timeout=4.0):
    """Click the specific live Qt modal, or close it and fail within a bound."""
    timer = QTimer()
    timer.setInterval(20)
    deadline = monotonic() + timeout
    state = {'clicked': False, 'error': None}
    def poll():
        box = qt.activeModalWidget()
        if not state['clicked'] and isinstance(box, QMessageBox):
            if (box.objectName() == object_name and box.windowTitle() == title
                    and (parent is None or box.parentWidget() is parent)):
                target = box.button(button)
                if target is not None and target.isVisible() and target.isEnabled():
                    state['clicked'] = True
                    QTest.mouseClick(target, Qt.LeftButton, pos=target.rect().center())
                    return
        if monotonic() >= deadline:
            state['error'] = f'Expected modal {object_name!r}/{title!r}, got {box!r}'
            timer.stop()
            if isinstance(box, QMessageBox):
                box.done(QMessageBox.No)
            elif isinstance(box, QDialog):
                QDialog.done(box, QDialog.Rejected)
    timer.timeout.connect(poll)
    timer.start()
    try:
        yield
    finally:
        timer.stop()
        timer.deleteLater()
    assert not state['error'], state['error']
    assert state['clicked'], f'Expected modal {object_name!r}/{title!r} was not shown'


def _schedule_dialog(qt, name, callback, errors, *, timeout=8.0):
    timer = QTimer(qt)
    timer.setInterval(20)
    deadline = monotonic() + timeout
    def poll():
        dialog = qt.activeModalWidget()
        if isinstance(dialog, QDialog) and dialog.objectName() == name:
            timer.stop()
            try:
                callback()
            except Exception as exc:
                errors.append(repr(exc))
                QDialog.done(dialog, QDialog.Rejected)
        elif monotonic() >= deadline:
            timer.stop()
            errors.append(f'Expected dialog {name!r}; active={dialog!r}')
            if isinstance(dialog, QDialog):
                QDialog.done(dialog, QDialog.Rejected)
    timer.timeout.connect(poll)
    timer.start()
    return timer


def test_real_menu_amendment_reopens_and_revokes_ownership(tmp_path, monkeypatch):
    qt = QApplication.instance() or QApplication([])
    app, controller, data = _setup(tmp_path)
    controller.attach_ownership(_document(tmp_path/'owner.json', _ownership(data)),
                                reference='Synthetic initial ownership')
    controller.save()
    revised = _changed_document(data)
    chosen = [_document(tmp_path/'revised.json', revised)]
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: (chosen[0], ''))
    errors = []
    def parent():
        dialog = qt.activeModalWidget()
        controls = dialog.column_controls
        def child():
            pile_dialog = qt.activeModalWidget()
            try:
                c = pile_dialog.pile_controls
                def click(key):
                    qt.processEvents()
                    QTest.mouseClick(c[key], Qt.LeftButton,
                                     pos=c[key].rect().center())
                    qt.processEvents()
                assert pile_dialog.layoutDirection() == Qt.RightToLeft
                assert c['controller'].revision == 1
                assert c['piles'].item(0, 3).text().startswith('-')
                c['amendment_reason'].setText('اصلاح مستند نوع بتن شمع')
                click('amend')
                assert c['controller'].revision == 2
                assert c['ownership_sha256'].text() == ''
                assert c['joint_sha256'].text() == ''
                assert 'ثبت مالی مسدود' in c['message'].text()
                click('history_refresh')
                assert c['history'].rowCount() == 1
                click('preview')
                report = json.loads(c['report'].toPlainText())
                assert report['engineering_ready'] is True
                assert report['ready'] is False and report['commit_allowed'] is False
                assert report['ownership_audit'] is None and report['joint_audit'] is None
                assert app.open_project('P')['boq'] == app.open_project('P')['takeoffs'] == []
                # A repeated file and an empty reason must fail without another version.
                c['amendment_reason'].setText('تلاش تکراری')
                with _expected_modal(qt, 'BoredPileErrorMessage', 'کنترل دیتایل شمع', QMessageBox.Ok, parent=pile_dialog):
                    click('amend')
                assert c['controller'].revision == 2 and c['message'].text().startswith('خطا:')
                c['amendment_reason'].clear()
                with _expected_modal(qt, 'BoredPileErrorMessage', 'کنترل دیتایل شمع', QMessageBox.Ok, parent=pile_dialog):
                    click('amend')
                assert c['controller'].revision == 2 and c['message'].text().startswith('خطا:')
            except Exception as exc:
                errors.append(repr(exc))
            finally:
                try:
                    with _expected_modal(qt, '', 'تغییرات ذخیره‌نشده', QMessageBox.Yes, parent=pile_dialog):
                        pile_dialog.reject()
                except Exception as exc:
                    errors.append(repr(exc))
                    QDialog.done(pile_dialog, QDialog.Rejected)
        try:
            controls['kind'].setCurrentIndex(controls['kind'].findData('bored_pile'))
            controls['id'].setText('PG1')
            controls['scroll'].ensureWidgetVisible(controls['pile_specialist'])
            qt.processEvents()
            child_timer = _schedule_dialog(qt, 'BoredPileDraftEditor', child, errors)
            try:
                QTest.mouseClick(controls['pile_specialist'], Qt.LeftButton,
                                 pos=controls['pile_specialist'].rect().center())
            finally:
                child_timer.stop(); child_timer.deleteLater()
        except Exception as exc:
            errors.append(repr(exc))
        finally:
            dialog.reject()
    parent_timer = _schedule_dialog(qt, 'ReviewedStructuralManualEditor', parent, errors)
    try:
        open_manual_structural_editor(app, project_id='P', floor_id='FND')
    finally:
        parent_timer.stop(); parent_timer.deleteLater()
    qt.processEvents()
    assert errors == []
    app.store.close()
    reopened = StructuralProApp(tmp_path/'db')
    record = reopened.get_structural_member('P','bored_pile','FND','PG1')
    assert record['revision'] == 2 and record['status'] == 'draft'
    assert record['data']['pile_detail']['input'] == revised
    assert len(reopened.open_project('P')['structural_member_history']) == 1
    reopened.store.close()


def test_delayed_real_warning_is_clicked_after_early_timer_would_expire():
    qt = QApplication.instance() or QApplication([])
    seen = []
    early = []
    QTimer.singleShot(10, lambda: early.append(qt.activeModalWidget()))
    def open_later():
        box = QMessageBox()
        box.setOption(QMessageBox.Option.DontUseNativeDialog)
        box.setObjectName('BoredPileErrorMessage')
        box.setWindowTitle('کنترل دیتایل شمع')
        box.setStandardButtons(QMessageBox.Ok)
        seen.append(box.exec())
    # Deliberately exceed the old 10 ms one-shot timer.
    QTimer.singleShot(80, open_later)
    from PySide6.QtCore import QEventLoop
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    with _expected_modal(qt, 'BoredPileErrorMessage', 'کنترل دیتایل شمع', QMessageBox.Ok):
        loop.exec()
    assert early == [None]
    assert seen == [QMessageBox.Ok]


def test_unexpected_modal_fails_within_bound_without_clicking_its_button():
    import pytest
    from PySide6.QtCore import QEventLoop
    qt = QApplication.instance() or QApplication([])
    seen = []
    def open_unexpected():
        box = QMessageBox()
        box.setOption(QMessageBox.Option.DontUseNativeDialog)
        box.setObjectName('UnrelatedWarning')
        box.setWindowTitle('unrelated')
        box.setStandardButtons(QMessageBox.Ok)
        seen.append(box.exec())
    loop = QEventLoop()
    QTimer.singleShot(10, open_unexpected)
    QTimer.singleShot(200, loop.quit)
    with pytest.raises(AssertionError, match='Expected modal'):
        with _expected_modal(qt, 'BoredPileErrorMessage', 'کنترل دیتایل شمع', QMessageBox.Ok, timeout=0.08):
            loop.exec()
    assert seen == [QMessageBox.No]


def test_ignored_click_is_reported_by_watchdog():
    import pytest
    from PySide6.QtCore import QEventLoop, QObject, QEvent
    qt = QApplication.instance() or QApplication([])
    loop = QEventLoop()
    class IgnoreClicks(QObject):
        def eventFilter(self, watched, event):
            return event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease)
    event_filter = IgnoreClicks()
    def open_warning():
        box = QMessageBox()
        box.setOption(QMessageBox.Option.DontUseNativeDialog)
        box.setObjectName('BoredPileErrorMessage')
        box.setWindowTitle('کنترل دیتایل شمع')
        box.setStandardButtons(QMessageBox.Ok)
        box.button(QMessageBox.Ok).installEventFilter(event_filter)
        QTimer.singleShot(400, lambda: box.done(QMessageBox.No))
        box.exec()
    QTimer.singleShot(10, open_warning)
    QTimer.singleShot(600, loop.quit)
    with pytest.raises(AssertionError, match='Expected modal'):
        with _expected_modal(qt, 'BoredPileErrorMessage', 'کنترل دیتایل شمع', QMessageBox.Ok, timeout=0.12):
            loop.exec()
