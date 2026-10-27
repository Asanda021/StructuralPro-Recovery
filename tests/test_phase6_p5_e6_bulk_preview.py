"""E6 preview uses the existing Decimal formula engine and canonical CAS."""
import pytest
from decimal import Decimal
from core.platform.application import StructuralProApp
from test_manual_formula_persistence import data


def test_bulk_preview_includes_unselected_dependency_changes_and_revisions(tmp_path):
    service = StructuralProApp(tmp_path / 'db'); service.create_project('Dependency preview', 'P')
    service.save_manual_formula('P', 'A', data(), expected_revision=0, reason='Synthetic input')
    for key, factor in [('B', '2'), ('C', '3')]:
        service.save_manual_formula('P', key, data(member=key, source_id='measured:' + key,
            expression='base*factor', references={'base': 'A'}, variables={'factor': factor},
            variable_units={'factor': 'عدد'}), expected_revision=0, reason='Explicit dependency')
    before = service.open_project('P'); digest = service.store.current_digest('P')
    try:
        preview = service.preview_bulk_edit_manual_formulas('P', ['A'],
            changes={'variables': {'length': '5'}}, expected_revisions={'A': 1})
        rows = {r['row_id']: r for r in preview['rows']}
        assert set(rows) == {'A', 'B', 'C'}
        for key, old, new in [('A', '6', '3'), ('B', '12', '6'), ('C', '18', '9')]:
            assert Decimal(rows[key]['old_quantity']) == Decimal(old)
            assert Decimal(rows[key]['new_quantity']) == Decimal(new)
            assert rows[key]['revision'] == 1
        assert service.store.current_digest('P') == digest
        assert service.open_project('P') == before
        service.bulk_edit_manual_formulas('P', ['A'], changes={'variables': {'length': '5'}},
            expected_revisions={'A': 1}, expected_digest=preview['cas_digest'], reason='Reviewed dependency closure')
        for operation, total in [(None, 18), ('undo_manual_formulas', 36), ('redo_manual_formulas', 18)]:
            if operation: getattr(service, operation)('P')
            register = service.load_manual_formulas('P')
            assert set(register) == {'A', 'B', 'C'}
            assert sum(Decimal(str(r['quantity'])) for r in register.values()) == total
            assert all(r['revision'] >= 2 for r in register.values())
            assert not service.open_project('P')['boq']
        snapshot = service.open_project('P'); final_digest = service.store.current_digest('P')
    finally: service.store.close()
    reopened = StructuralProApp(tmp_path / 'db')
    try:
        assert reopened.open_project('P') == snapshot
        assert reopened.store.current_digest('P') == final_digest
    finally: reopened.store.close()


def test_native_bulk_confirmation_displays_dependent_rows_and_no_is_read_only(tmp_path):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from app.manual_takeoff import ManualTakeoffDialog
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / 'db'); service.create_project('Native bulk preview', 'P')
    service.save_manual_formula('P', 'A', data(), expected_revision=0, reason='Explicit input')
    service.save_manual_formula('P', 'B', data(member='B', source_id='measured:B', expression='base*2',
        variables={}, variable_units={}, references={'base': 'A'}), expected_revision=0, reason='Dependency')
    dialog = ManualTakeoffDialog(service, 'P'); dialog.show(); dialog.manual_tabs.setCurrentIndex(1)
    qt.processEvents()
    assert dialog.formula_table.item(0, 0).text() == 'A'
    dialog.formula_bulk_name.setText('length'); dialog.formula_bulk_value.setText('5')
    dialog.formula_reason.setText('Explicit length revision')
    dialog.formula_bulk_name.setFocus(); qt.processEvents()
    QTest.mouseClick(dialog.formula_table.viewport(), Qt.MouseButton.LeftButton,
        pos=dialog.formula_table.visualItemRect(dialog.formula_table.item(0, 0)).center())
    qt.processEvents()
    digest = service.store.current_digest('P'); messages = []
    watcher = QTimer(dialog)
    def reject():
        message = qt.activeModalWidget()
        if isinstance(message, QMessageBox):
            messages.append(message.text())
            QTest.mouseClick(message.button(QMessageBox.StandardButton.No), Qt.MouseButton.LeftButton)
    watcher.timeout.connect(reject); watcher.start(20)
    try:
        QTest.mouseClick(dialog.formula_bulk_button, Qt.MouseButton.LeftButton)
        assert len(messages) == 1, dialog.status.text()
        assert 'A | 6 → 3' in messages[0] and 'B | 12 → 6' in messages[0]
        assert service.store.current_digest('P') == digest
        assert not service.open_project('P')['boq']
    finally: watcher.stop(); dialog.close(); service.store.close(); qt.processEvents()


