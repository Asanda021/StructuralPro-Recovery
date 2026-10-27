"""E4 Qt real browse and CAS invalidation, no BOQ mutation."""
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import pytest
from core.platform.application import StructuralProApp
from app.project_search_panel import ProjectSearchDialog


def test_search_duplicate_member_identity_is_not_resolved_by_matching_title(tmp_path):
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / 'db'); service.create_project('Ambiguous search', 'P')
    project = service.open_project('P')
    project['members'] = [
        {'id': 'M1', 'floor_id': 'F1', 'kind': 'column', 'title': 'ستون شمالی', 'revision': 'R1'},
        {'id': 'M1', 'floor_id': 'F2', 'kind': 'column', 'title': 'ستون جنوبی', 'revision': 'R2'},
    ]
    service.store.save('P', project, expected_digest=service.store.current_digest('P'))
    digest = service.store.current_digest('P'); calls = []
    panel = ProjectSearchDialog(service, 'P', initial_query='شمالی', on_navigate=lambda *args: calls.append(args))
    try:
        assert panel.list.count() == 1
        panel.list.setCurrentRow(0)
        QTest.mouseClick(panel.open_button, Qt.MouseButton.LeftButton)
        assert not calls
        assert 'مبهم' in panel.status.text()
        assert service.store.current_digest('P') == digest
        assert not service.open_project('P')['boq']
    finally:
        panel.close(); service.store.close(); qt.processEvents()


def test_search_floor_opens_and_selects_actual_inspector_node(tmp_path):
    from PySide6.QtWidgets import QMainWindow
    from PySide6.QtCore import QSettings
    from app.workspace_docks import WorkspaceDockController
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / 'db'); service.create_project('Floor navigation', 'P')
    service.add_project_floor('P', 'طبقه بیست', level='F20')
    window = QMainWindow(); window.show()
    controller = WorkspaceDockController(window, QSettings(str(tmp_path / 'ui.ini'), QSettings.IniFormat), service, lambda: 'P')
    calls = []
    search = ProjectSearchDialog(service, 'P', initial_query='طبقه بیست',
        on_navigate=lambda route, pid, identity: calls.append(controller.focus_project_record(identity)))
    digest = service.store.current_digest('P')
    try:
        search.list.setCurrentRow(0)
        QTest.mouseClick(search.open_button, Qt.MouseButton.LeftButton)
        assert calls == [True], search.status.text()
        selected = controller.tree.selectedItems()
        assert len(selected) == 1
        kind, record = selected[0].data(0, Qt.ItemDataRole.UserRole)
        assert kind == 'floor' and record['id'] == 'F20'
        assert controller.dock.isVisible()
        assert service.store.current_digest('P') == digest
    finally: search.close(); window.close(); service.store.close(); qt.processEvents()


def test_search_floor_member_route_collision_is_not_guessed(tmp_path):
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / 'db'); service.create_project('Route identity', 'P')
    service.add_project_floor('P', 'طبقه اول', level='X1')
    service.add_project_member('P', 'X1', 'X1', 'column')
    calls = []
    search = ProjectSearchDialog(service, 'P', initial_query='طبقه اول', on_navigate=lambda *args: calls.append(args))
    digest = service.store.current_digest('P')
    try:
        search.list.setCurrentRow(0)
        QTest.mouseClick(search.open_button, Qt.MouseButton.LeftButton)
        assert not calls
        assert 'مبهم' in search.status.text()
        assert service.store.current_digest('P') == digest
    finally: search.close(); service.store.close(); qt.processEvents()


def test_search_live_member_and_stale_fails_closed(tmp_path):
    qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path/"app")
    app.create_project("پروژه اصلی","P")
    app.add_project_floor("P","طبقه ۲",level="F2")
    app.add_project_member("P","M12","F2","column")
    before=app.store.current_digest("P")
    navigated=[]
    panel=ProjectSearchDialog(app,"P",initial_query="M12",
                              on_navigate=lambda *args:navigated.append(args))
    try:
        assert panel.list.count()>=1
        panel.list.setCurrentRow(0)
        QTest.mouseClick(panel.open_button,Qt.MouseButton.LeftButton)
        assert '"M12"' in panel.detail.toPlainText()
        assert navigated==[("projects","P","M12")]
        assert app.store.current_digest("P")==before
        app.add_project_floor("P","طبقه ۳",level="F3")
        assert panel.open_record() is None
        assert not panel.open_button.isEnabled()
        assert app.open_project("P")["boq"]==[]
    finally:
        panel.close();app.store.close();qt.processEvents()


