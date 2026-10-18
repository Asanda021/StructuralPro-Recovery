"""Offscreen Qt acceptance through the real spatial engine and SQLite."""
import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.reviewed_structural_manual_editor import open_manual_structural_editor
from app.bored_pile_draft_controller import PileDraftController
from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_spatial_overlap import POLICY
from test_bored_pile_joint_real_application import _saved_joint_case
from test_bored_pile_real_application_controller import _document


def test_menu_click_real_spatial_engine_is_ephemeral_and_finance_locked(tmp_path, monkeypatch):
    qt = QApplication.instance() or QApplication([])
    app, controller, data, compiled, owner, joint, _ = _saved_joint_case(tmp_path)
    controller.attach_joint(_document(tmp_path / 'joint.json', joint), reference='Synthetic joint')
    controller.save()
    link = joint['interfaces'][0]
    pile = data['piles'][0]
    proof = {
        'policy': POLICY, 'project_id': 'P', 'floor_id': 'FND', 'group_id': 'PG1',
        'input_sha256': compiled['source_sha256'],
        'coordinate_ref': data['datum']['coordinate_ref'],
        'vertical_datum_ref': data['datum']['vertical_datum_ref'],
        'prepared_by': 'SpatialPreparer', 'reviewer': 'SpatialIndependentReviewer',
        'links': [{
            'pile_id': pile['id'], 'pile_physical_id': pile['physical_id'],
            'other_kind': link['other_kind'], 'other_floor_id': link['other_floor_id'],
            'other_member_id': link['other_member_id'],
            'other_physical_id': link['other_physical_id'],
            'other_record_sha256': link['other_record_sha256'],
            'other_revision': link['other_revision'],
            'pile_center_x_m': '0', 'pile_center_y_m': '0',
            'other_x_min_m': '-1', 'other_y_min_m': '-1',
            'other_x_max_m': '1', 'other_y_max_m': '1',
            'other_top_m': link['other_top_m'], 'other_bottom_m': link['other_bottom_m'],
            'geometry_reference': link['geometry_reference'],
            'geometry_sha256': link['geometry_sha256'],
            'deduction_id': link['deduction_id'],
        }],
    }
    path = _document(tmp_path / 'spatial.json', proof)
    chosen = [path]
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: (chosen[0], ''))
    before = app.open_project('P')
    failures = []

    def dismiss_warning():
        box = qt.activeModalWidget()
        if isinstance(box, QMessageBox):
            QTest.mouseClick(box.button(QMessageBox.Ok), Qt.LeftButton)

    def parent():
        dialog = qt.activeModalWidget()
        controls = dialog.column_controls

        def child():
            pile_dialog = qt.activeModalWidget()
            try:
                c = pile_dialog.pile_controls
                def click(key):
                    QTest.mouseClick(c[key], Qt.LeftButton)
                    qt.processEvents()
                assert pile_dialog.layoutDirection() == Qt.RightToLeft
                assert c['controller'].revision == controller.revision
                assert c['piles'].item(0, 3).text().startswith('-')
                assert c['spatial'].text() == 'پیش‌ممیزی سه‌بعدی'
                click('spatial')
                result = json.loads(c['report'].toPlainText())
                assert result['status'] == 'SPATIAL_PREVIEW_ONLY'
                assert result['matched_interfaces'][0]['overlap_volume_m3'] == '0'
                assert result['ready_for_boq'] is False and result['commit_allowed'] is False
                assert c['report'].isReadOnly()
                assert 'ثبت مالی مسدود' in c['message'].text()
                assert app.open_project('P') == before
                # A changed source cannot reuse the prior result.
                with open(path, 'ab') as handle:
                    handle.write(b'\n')
                # The picker hashes current bytes; a malformed numeric token is rejected.
                chosen[0] = _document(tmp_path / 'invalid.json', {**proof, 'links': [
                    {**proof['links'][0], 'pile_center_x_m': 0.5}]})
                QTimer.singleShot(10, dismiss_warning)
                click('spatial')
                assert c['message'].text().startswith('خطا:')
                assert c['report'].toPlainText() == ''
                assert app.open_project('P') == before
            except Exception as exc:
                failures.append(repr(exc))
            finally:
                pile_dialog.reject()

        try:
            controls['kind'].setCurrentIndex(controls['kind'].findData('bored_pile'))
            controls['id'].setText('PG1')
            controls['scroll'].ensureWidgetVisible(controls['pile_specialist'])
            qt.processEvents()
            QTimer.singleShot(20, child)
            QTest.mouseClick(controls['pile_specialist'], Qt.LeftButton)
        except Exception as exc:
            failures.append(repr(exc))
        finally:
            dialog.reject()

    QTimer.singleShot(25, parent)
    open_manual_structural_editor(app, project_id='P', floor_id='FND')
    qt.processEvents()
    assert failures == []
    assert app.store.db.execute('pragma integrity_check').fetchone()[0] == 'ok'
    app.store.close()
    reopened = StructuralProApp(tmp_path / 'db')
    try:
        again = PileDraftController(reopened, 'P')
        again.load('FND', 'PG1')
        assert again.revision == controller.revision
        assert 'spatial_document' not in again.data['pile_detail']
        assert reopened.open_project('P')['boq'] == []
        assert reopened.open_project('P')['takeoffs'] == []
    finally:
        reopened.store.close()