def test_bulk_apply_requires_the_preview_project_digest_when_supplied(tmp_path):
    service = StructuralProApp(tmp_path / 'db'); service.create_project('CAS preview', 'P')
    service.save_manual_formula('P', 'A', data(), expected_revision=0, reason='Synthetic input')
    preview = service.preview_bulk_edit_manual_formulas('P', ['A'],
        changes={'variables': {'length': '5'}}, expected_revisions={'A': 1})
    concurrent = StructuralProApp(tmp_path / 'db')
    try:
        concurrent.add_project_floor('P', 'Concurrent floor', level='F2')
        digest = service.store.current_digest('P'); before = service.open_project('P')
        with pytest.raises(RuntimeError):
            service.bulk_edit_manual_formulas('P', ['A'], changes={'variables': {'length': '5'}},
                expected_revisions={'A': 1}, expected_digest=preview['cas_digest'], reason='Stale preview')
        assert service.store.current_digest('P') == digest
        assert service.open_project('P') == before
    finally: concurrent.store.close(); service.store.close()


def test_bulk_preview_cannot_invalidate_committed_dependency_even_if_quantity_equal(tmp_path):
    service = StructuralProApp(tmp_path / 'db'); service.create_project('Equal quantity, different evidence', 'P')
    service.save_manual_formula('P', 'A', data(), expected_revision=0, reason='Synthetic dimensions')
    service.save_manual_formula('P', 'B', data(member='B', source_id='measured:B', expression='base',
        references={'base': 'A'}, variables={}, variable_units={}), expected_revision=0, reason='Dependency')
    service.review_manual_formula('P', 'B', expected_revision=1, reviewer='Engineer', note='Explicit review')
    service.commit_manual_formula('P', 'B', expected_revision=1)
    digest = service.store.current_digest('P')
    try:
        with pytest.raises(ValueError):
            service.preview_bulk_edit_manual_formulas('P', ['A'],
                changes={'variables': {'length': '5', 'width': '0.4'}}, expected_revisions={'A': 1})
        assert service.store.current_digest('P') == digest
    finally: service.store.close()


@pytest.mark.parametrize('count', [1, 5, 20])
def test_bulk_independent_member_totals_undo_redo_and_reopen(tmp_path, count):
    service = StructuralProApp(tmp_path / 'db'); service.create_project('Independent quantities', 'P')
    keys = [f'C{i}' for i in range(count)]
    for key in keys:
        service.save_manual_formula('P', key, data(member=key, source_id='measured:' + key),
            expected_revision=0, reason='Explicit dimensions 10 x .2 x 3')
    try:
        preview = service.preview_bulk_edit_manual_formulas('P', keys, changes={'variables': {'length': '5'}},
            expected_revisions={key: 1 for key in keys})
        assert sum(Decimal(r['old_quantity']) for r in preview['rows']) == Decimal(count) * 10 * Decimal('.2') * 3
        assert sum(Decimal(r['new_quantity']) for r in preview['rows']) == Decimal(count) * 5 * Decimal('.2') * 3
        service.bulk_edit_manual_formulas('P', keys, changes={'variables': {'length': '5'}},
            expected_revisions={key: 1 for key in keys}, expected_digest=preview['cas_digest'], reason='Explicit new length')
        for operation, total in [(None, count * 3), ('undo_manual_formulas', count * 6), ('redo_manual_formulas', count * 3)]:
            if operation: getattr(service, operation)('P')
            register = service.load_manual_formulas('P')
            assert len(register) == count
            assert sum(Decimal(str(r['quantity'])) for r in register.values()) == total
            assert all(r['revision'] >= 2 and r['status'] == 'draft' for r in register.values())
            assert not service.open_project('P')['boq']
        project = service.open_project('P'); digest = service.store.current_digest('P')
        assert service.store.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally: service.store.close()
    reopened = StructuralProApp(tmp_path / 'db')
    try:
        assert reopened.open_project('P') == project
        assert reopened.store.current_digest('P') == digest
    finally: reopened.store.close()


