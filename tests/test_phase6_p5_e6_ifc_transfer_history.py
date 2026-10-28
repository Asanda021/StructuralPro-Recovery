"""Reviewed real IFC ownership: append-only Undo/Redo in canonical SQLite."""
from copy import deepcopy
from decimal import Decimal
import pytest
from test_phase2_priority5_complete import case
from core.platform.application import StructuralProApp
from hashlib import sha256
import json


@pytest.mark.parametrize('mode', ['split', 'merge'])
def test_ifc_transfer_undo_redo_preserves_history_quantities_and_reopen(tmp_path, mode):
    app, args, _, _ = case(tmp_path, mode)
    original = deepcopy(app.open_project('P'))
    transfer = app.apply_ifc_quantity_transfer('P', **args)
    assert hasattr(app, 'undo_ifc_quantity_transfer'), 'canonical IFC transfer has no versioned Undo'
    try:
        for action, expected_revision, expected_owners in [
            ('undo', 1, {r['source_id'] for r in transfer['consumed_rows']}),
            ('redo', 2, {r['source_id'] for r in transfer['rows']}),
        ]:
            token = app.store.current_digest('P')
            kw = dict(transfer_id=transfer['id'], expected_revision=expected_revision,
                author='author', reviewer='reviewer', reason='Explicit synthetic ownership history', expected_digest=token)
            preview = app.preview_ifc_quantity_transfer_step('P', action=action, **kw)
            assert preview['preview_only'] and not preview['commit_allowed']
            assert app.store.current_digest('P') == token
            event = getattr(app, action + '_ifc_quantity_transfer')('P', **kw)
            assert event['group_revision'] == expected_revision + 1
            project = app.open_project('P')
            assert project['takeoffs'] == original['takeoffs']
            assert project['manual_formula_register'] == original['manual_formula_register']
            assert {s for r in project['boq'] for s in r['source_ids']} == expected_owners
            assert sum(Decimal(str(r['quantity'])) for r in project['boq']) == Decimal(2) + Decimal(4)
            assert project['manual_formula_amendments'][transfer['id']] == transfer
            assert app.store.integrity_check()['ok']
            # JSON persistence must not reorder the compensation before its parent.
            app.store.close(); app = StructuralProApp(tmp_path / 'app')
            assert app.open_project('P') == project
            # Collaboration identities are session authentication, not a SQLite
            # credential store. Re-establish the same explicit fixture actors.
            from core.collaboration.workspace import User
            app.collaboration.add_user(User('author', 'Synthetic author', 'editor'))
            app.collaboration.add_user(User('reviewer', 'Synthetic reviewer', 'reviewer'))
        assert len(app.open_project('P')['manual_formula_amendments']) == 3
    finally: app.store.close()


@pytest.mark.parametrize('mode', ['split', 'merge'])
@pytest.mark.parametrize('quantity_name,unit,expected', [('GrossSideArea','m2',Decimal(6)*Decimal('.3')),
    ('GrossVolume','m3',Decimal(6)*Decimal('.2')*Decimal('.3'))])
def test_documented_ifc_surface_and_concrete_volume_shares_conserve_original(tmp_path, mode, quantity_name, unit, expected):
    app,args,_,_=case(tmp_path,mode,quantity_name=quantity_name)
    original=deepcopy(app.open_project('P'));event=app.apply_ifc_quantity_transfer('P',**args)
    try:
        for action,version in [(None,1),('undo',1),('redo',2)]:
            if action:
                getattr(app,action+'_ifc_quantity_transfer')('P',transfer_id=event['id'],expected_revision=version,
                    author='author',reviewer='reviewer',reason='Explicit synthetic face/solid ownership',expected_digest=app.store.current_digest('P'))
            project=app.open_project('P')
            assert {row['unit'] for row in project['boq']}=={unit}
            assert sum(Decimal(str(row['quantity'])) for row in project['boq'])==expected
            assert project['takeoffs']==original['takeoffs']
            assert project['manual_formula_register']==original['manual_formula_register']
        assert event['classification']=='gross'
        assert sum(Decimal(row['quantity']) for row in event['current'])==expected
    finally:app.store.close()
    reopened=StructuralProApp(tmp_path/'app')
    try:assert reopened.open_project('P')==project
    finally:reopened.store.close()