def test_search_does_not_read_other_project(tmp_path):
    qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path/"app")
    app.create_project("پروژه یک","P1")
    app.create_project("پروژه محرمانه","P2")
    dialog=ProjectSearchDialog(app,"P1",initial_query="محرمانه")
    try:
        assert dialog.list.count()==0
        assert dialog.open_record() is None
        assert app.open_project("P2")["name"]=="پروژه محرمانه"
    finally:
        dialog.close();app.store.close();qt.processEvents()

def test_boq_navigation_selects_exact_stored_row_without_financial_recalc(tmp_path):
    from PySide6.QtWidgets import QApplication,QTableWidget
    from app.project_search_panel import display_verified_boq_row
    qt=QApplication.instance() or QApplication([])
    table=QTableWidget(0,6)
    project={"id":"P","boq":[
        {"row_id":"B1","description":"دیوار","quantity":"13.00","unit":"m2"},
        {"row_id":"B2","description":"سقف","quantity":"2.50","unit":"m3"},
    ]}
    before=repr(project)
    assert display_verified_boq_row(project,"B2",table)==1
    assert table.currentRow()==1
    assert table.item(1,1).text()=="سقف"
    assert table.item(1,2).text()=="2.50"
    assert table.item(1,5).text()=="بدون مبلغ مصوب"
    assert repr(project)==before
    table.close();qt.processEvents()


def test_boq_duplicate_identity_refused_without_changing_table(tmp_path):
    import pytest
    from PySide6.QtWidgets import QApplication,QTableWidget
    from app.project_search_panel import display_verified_boq_row
    qt=QApplication.instance() or QApplication([])
    table=QTableWidget(0,6)
    project={"id":"P","boq":[{"row_id":"B1","description":"الف"},
                             {"row_id":"B1","description":"ب"}]}
    with pytest.raises(ValueError):
        display_verified_boq_row(project,"B1",table)
    assert table.rowCount()==0
    table.close();qt.processEvents()


def test_search_to_verified_ifc_real_source_and_fourway_selection(tmp_path):
    from test_phase6_p3_real_project_bridge import reviewed
    from app.verified_search_navigation import prepare_verified_member_view
    app,path,proof,proposal=reviewed(tmp_path)
    qt=QApplication.instance() or QApplication([])
    before=app.store.current_digest("P")
    viewer=prepare_verified_member_view(app,"P","B1")
    try:
        assert viewer._ifc_selected_global_id==proposal["global_id"]
        assert viewer._verified_selection_panel.members.selectedItems()[0].text(0)=="B1"
        assert viewer.viewer.kind=="ifc"
        assert app.store.current_digest("P")==before
        assert app.open_project("P")["boq"]==[]
    finally:
        viewer._verified_selection_dialog.close()
        viewer.close();qt.processEvents();app.store.close()


def test_search_to_verified_ifc_rejects_missing_review_and_tampered_file(tmp_path):
    from test_phase2_priority5_closure import identity_case
    from test_phase6_p3_real_project_bridge import reviewed
    from app.verified_search_navigation import reviewed_member_source
    app,path,proof,proposal,args=identity_case(tmp_path)
    with pytest.raises(ValueError):
        reviewed_member_source(app,"P","B1")
    app.store.close()
    folder=tmp_path/"reviewed"
    folder.mkdir()
    app,path,proof,proposal=reviewed(folder)
    proof.write_text("tampered",encoding="utf8")
    # Document SHA may still exist; independent proof is verified by live
    # VerifiedProjectSelection on actual opening, never bypassed.
    from app.verified_search_navigation import prepare_verified_member_view
    with pytest.raises((ValueError, RuntimeError)):
        prepare_verified_member_view(app,"P","B1")
    app.store.close()
def test_search_opens_exact_document_only_with_live_sha_and_revision(tmp_path):
    from PySide6.QtWidgets import QApplication
    from core.platform.application import StructuralProApp
    from hashlib import sha256
    from reportlab.pdfgen.canvas import Canvas
    import app.verified_search_navigation as navigation
    import pytest
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('اسناد','P')
    path=tmp_path/'plan.pdf';c=Canvas(str(path));c.drawString(30,30,'synthetic QA document');c.save()
    project=service.open_project('P')
    project['drawings']=[{'id':'D1','name':'پلان آزمایشی','path':str(path),
                          'source_sha256':sha256(path.read_bytes()).hexdigest(),'revision':'R1'}]
    service.store.save('P',project,expected_digest=service.store.current_digest('P'))
    try:
        assert hasattr(navigation,'prepare_verified_drawing_view'), 'document search has no exact source handoff'
        before=service.store.current_digest('P')
        view=navigation.prepare_verified_drawing_view(service,'P','D1')
        assert view.viewer.kind=='pdf'
        assert str(view.viewer.path)==str(path)
        view.close();qt.processEvents()
        assert before==service.store.current_digest('P')
        path.write_bytes(path.read_bytes()+b'changed')
        with pytest.raises(ValueError,match='هش'):
            navigation.prepare_verified_drawing_view(service,'P','D1')
        with pytest.raises(ValueError):
            navigation.prepare_verified_drawing_view(service,'P','OTHER')
        assert before==service.store.current_digest('P')
    finally:service.store.close();qt.processEvents()