def test_documented_opening_is_deducted_once_bulk_undo_redo_reopen(tmp_path):
    from copy import deepcopy
    service=StructuralProApp(tmp_path/'db');service.create_project('دیوار مصنوعی','P')
    wall=data(family='block_wall',title='دیوار بلوکی مصنوعی',member='W1',unit='m2',expression='length*height-opening',
        variables={'length':'4','height':'3','opening':'2'},
        variable_units={'length':'m','height':'m','opening':'m2'},source_id='wall:W1',
        deductions=[{'id':'O1','variable':'opening','quantity':'2','unit':'m2',
                     'basis':'بازشوی مصنوعی یک در دو متر','source_id':'opening:O1'}])
    service.save_manual_formula('P','W1',wall,expected_revision=0,reason='نمونه صریح')
    digest=service.store.current_digest('P')
    preview=service.preview_bulk_edit_manual_formulas('P',['W1'],changes={'variables':{'length':'5'}},expected_revisions={'W1':1})
    assert preview['rows'][0]['old_quantity']=='10' and preview['rows'][0]['new_quantity']=='13'
    assert service.store.current_digest('P')==digest
    duplicate=deepcopy(wall);duplicate['member']='W2';duplicate['source_id']='wall:W2'
    with pytest.raises(ValueError):service.save_manual_formula('P','W2',duplicate,expected_revision=0,reason='کسر تکراری باید رد شود')
    assert service.store.current_digest('P')==digest
    for operation in ('split','merge','ownership'):
        with pytest.raises(ValueError):
            service.bulk_edit_manual_formulas('P',['W1'],changes={operation:True},expected_revisions={'W1':1},reason='عملیات فاقد قرارداد رسمی')
    service.bulk_edit_manual_formulas('P',['W1'],changes={'variables':{'length':'5'}},expected_revisions={'W1':1},reason='طول صریح جدید')
    assert Decimal(str(service.load_manual_formulas('P')['W1']['quantity']))==13
    service.undo_manual_formulas('P');assert Decimal(str(service.load_manual_formulas('P')['W1']['quantity']))==10
    service.redo_manual_formulas('P');assert Decimal(str(service.load_manual_formulas('P')['W1']['quantity']))==13
    project=service.open_project('P');assert not project['boq']
    assert len(project['manual_formula_register'])==1
    assert project['manual_formula_register']['W1']['data']['deductions']==wall['deductions']
    service.store.close()
    reopened=StructuralProApp(tmp_path/'db')
    try:assert reopened.open_project('P')==project
    finally:reopened.store.close()


def test_bulk_sqlite_abort_preserves_all_rows_history_and_reopen(tmp_path):
    """SQLite trigger aborts the real transaction, not a mocked service save."""
    import sqlite3
    service=StructuralProApp(tmp_path/'db');service.create_project('قطع تراکنش','P')
    for key in ('A','B'):
        service.save_manual_formula('P',key,data(member=key,source_id='measured:'+key),
                                    expected_revision=0,reason='نمونه مصنوعی صریح')
    before=service.open_project('P');digest=service.store.current_digest('P')
    versions=service.store.db.execute('SELECT count(*) FROM revisions').fetchone()[0]
    service.store.db.execute("CREATE TRIGGER qa_abort_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT,'QA_REAL_TRANSACTION_ABORT'); END")
    service.store.db.commit()
    try:
        with pytest.raises(sqlite3.DatabaseError,match='QA_REAL_TRANSACTION_ABORT'):
            service.bulk_edit_manual_formulas('P',['A','B'],changes={'variables':{'length':'5'}},
                expected_revisions={'A':1,'B':1},reason='آزمون شکست عمدی SQLite')
        assert service.open_project('P')==before
        assert service.store.current_digest('P')==digest
        assert service.store.db.execute('SELECT count(*) FROM revisions').fetchone()[0]==versions
        assert service.store.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:
        service.store.db.execute('DROP TRIGGER qa_abort_revision');service.store.db.commit();service.store.close()
    reopened=StructuralProApp(tmp_path/'db')
    try:
        assert reopened.open_project('P')==before
        assert reopened.store.current_digest('P')==digest
        assert not reopened.open_project('P')['boq']
    finally:reopened.store.close()


