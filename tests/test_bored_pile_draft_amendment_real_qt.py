"""Actual PySide6 menu and draft-amendment clicks against StructuralProApp/SQLite."""
from copy import deepcopy
import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.reviewed_structural_manual_editor import open_manual_structural_editor
from core.platform.application import StructuralProApp
from test_bored_pile_draft_amendment_real_application import _changed_document
from test_bored_pile_real_application_controller import _setup, _document, _ownership


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
    def dismiss_warning():
        box = qt.activeModalWidget()
        if isinstance(box, QMessageBox):
            QTest.mouseClick(box.button(QMessageBox.Ok), Qt.LeftButton,
                             pos=box.button(QMessageBox.Ok).rect().center())
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
                QTimer.singleShot(10, dismiss_warning)
                click('amend')
                assert c['controller'].revision == 2 and c['message'].text().startswith('خطا:')
                c['amendment_reason'].clear()
                QTimer.singleShot(10, dismiss_warning)
                click('amend')
                assert c['controller'].revision == 2 and c['message'].text().startswith('خطا:')
            except Exception as exc:
                errors.append(repr(exc))
            finally:
                def discard_unsaved_reason():
                    box = qt.activeModalWidget()
                    if isinstance(box, QMessageBox):
                        QTest.mouseClick(box.button(QMessageBox.Yes), Qt.LeftButton)
                QTimer.singleShot(10, discard_unsaved_reason)
                pile_dialog.reject()
        try:
            controls['kind'].setCurrentIndex(controls['kind'].findData('bored_pile'))
            controls['id'].setText('PG1')
            controls['scroll'].ensureWidgetVisible(controls['pile_specialist'])
            qt.processEvents()
            QTimer.singleShot(20, child)
            QTest.mouseClick(controls['pile_specialist'], Qt.LeftButton,
                             pos=controls['pile_specialist'].rect().center())
        except Exception as exc:
            errors.append(repr(exc))
        finally:
            dialog.reject()
    QTimer.singleShot(25, parent)
    open_manual_structural_editor(app, project_id='P', floor_id='FND')
    qt.processEvents()
    assert errors == []
    app.store.close()
    reopened = StructuralProApp(tmp_path/'db')
    record = reopened.get_structural_member('P','bored_pile','FND','PG1')
    assert record['revision'] == 2 and record['status'] == 'draft'
    assert record['data']['pile_detail']['input'] == revised
    assert len(reopened.open_project('P')['structural_member_history']) == 1
    reopened.store.close()
