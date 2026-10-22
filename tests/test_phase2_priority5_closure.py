"""Acceptance of the remaining IFC gates using real Qt, IFC and SQLite."""
import gc,weakref

def test_closed_drawing_window_releases_scene_and_model():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog();w.show();ref=weakref.ref(w)
    w.close();del w
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    app.processEvents();gc.collect()
    assert ref() is None, 'Closed drawing window is retained by Qt signal/parent cycles'


def identity_case(tmp_path):
    from test_phase2_priority5_ifc import model_file
    from core.platform.application import StructuralProApp
    from core.collaboration.workspace import User
    import hashlib
    p=tmp_path/'source.ifc';_,objects=model_file(p)
    app=StructuralProApp(tmp_path/'app');app.create_project('identity','P')
    app.add_project_floor('P','طبقه اول',level='F1');app.add_project_member('P','B1','F1','beam')
    app.collaboration.add_user(User('author','نویسنده','editor'))
    app.collaboration.add_user(User('reviewer','بازبین','reviewer'))
    proof=tmp_path/'mapping.txt';proof.write_text('Explicit synthetic mapping B1 to first beam; R1',encoding='utf-8')
    proposal=app.save_ifc_identity_proposal('P',str(p),revision='R1',global_id=objects[0].GlobalId,floor_id='F1',member_id='B1',author='author',reference='explicit synthetic mapping',expected_digest=app.store.current_digest('P'),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    args=dict(proposal_id=proposal['id'],reviewer='reviewer',evidence_path=str(proof),evidence_sha256=hashlib.sha256(proof.read_bytes()).hexdigest(),note='Checked source, storey and physical identity',expected_digest=app.store.current_digest('P'))
    return app,p,proof,proposal,args


def test_reviewed_identity_persists_and_cannot_be_forged(tmp_path):
    from copy import deepcopy
    import pytest
    app,p,proof,proposal,args=identity_case(tmp_path)
    result=app.review_ifc_identity('P',**args)
    assert result['status']=='approved' and result['member_id']=='B1'
    assert result['review']['user_id']=='reviewer'
    assert result['commit_allowed'] is False and result['payable_rows']==[]
    before=app.store.current_digest('P');project=deepcopy(app.open_project('P'))
    project['ifc_identity_proposals'][0]['member_id']='other'
    with pytest.raises(ValueError,match='IFC'):app.store.save('P',project,expected_digest=before)
    assert app.store.current_digest('P')==before
    project=deepcopy(app.open_project('P'));project['ifc_identity_reviews'][0]['review']['note']='forged'
    with pytest.raises(ValueError,match='IFC'):app.store.save('P',project,expected_digest=before)
    app.store.close()
    from core.platform.application import StructuralProApp
    reopened=StructuralProApp(tmp_path/'app')
    assert reopened.open_project('P')['ifc_identity_reviews'][0]==result
    assert reopened.store.integrity_check()['ok'] and reopened.open_project('P')['boq']==[]
    reopened.store.close()


import pytest
@pytest.mark.parametrize('bad',['same_actor','unregistered','no_permission','evidence_changed','source_changed','stale','twice'])
def test_identity_review_negative_atomic(tmp_path,bad):
    from core.collaboration.workspace import User
    app,p,proof,proposal,args=identity_case(tmp_path)
    if bad=='same_actor':
        app.collaboration.add_user(User('author2','two','owner'))
        args['reviewer']='author'
    elif bad=='unregistered':args['reviewer']='nobody'
    elif bad=='no_permission':
        app.collaboration.add_user(User('reader','read','viewer'));args['reviewer']='reader'
    elif bad=='evidence_changed':proof.write_text('changed')
    elif bad=='source_changed':p.write_text(p.read_text()+'\n/* changed */')
    elif bad=='stale':
        app.add_project_floor('P','دوم',level='F2')
    elif bad=='twice':
        app.review_ifc_identity('P',**args);args['expected_digest']=app.store.current_digest('P')
    before=app.store.current_digest('P')
    with pytest.raises((ValueError,PermissionError,RuntimeError)):
        app.review_ifc_identity('P',**args)
    assert app.store.current_digest('P')==before and app.open_project('P')['boq']==[]
    app.store.close()


def test_identity_review_real_qt_click(tmp_path):
    from PySide6.QtWidgets import QApplication,QPushButton,QLineEdit,QTreeWidget,QComboBox
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,p,proof,proposal,args=identity_case(tmp_path)
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id='P');w.show();w.open_drawing(str(p))
    QTest.keyClicks(w.ifc_revision,'R1');QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton)
    dlg=w._ifc_inspector;tree=dlg.findChild(QTreeWidget,'ifc_tree')
    QTest.keyClicks(dlg.findChild(QLineEdit,'ifc_search'),proposal['global_id'])
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    dlg.findChild(QLineEdit,'ifc_identity_evidence').setText(str(proof))
    QTest.keyClicks(dlg.findChild(QLineEdit,'ifc_review_note'),'Checked independent source evidence')
    QTest.mouseClick(dlg.findChild(QPushButton,'ifc_review_identity'),Qt.LeftButton)
    from PySide6.QtWidgets import QLabel
    assert app.open_project('P').get('ifc_identity_reviews'), dlg.findChild(QLabel,'ifc_review_outcome').text()
    decision=app.open_project('P')['ifc_identity_reviews'][0]
    assert decision['global_id']==proposal['global_id']
    assert decision['review']['user_id']=='reviewer' and decision['commit_allowed'] is False
    w.close();qt.processEvents();app.store.close()