def test_twenty_columns_preview_no_write_then_existing_bulk_apply(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("کنترل ۲۰ ستون","P")
    keys=[]
    for i in range(20):
        key=f"C{i+1}"
        app.save_manual_formula("P",key,data(member=key,source_id="measured:"+key),
                                expected_revision=0,reason="ورودی مستند آزمایشی")
        keys.append(key)
    expected={key:1 for key in keys}
    before=app.open_project("P")
    digest=app.store.current_digest("P")
    preview=app.preview_bulk_edit_manual_formulas("P",keys,changes={"variables":{"length":"5"}},
                                                   expected_revisions=expected)
    assert len(preview["rows"])==20 and preview["preview_only"] and not preview["boq_write"]
    assert all(x["old_quantity"]=="6" and x["new_quantity"]=="3" for x in preview["rows"])
    assert app.store.current_digest("P")==digest
    assert app.open_project("P")==before
    app.bulk_edit_manual_formulas("P",keys,changes={"variables":{"length":"5"}},
                                 expected_revisions=expected,reason="تغییر مستند گروهی")
    updated=app.load_manual_formulas("P")
    assert all(Decimal(str(updated[key]["quantity"]))==Decimal("3") for key in keys)
    assert app.open_project("P")["boq"]==[]
    with pytest.raises(RuntimeError):
        app.preview_bulk_edit_manual_formulas("P",keys,changes={"variables":{"length":"1"}},
                                               expected_revisions=expected)
    app.store.close()


@pytest.mark.parametrize("changes",[
    {"variables":{"not_present":"1"}},
    {"member":"HACK"},
    {"unit":"m2"},
    {"variable_units":{"unknown":"m"}},
])
def test_group_preview_rejects_hidden_identity_or_unknown_fields(tmp_path,changes):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("کنترل","P")
    app.save_manual_formula("P","A",data(),expected_revision=0,reason="ورودی")
    digest=app.store.current_digest("P")
    with pytest.raises(ValueError):
        app.preview_bulk_edit_manual_formulas("P",["A"],changes=changes,
                                               expected_revisions={"A":1})
    assert app.store.current_digest("P")==digest
    app.store.close()


def test_committed_row_is_not_bulk_modified(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("کنترل","P")
    app.save_manual_formula("P","A",data(),expected_revision=0,reason="اول")
    app.review_manual_formula("P","A",expected_revision=1,reviewer="مهندس",note="کنترل")
    app.commit_manual_formula("P","A",expected_revision=1)
    digest=app.store.current_digest("P")
    with pytest.raises(ValueError):
        app.preview_bulk_edit_manual_formulas("P",["A"],changes={"variables":{"length":"4"}},
                                               expected_revisions={"A":1})
    assert app.store.current_digest("P")==digest
    app.store.close()

def test_twenty_member_bulk_undo_redo_uses_original_guarded_history(tmp_path):
    from decimal import Decimal
    app=StructuralProApp(tmp_path/"data")
    app.create_project("ویرایش گروهی","P")
    keys=[]
    for i in range(20):
        key=f"C{i+1}"
        app.save_manual_formula("P",key,data(member=key,source_id="measured:"+key),
                                expected_revision=0,reason="ورودی صریح")
        keys.append(key)
    app.bulk_edit_manual_formulas("P",keys,changes={"variables":{"length":"5"}},
                                 expected_revisions={key:1 for key in keys},
                                 reason="تغییر گروهی")
    assert all(Decimal(str(app.load_manual_formulas("P")[k]["quantity"]))==3 for k in keys)
    app.undo_manual_formulas("P")
    assert all(Decimal(str(app.load_manual_formulas("P")[k]["quantity"]))==6 for k in keys)
    app.redo_manual_formulas("P")
    assert all(Decimal(str(app.load_manual_formulas("P")[k]["quantity"]))==3 for k in keys)
    assert app.open_project("P")["boq"]==[]
    app.store.close()


def test_bulk_change_after_other_writer_invalidates_preview_digest(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("هم‌زمان","P")
    app.save_manual_formula("P","A",data(),expected_revision=0,reason="اول")
    preview=app.preview_bulk_edit_manual_formulas("P",["A"],
        changes={"variables":{"length":"7"}},expected_revisions={"A":1})
    concurrent=StructuralProApp(tmp_path/"data")
    concurrent.add_project_floor("P","دوم",level="F2")
    assert app.store.current_digest("P")!=preview["cas_digest"]
    with pytest.raises(RuntimeError):
        app.bulk_edit_manual_formulas("P",["A"],
            changes={"variables":{"length":"7"}},
            expected_revisions={"A":0},reason="نسخه قدیمی")
    assert app.open_project("P")["boq"]==[]
    concurrent.store.close();app.store.close()


def test_group_preview_rejects_ifc_evidence_tamper_without_writes(tmp_path):
    app=StructuralProApp(tmp_path/"data")
    app.create_project("آزمون حفاظت","P")
    # A generic row cannot become IFC-approved merely by tagging an
    # unreviewed identity. The canonical validator must fail closed.
    source=data(member="C1",source_id="measured:test")
    source["ifc_evidence"]={"proposal_id":"forged","quantity_name":"NetVolume",
                            "author":"intruder"}
    with pytest.raises((ValueError,KeyError,PermissionError)):
        app.save_manual_formula("P","A",source,expected_revision=0,reason="مدرک جعلی")
    assert app.open_project("P")["boq"]==[]
    app.store.close()