@pytest.mark.parametrize('bad', ['stale_digest', 'stale_revision', 'self_review', 'unknown_actor',
    'proof', 'source', 'redo_before_undo', 'duplicate_undo'])
def test_transfer_history_rejects_expired_or_invalid_authority_without_writes(tmp_path, bad):
    app, args, allocation, _ = case(tmp_path)
    transfer = app.apply_ifc_quantity_transfer('P', **args)
    kw = dict(transfer_id=transfer['id'], expected_revision=1, author='author', reviewer='reviewer',
        reason='Synthetic requested inverse', expected_digest=app.store.current_digest('P'))
    action = 'undo'
    if bad == 'stale_digest': app.add_project_floor('P', 'Concurrent floor', level='F2')
    elif bad == 'stale_revision': kw['expected_revision'] = 0
    elif bad == 'self_review': kw['reviewer'] = 'author'
    elif bad == 'unknown_actor': kw['author'] = 'unknown'
    elif bad == 'proof': allocation.write_text('{}')
    elif bad == 'source':
        path = app.open_project('P')['ifc_identity_reviews'][-1]['document']['source_path']
        with open(path, 'a') as output: output.write('\n/* changed source */')
    elif bad == 'redo_before_undo': action = 'redo'
    else:
        app.undo_ifc_quantity_transfer('P', **kw)
        kw.update(expected_digest=app.store.current_digest('P'), expected_revision=2)
    before = deepcopy(app.open_project('P')); token = app.store.current_digest('P')
    try:
        with pytest.raises((ValueError, RuntimeError, PermissionError)):
            getattr(app, action + '_ifc_quantity_transfer')('P', **kw)
        assert app.store.current_digest('P') == token
        assert app.open_project('P') == before
    finally: app.store.close()
    reopened = StructuralProApp(tmp_path / 'app')
    try: assert reopened.open_project('P') == before
    finally: reopened.store.close()


@pytest.mark.parametrize('amount', ['0', '-1', 'NaN', '7'])
def test_ifc_source_share_cannot_be_zero_nonfinite_or_overallocated(tmp_path, amount):
    app, args, path, data = case(tmp_path)
    data['current'][0]['quantity'] = amount
    path.write_text(json.dumps(data)); args['evidence_sha256'] = sha256(path.read_bytes()).hexdigest()
    before = deepcopy(app.open_project('P')); token = app.store.current_digest('P')
    try:
        with pytest.raises(ValueError): app.apply_ifc_quantity_transfer('P', **args)
        assert app.open_project('P') == before and app.store.current_digest('P') == token
    finally: app.store.close()


def test_ifc_history_sqlite_abort_rolls_back_group_revision_and_boq(tmp_path):
    import sqlite3
    app, args, _, _ = case(tmp_path)
    transfer = app.apply_ifc_quantity_transfer('P', **args)
    before = deepcopy(app.open_project('P')); token = app.store.current_digest('P')
    versions = app.store.db.execute('SELECT count(*) FROM revisions').fetchone()[0]
    app.store.db.execute("CREATE TRIGGER abort_ifc_history BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT,'IFC_HISTORY_TEST_ABORT'); END")
    app.store.db.commit()
    try:
        with pytest.raises(sqlite3.DatabaseError, match='IFC_HISTORY_TEST_ABORT'):
            app.undo_ifc_quantity_transfer('P', transfer_id=transfer['id'], expected_revision=1,
                author='author', reviewer='reviewer', reason='Rollback test', expected_digest=token)
        assert app.open_project('P') == before and app.store.current_digest('P') == token
        assert app.store.db.execute('SELECT count(*) FROM revisions').fetchone()[0] == versions
        assert app.store.integrity_check()['ok']
    finally:
        app.store.db.execute('DROP TRIGGER abort_ifc_history'); app.store.db.commit(); app.store.close()
    reopened = StructuralProApp(tmp_path / 'app')
    try: assert reopened.open_project('P') == before
    finally: reopened.store.close()


