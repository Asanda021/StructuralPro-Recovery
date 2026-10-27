"""Canonical session navigation uses the original Qt workspace and SQLite."""
from hashlib import sha256
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from core.platform.application import StructuralProApp
from core.drawings.takeoff_session import DrawingTakeoffSession
from app.project_search_panel import ProjectSearchDialog


def test_session_search_opens_exact_original_workspace_without_write(tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    import app.verified_search_navigation as nav
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path/'db'); service.create_project('Session QA','P')
    path=tmp_path/'source.pdf'; pdf=Canvas(str(path));pdf.drawString(20,20,'QA');pdf.save()
    session=DrawingTakeoffSession(str(path));session.add_count(3,page=1,label='explicit count')
    service.save_drawing_takeoff_session('P',session,session_id='SESSION-QA')
    before=service.store.current_digest('P'); views=[]
    def navigate(route,pid,identity):
        assert route=='drawing_session'
        views.append(nav.prepare_verified_drawing_session_view(service,pid,identity))
    panel=ProjectSearchDialog(service,'P',initial_query='SESSION-QA',on_navigate=navigate)
    try:
        assert panel.list.count()==1, 'canonical persisted sessions are missing from search'
        panel.list.setCurrentRow(0);QTest.mouseClick(panel.open_button,Qt.MouseButton.LeftButton)
        assert len(views)==1, panel.status.text()
        view=views[0]
        assert view.persisted_session_id=='SESSION-QA' and view.persisted_session_revision==1
        assert view.session.to_dict()==session.to_dict()
        assert view.viewer.kind=='pdf' and str(view.viewer.path)==str(path)
        assert view.table.rowCount()==1
        assert service.store.current_digest('P')==before
        path.write_bytes(path.read_bytes()+b'changed')
        with pytest.raises(ValueError,match='هش'):
            nav.prepare_verified_drawing_session_view(service,'P','SESSION-QA')
        with pytest.raises((ValueError,KeyError)):
            nav.prepare_verified_drawing_session_view(service,'P','OTHER')
        assert service.store.current_digest('P')==before
        assert not service.open_project('P')['boq']
        reopened=StructuralProApp(tmp_path/'db')
        try:
            assert reopened.store.current_digest('P')==before
            assert DrawingTakeoffSession.from_dict(reopened.load_drawing_takeoff_session('P','SESSION-QA')['session']).to_dict()==session.to_dict()
        finally:reopened.store.close()
    finally:
        panel.close()
        for view in views:view.close()
        service.store.close();qt.processEvents()


def test_dxf_session_restores_original_handles_and_documented_units(tmp_path):
    import ezdxf
    from app.verified_search_navigation import prepare_verified_drawing_session_view
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('DXF QA','P')
    drawing=ezdxf.new('R2018');drawing.header['$INSUNITS']=6
    entity=drawing.modelspace().add_line((0,0),(4,0));path=tmp_path/'plan.dxf';drawing.saveas(path)
    session=DrawingTakeoffSession(str(path))
    service.save_drawing_takeoff_session('P',session,session_id='CAD-QA')
    before=service.store.current_digest('P')
    view=prepare_verified_drawing_session_view(service,'P','CAD-QA')
    try:
        assert view.viewer.kind=='cad'
        assert view.cad_document.units=='m'
        assert view.cad_document.source_sha256==sha256(path.read_bytes()).hexdigest()
        view.cad_handle.setText(entity.dxf.handle)
        QTest.mouseClick(view.cad_find,Qt.MouseButton.LeftButton)
        assert view._cad_handle_items[entity.dxf.handle].isSelected()
        assert service.store.current_digest('P')==before
    finally:view.close();service.store.close();qt.processEvents()


def test_session_route_rejects_stale_and_permission_revocation(tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    from app.verified_search_navigation import prepare_verified_drawing_session_view
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('Permission QA','P')
    path=tmp_path/'source.pdf';pdf=Canvas(str(path));pdf.save()
    service.save_drawing_takeoff_session('P',DrawingTakeoffSession(str(path)),session_id='S')
    calls=[];panel=ProjectSearchDialog(service,'P',initial_query='S',on_navigate=lambda *args:calls.append(args))
    try:
        index=next(i for i,r in enumerate(panel.results) if r['kind']=='drawing_session')
        panel.list.setCurrentRow(index)
        service.add_project_floor('P','Changed',level='F1')
        assert panel.open_record() is None and not calls
        service.store.db.execute('DELETE FROM project_acl WHERE project_id=?',('P',))
        service.store.db.commit()
        with pytest.raises(PermissionError):prepare_verified_drawing_session_view(service,'P','S')
    finally:panel.close();service.store.close();qt.processEvents()
