"""Published IFC4 ceiling surface interoperability example; no engineering/QTO approval."""
import hashlib,json,os,shutil,time
from pathlib import Path
from urllib.request import urlopen
import pytest

UPSTREAM='7ddf57a201f88a0c213d5322b02ed15e94a60a40'
SOURCE_PATH='IFC 4.0.2.1 (IFC 4)/Example project location/example project location.ifc'
SHA='2c12c00c675e43fb872af8bec583c29e887e75a40c614d8585abcc2baf7590ed'
BLOB='a92907767b710f716aa86d3bba3ba83233106bcd'

@pytest.fixture(scope='module')
def published_source(tmp_path_factory):
    path=tmp_path_factory.mktemp('published-electrical')/'source.ifc'
    with urlopen('https://media.githubusercontent.com/media/buildingsmart-community/Community-Sample-Test-Files/'+UPSTREAM+'/'+__import__('urllib.parse',fromlist=['quote']).quote(SOURCE_PATH),timeout=60) as r:
        data=r.read(4000000)
    assert len(data)==2959580 and hashlib.sha256(data).hexdigest()==SHA
    path.write_bytes(data)
    return path


def test_original_qprocess_and_actual_ceiling_surface_member_pick(published_source):
    import ifcopenshell
    from PySide6.QtCore import QPoint,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    model=ifcopenshell.open(str(published_source));assert model.schema=='IFC4'
    target=model.by_type('IfcCovering');assert len(target)==16 and all(x.PredefinedType=='CEILING' for x in target)
    gid=target[0].GlobalId
    qt=QApplication.instance() or QApplication([]);window=GraphicalTakeoffDialog()
    output=Path(os.environ.get('P6_COVERING_EVIDENCE','covering-evidence'));output.mkdir(exist_ok=True)
    def await_done(test,seconds=60):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            qt.processEvents()
            if test():return
            QTest.qWait(10)
        raise AssertionError('bounded original GUI worker timeout')
    try:
        window.ifc_revision.setText('COMMUNITY-'+UPSTREAM[:12]);window.show()
        window.open_cad_async(published_source);await_done(lambda:window._cad_job is None)
        assert window.viewer.kind=='ifc',window.status.text()
        assert len(window.viewer.ifc_document.source_roster)==550
        assert window.viewer.ifc_document.source_sha256==SHA
        window.open_ifc_3d();await_done(lambda:window._ifc_3d_loader is None)
        view=window._ifc_3d_dialog;assert view is not None,window.status.text()
        view.batch_type.setCurrentIndex(view.batch_type.findData('IfcCovering'))
        ids=view._filtered_batch_ids();assert len(ids)==16 and gid in ids
        view.batch_size.setValue(1);view.batch_page.setValue(ids.index(gid)+1)
        assert view.request_selected_batch()
        await_done(lambda:window._ifc_3d_loader is None)
        assert {m.global_id for m in view.scene.meshes}=={gid}
        view.show();qt.processEvents();picked=False
        for face in view.canvas._faces():
            x=sum(p[0] for p in face.points)/3;y=sum(p[1] for p in face.points)/3
            if view.scene.pick(x,y,view.canvas.width(),view.canvas.height())==gid:
                QTest.mouseClick(view.canvas,Qt.MouseButton.LeftButton,pos=QPoint(round(x),round(y)))
                qt.processEvents();picked=view.canvas.selected_id==gid
                if picked:break
        assert picked
        assert not view.scene.quantity_authority and not window.session.items
        assert view.grab().save(str(output/'actual-ceiling-surface.png'))
        (output/'source-verified.json').write_text(json.dumps(dict(
            source_commit=UPSTREAM,source_path=SOURCE_PATH,source_sha256=SHA,source_git_lfs_pointer_blob=BLOB,
            source_license='CC BY 4.0; buildingSMART Community Sample Test Files',
            total_source_elements=550,target_type='IfcCovering',predefined_type='CEILING',explicit_ceiling_count=16,selected_global_id=gid,
            source_roster_count=550,raw_source_redistributed=False,boq_written=False,
            category='published ceiling surface example; not evidence for paint/plaster/tile/insulation semantics',
            status='PASS_ORIGINAL_QPROCESS_BATCH_AND_NATIVE_QT_PICK'),indent=2),encoding='utf-8')
    finally:
        window.cancel_ifc_3d_loading();window.cancel_cad_loading()
        view=getattr(window,'_ifc_3d_dialog',None)
        if view is not None:view.close()
        window.close();qt.processEvents()


def test_changed_copy_of_source_is_rejected(published_source,tmp_path):
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D
    copy=tmp_path/'changed.ifc';shutil.copyfile(published_source,copy)
    import ifcopenshell
    target=ifcopenshell.open(str(copy)).by_type('IfcCovering')[0].GlobalId
    contract=DeepIFCAdapter().read_display_contract(copy,revision='CEILING-TEST',max_triangles=40000,selected_global_ids=[target])
    copy.write_bytes(copy.read_bytes()+b'\n/* deliberately modified test copy */')
    with pytest.raises(ValueError,match='تغییر'):VerifiedScene3D(contract)