def test_native_ifc_history_requires_preview_confirmation_and_displays_owners(tmp_path):
    from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit, QComboBox, QScrollArea, QLabel
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app, args, _, _ = case(tmp_path)
    transfer = app.apply_ifc_quantity_transfer('P', **args)
    qt = QApplication.instance() or QApplication([])
    source = app.open_project('P')['ifc_identity_reviews'][-1]['document']['source_path']
    view = GraphicalTakeoffDialog(app_service=app, project_id='P'); view.show()
    view.open_drawing(source); view.ifc_revision.setText('R2')
    QTest.mouseClick(view.ifc_inspect_button, Qt.MouseButton.LeftButton)
    dialog = view._ifc_inspector
    try:
        preview = dialog.findChild(QPushButton, 'ifc_history_preview')
        assert preview is not None, 'versioned IFC Undo/Redo has no real review controls'
        apply = dialog.findChild(QPushButton, 'ifc_history_apply')
        confirm = dialog.findChild(QPushButton, 'ifc_group_confirm')
        dialog.findChild(QLineEdit, 'ifc_author').setText('author')
        dialog.findChild(QLineEdit, 'ifc_history_reason').setText('Explicit synthetic ownership reversal')
        scroll = dialog.findChild(QScrollArea)
        def click(button):
            scroll.ensureWidgetVisible(button); qt.processEvents()
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        for action, revision in [('undo', 2), ('redo', 3)]:
            selector = dialog.findChild(QComboBox, 'ifc_history_action')
            selector.setCurrentIndex(selector.findData(action))
            token = app.store.current_digest('P')
            click(preview)
            assert app.store.current_digest('P') == token
            click(apply)
            assert app.store.current_digest('P') == token
            click(confirm); click(apply)
            from core.takeoff.manual_formula_amendments import ifc_transfer_head
            _, head = ifc_transfer_head(app.open_project('P'), transfer['id'])
            assert head['group_revision'] == revision, dialog.findChild(QLabel, 'ifc_review_outcome').text()
        assert len(app.open_project('P')['manual_formula_amendments']) == 3
    finally: view.close(); app.store.close(); qt.processEvents()


@pytest.mark.parametrize('bad', ['id', 'reviewer', 'role', 'revision'])
def test_direct_sqlite_command_rejects_corrupted_history_identity_and_review(tmp_path, bad):
    from core.takeoff.manual_formula_amendments import ifc_transfer_step_payload, digest
    from core.takeoff.commit_guards import rebuild_project_boq
    app, args, _, _ = case(tmp_path)
    root = app.apply_ifc_quantity_transfer('P', **args)
    before = deepcopy(app.open_project('P')); token = app.store.current_digest('P')
    payload = ifc_transfer_step_payload(before, transfer_id=root['id'], action='undo', expected_revision=1,
        expected_digest=token, author='author', reviewer='reviewer', reason='Explicit reverse')
    event = dict(payload, id='MA-test-step', status='applied', revision=1, created_at='2026-10-27T00:00:00+00:00',
        review={'reviewer': 'reviewer', 'role': 'reviewer', 'digest': digest(payload)})
    if bad == 'id': event['id'] = root['id']
    elif bad == 'reviewer': event['review']['reviewer'] = 'intruder'
    elif bad == 'role': event['review']['role'] = 'viewer'
    else: event['revision'] = 999
    candidate = deepcopy(before); candidate['manual_formula_amendments']['MA-test-step'] = event
    _, candidate['boq'] = rebuild_project_boq(candidate, candidate['takeoffs'])
    try:
        with pytest.raises(ValueError):
            app.store.save('P', candidate, expected_digest=token,
                manual_formula_command={'action': 'apply_ifc_transfer_step', 'id': 'MA-test-step'})
        assert app.store.current_digest('P') == token and app.open_project('P') == before
    finally: app.store.close()


@pytest.mark.parametrize('change', ['project', 'revision', 'source'])
def test_native_ifc_history_apply_rechecks_live_viewer_context(tmp_path, change):
    from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit, QScrollArea
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app, args, _, _ = case(tmp_path)
    app.apply_ifc_quantity_transfer('P', **args)
    qt = QApplication.instance() or QApplication([])
    source = app.open_project('P')['ifc_identity_reviews'][-1]['document']['source_path']
    view = GraphicalTakeoffDialog(app_service=app, project_id='P'); view.show()
    view.open_drawing(source); view.ifc_revision.setText('R2')
    QTest.mouseClick(view.ifc_inspect_button, Qt.MouseButton.LeftButton)
    dialog = view._ifc_inspector
    def click(name):
        button = dialog.findChild(QPushButton, name)
        dialog.findChild(QScrollArea).ensureWidgetVisible(button); qt.processEvents()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    try:
        dialog.findChild(QLineEdit, 'ifc_author').setText('author')
        dialog.findChild(QLineEdit, 'ifc_history_reason').setText('Synthetic inverse')
        click('ifc_history_preview')
        token = app.store.current_digest('P'); before = deepcopy(app.open_project('P'))
        if change == 'project': view.project_id_input.setText('OTHER')
        elif change == 'revision': view.ifc_revision.setText('R99')
        else: view.open_drawing(str(tmp_path / 'beams-R1.ifc'))
        click('ifc_group_confirm'); click('ifc_history_apply')
        assert app.store.current_digest('P') == token
        assert app.open_project('P') == before
    finally: view.close(); app.store.close(); qt.processEvents()


