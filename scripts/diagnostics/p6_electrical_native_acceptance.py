"""Published IFC4 electrical interoperability example; no engineering/QTO approval."""
import hashlib,json,os,shutil,time
from pathlib import Path
from urllib.request import urlopen
import pytest

UPSTREAM='7a7eb6bdeab3e630eeef0e923a908d0c6af07cd2'
SOURCE_PATH='IFC4/buildingSMART-Certification-datasets/Simple-Scene/Infra-Electrical.ifc'
SHA='18ec714203238bc33ef767306cfcaa8209fcda186a8fe8ad2db7f204bc6b5a49'
BLOB='ceb647e0912ad6d4f6913b23f61f631e629b38f2'

@pytest.fixture(scope='module')
def published_source(tmp_path_factory):
    path=tmp_path_factory.mktemp('published-electrical')/'source.ifc'
    with urlopen('https://raw.githubusercontent.com/BIMvoice/ifcsamples/'+UPSTREAM+'/'+SOURCE_PATH,timeout=60) as r:
        data=r.read(200000)
    assert len(data)==120095 and hashlib.sha256(data).hexdigest()==SHA
    assert hashlib.sha1(b'blob 120095\0'+data).hexdigest()==BLOB
    path.write_bytes(data)
    return path


def test_original_qprocess_and_actual_electrical_member_pick(published_source):
    import ifcopenshell
    from PySide6.QtCore import QPoint,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    model=ifcopenshell.open(str(published_source));assert model.schema=='IFC4'
    target=model.by_type('IfcElectricAppliance');assert len(target)==1
    gid=target[0].GlobalId
    qt=QApplication.instance() or QApplication([]);window=GraphicalTakeoffDialog()
    output=Path(os.environ.get('P6_ELECTRICAL_EVIDENCE','electrical-evidence'));output.mkdir(exist_ok=True)
    def await_done(test,seconds=60):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            qt.processEvents()
            if test():return
            QTest.qWait(10)
        raise AssertionError('bounded original GUI worker timeout')
    try:
        window.ifc_revision.setText('BIMVOICE-'+UPSTREAM[:12]);window.show()
        window.open_cad_async(published_source);await_done(lambda:window._cad_job is None)
        assert window.viewer.kind=='ifc',window.status.text()
        assert len(window.viewer.ifc_document.source_roster)==6
        assert window.viewer.ifc_document.source_sha256==SHA
        window.open_ifc_3d();await_done(lambda:window._ifc_3d_loader is None)
        view=window._ifc_3d_dialog;assert view is not None,window.status.text()
        view.batch_type.setCurrentIndex(view.batch_type.findData('IfcElectricAppliance'))
        assert view._filtered_batch_ids()==(gid,)
        view.batch_size.setValue(1);assert view.request_selected_batch()
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
        assert view.grab().save(str(output/'actual-electric-appliance.png'))
        (output/'source-verified.json').write_text(json.dumps(dict(
            source_commit=UPSTREAM,source_path=SOURCE_PATH,source_sha256=SHA,source_git_blob=BLOB,
            source_license='CC BY 4.0; buildingSMART Certification datasets; BIMvoice redistribution',
            total_source_elements=6,target_type='IfcElectricAppliance',selected_global_id=gid,
            source_roster_count=6,raw_source_redistributed=False,boq_written=False,
            category='published interoperability example, not an actual owner electrical installation',
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
    contract=DeepIFCAdapter().read_display_contract(copy,revision='ELECTRICAL-TEST')
    copy.write_bytes(copy.read_bytes()+b'\n/* deliberately modified test copy */')
    with pytest.raises(ValueError,match='تغییر'):VerifiedScene3D(contract)