def test_search_wbs_and_activity_focus_original_workspace_without_write(tmp_path):
    from PySide6.QtWidgets import QApplication
    from core.platform.application import StructuralProApp
    from test_phase4_structure import structure,activity
    from core.search.global_search import search_project
    import app.verified_search_navigation as navigation
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('کنترل','P');structure(service);activity(service)
    try:
        assert any(r['entity_id']=='W1' for r in search_project(service.open_project('P'),'اسکلت')), 'canonical project_wbs is missing from search'
        assert hasattr(navigation,'prepare_verified_controls_view'), 'WBS navigation does not focus the selected record'
        before=service.store.current_digest('P')
        from app.project_search_panel import ProjectSearchDialog
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        for identifier,query in (('A','بتن‌ریزی'),('W1','اسکلت')):
            opened=[]
            search=ProjectSearchDialog(service,'P',initial_query=query,
                on_navigate=lambda route,pid,identity:opened.append(navigation.prepare_verified_controls_view(service,pid,identity)))
            search.show();search.list.setCurrentRow(0)
            QTest.mouseClick(search.open_button,Qt.MouseButton.LeftButton)
            assert len(opened)==1,search.status.text()
            view=opened[0]
            if identifier=='A':assert view.selected_id=='A' and view.fields['activity_id'].text()=='A'
            else:assert view.fields['structure_id'].text()=='W1'
            view.close();search.close();qt.processEvents()
        import pytest
        with pytest.raises(ValueError):navigation.prepare_verified_controls_view(service,'P','MISSING')
        assert before==service.store.current_digest('P')
    finally:service.store.close();qt.processEvents()

def test_search_manual_formula_opens_same_record_in_original_editor(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from core.platform.application import StructuralProApp
    from test_manual_formula_persistence import data
    from app.project_search_panel import ProjectSearchDialog
    import app.verified_search_navigation as navigation
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('جستجوی متره','P')
    service.save_manual_formula('P','ROW1',data(title='عنوان یکتای آزمایشی'),expected_revision=0,reason='ورودی صریح')
    opened=[]
    search=ProjectSearchDialog(service,'P',initial_query='عنوان یکتای آزمایشی',
        on_navigate=lambda route,pid,identity:opened.append(navigation.prepare_verified_formula_view(service,pid,identity)))
    try:
        assert search.results and search.results[0]['entity_id']=='ROW1', 'formula register key is lost from navigation identity'
        before=service.store.current_digest('P');search.show();search.list.setCurrentRow(0)
        QTest.mouseClick(search.open_button,Qt.MouseButton.LeftButton)
        assert len(opened)==1,search.status.text()
        view=opened[0];assert view._formula_selected=='ROW1'
        assert view.formula_id.text()=='ROW1' and view._formula_revision==1
        assert before==service.store.current_digest('P')
    finally:
        for view in opened:view.close()
        search.close();service.store.close();qt.processEvents()

def test_report_without_specialist_handoff_stays_explicitly_read_only(tmp_path):
    from PySide6.QtWidgets import QApplication
    from core.platform.application import StructuralProApp
    from app.project_search_panel import ProjectSearchDialog
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('گزارش','P')
    project=service.open_project('P');project['reports']=[{'id':'R1','title':'گزارش فاقد مسیر تخصصی'}]
    service.store.save('P',project,expected_digest=service.store.current_digest('P'))
    calls=[];search=ProjectSearchDialog(service,'P',initial_query='فاقد مسیر تخصصی',on_navigate=lambda *args:calls.append(args))
    try:
        search.list.setCurrentRow(0);assert search.open_record() is not None
        assert not calls, 'unsupported report must not masquerade as an opened specialist record'
        assert 'فقط‌خواندنی' in search.status.text()
    finally:search.close();service.store.close();qt.processEvents()