def test_ifc_inverse_cannot_rewind_a_migrated_crosswalk_without_its_own_contract(tmp_path):
    app,args,_,_=case(tmp_path,crosswalks='dxf')
    proof=tmp_path/'crosswalk-group.json'
    app.migrate_ifc_crosswalk_group('P',lineage_id=args['lineage_id'],evidence_path=str(proof),
        evidence_sha256=sha256(proof.read_bytes()).hexdigest(),author='author',reviewer='reviewer',
        expected_digest=app.store.current_digest('P'))
    transfer=app.apply_ifc_quantity_transfer('P',**dict(args,expected_digest=app.store.current_digest('P')))
    before=deepcopy(app.open_project('P'));token=app.store.current_digest('P')
    try:
        with pytest.raises(ValueError):
            app.undo_ifc_quantity_transfer('P',transfer_id=transfer['id'],expected_revision=1,
                author='author',reviewer='reviewer',reason='No inverse crosswalk review exists',expected_digest=token)
        assert app.open_project('P')==before and app.store.current_digest('P')==token
    finally:app.store.close()


@pytest.mark.parametrize('count', [1, 5, 20])
def test_independent_ifc_groups_preserve_total_and_other_owners_on_undo(tmp_path, count):
    transfers = []
    app = None
    for index in range(count):
        folder = tmp_path / str(index); folder.mkdir()
        identity = None if app is None else (app, tmp_path / '0' / 'source.ifc', tmp_path / '0' / 'mapping.txt')
        app, args, _, _ = case(folder, identity=identity,
            names=(f'G{index}-A', f'G{index}-B', f'G{index}-C'))
        transfers.append(app.apply_ifc_quantity_transfer('P', **args))
    try:
        before = deepcopy(app.open_project('P'))
        assert sum(Decimal(str(row['quantity'])) for row in before['boq']) == count * (Decimal(2) + Decimal(4))
        first = transfers[0]
        app.undo_ifc_quantity_transfer('P', transfer_id=first['id'], expected_revision=1,
            author='author', reviewer='reviewer', reason='Undo one independently measured group', expected_digest=app.store.current_digest('P'))
        after = app.open_project('P')
        assert sum(Decimal(str(row['quantity'])) for row in after['boq']) == count * Decimal(6)
        assert len({source for row in after['boq'] for source in row['source_ids']}) == count * 2 - 1
        assert after['takeoffs'] == before['takeoffs']
        assert after['manual_formula_register'] == before['manual_formula_register']
        assert app.store.integrity_check()['ok']
    finally: app.store.close()
    reopened = StructuralProApp(tmp_path / '0' / 'app')
    try: assert reopened.open_project('P') == after
    finally: reopened.store.close()


def test_crosswalk_migration_rejects_effectively_undone_quantity_ownership(tmp_path):
    app,args,_,_=case(tmp_path,crosswalks='dxf')
    transfer=app.apply_ifc_quantity_transfer('P',**args)
    app.undo_ifc_quantity_transfer('P',transfer_id=transfer['id'],expected_revision=1,
        author='author',reviewer='reviewer',reason='Restore original owners',
        expected_digest=app.store.current_digest('P'))
    before=deepcopy(app.open_project('P'));token=app.store.current_digest('P')
    proof=tmp_path/'crosswalk-group.json'
    try:
        with pytest.raises(ValueError):
            app.migrate_ifc_crosswalk_group('P',lineage_id=args['lineage_id'],evidence_path=str(proof),
                evidence_sha256=sha256(proof.read_bytes()).hexdigest(),author='author',reviewer='reviewer',
                expected_digest=token)
        assert app.open_project('P')==before and app.store.current_digest('P')==token
    finally:app.store.close()
