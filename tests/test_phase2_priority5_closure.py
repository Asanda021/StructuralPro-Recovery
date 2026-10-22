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
    assert result['revision']==1 and result['created_at'] and result['event_id'].startswith('IFC-IDENTITY-')
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


def opening_model(path, *, mm=False, wrong_qto=False):
    from test_phase2_priority5_ifc import model_file
    import ifcopenshell as ifc
    m,objects=model_file(path,millimetres=mm);wall=objects[3];factor=1000. if mm else 1.
    # Explicit analytical wall: 4 x .2 x 3 = 2.4 m3; opening 1 x .2 x 2 = .4 m3.
    axes=m.create_entity('IfcAxis2Placement3D',Location=m.create_entity('IfcCartesianPoint',Coordinates=(0.,0.,factor)))
    opening=m.create_entity('IfcOpeningElement',GlobalId=ifc.guid.new(),Name='بازشوی واقعی مصنوعی',ObjectPlacement=m.create_entity('IfcLocalPlacement',PlacementRelTo=wall.ObjectPlacement,RelativePlacement=axes))
    profile=m.create_entity('IfcRectangleProfileDef',ProfileType='AREA',XDim=factor,YDim=.2*factor)
    solid=m.create_entity('IfcExtrudedAreaSolid',SweptArea=profile,ExtrudedDirection=m.create_entity('IfcDirection',DirectionRatios=(0.,0.,1.)),Depth=2.*factor)
    context=m.by_type('IfcGeometricRepresentationContext')[0]
    rep=m.create_entity('IfcShapeRepresentation',ContextOfItems=context,RepresentationIdentifier='Body',RepresentationType='SweptSolid',Items=[solid])
    opening.Representation=m.create_entity('IfcProductDefinitionShape',Representations=[rep])
    m.create_entity('IfcRelVoidsElement',GlobalId=ifc.guid.new(),RelatingBuildingElement=wall,RelatedOpeningElement=opening)
    qset=m.by_type('IfcElementQuantity')[3]
    qset.Quantities=[m.create_entity('IfcQuantityVolume',Name='GrossVolume',VolumeValue=2.4*factor**3),m.create_entity('IfcQuantityVolume',Name='NetVolume',VolumeValue=(2.1 if wrong_qto else 2.)*factor**3)]
    # Distinct local member positions, so this fixture does not imply co-located ownership.
    for i,obj in enumerate(objects):obj.ObjectPlacement.RelativePlacement.Location.Coordinates=(float(i*6)*factor,0.,0.)
    m.write(str(path));return wall.GlobalId,opening.GlobalId


@pytest.mark.parametrize('mm',[False,True])
def test_real_void_geometry_independent_volume_oracle(tmp_path,mm):
    from core.drawings.bim_quantities import compare_volume_qto
    from decimal import Decimal
    p=tmp_path/'void.ifc';gid,opening=opening_model(p,mm=mm)
    result=compare_volume_qto(p,revision='R1',global_id=gid)
    assert result['opening_ids']==[opening]
    assert abs(Decimal(result['gross_volume_m3'])-Decimal('2.4'))<Decimal('0.00000001')
    assert abs(Decimal(result['net_volume_m3'])-Decimal('2'))<Decimal('0.00000001')
    assert result['within_tolerance'] and result['commit_allowed'] is False
    assert result['payable_rows']==[]


def test_qto_geometry_conflict_not_promoted(tmp_path):
    from core.drawings.bim_quantities import compare_volume_qto
    p=tmp_path/'conflict.ifc';gid,_=opening_model(p,wrong_qto=True)
    result=compare_volume_qto(p,revision='R1',global_id=gid)
    assert not result['within_tolerance'] and not result['commit_allowed']
    assert any(not q['within_tolerance'] for q in result['comparisons'])


def test_ifc_qto_existing_formula_register_boq_and_reopen(tmp_path):
    from core.takeoff import manual_formula_register as formula
    from core.drawings.ifc_pipeline import quantity_formula_data
    from decimal import Decimal
    app,p,proof,proposal,args=identity_case(tmp_path)
    app.review_ifc_identity('P',**args)
    data=quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    assert data['family']=='manual_workbench' and data['variables']=={'Q':'4'}
    formula.save(app,'P','IFC-Q',data,expected_revision=0,reason='Explicit generic QTO; not materials')
    formula.review(app,'P','IFC-Q',expected_revision=1,reviewer='reviewer',note='QTO, unit and ownership checked')
    formula.commit(app,'P','IFC-Q',expected_revision=1)
    project=app.open_project('P')
    assert Decimal(str(project['boq'][0]['quantity']))==4
    assert project['boq'][0].get('unit_price') is None
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):formula.commit(app,'P','IFC-Q',expected_revision=1)
    assert app.store.current_digest('P')==before
    app.store.close()
    from core.platform.application import StructuralProApp
    reopened=StructuralProApp(tmp_path/'app');assert reopened.open_project('P')['takeoffs']==project['takeoffs']
    assert reopened.store.integrity_check()['ok'];reopened.store.close()


@pytest.mark.parametrize('mutation',['no_binding','wrong_quantity','changed_qto','changed_formula','same_reviewer','source_changed','proof_changed'])
def test_ifc_qto_handoff_fail_closed(tmp_path,mutation):
    from core.takeoff import manual_formula_register as formula
    from core.drawings.ifc_pipeline import quantity_formula_data
    app,p,proof,proposal,args=identity_case(tmp_path)
    if mutation=='no_binding':
        with pytest.raises(ValueError):quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
        return
    app.review_ifc_identity('P',**args)
    data=quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    if mutation=='wrong_quantity':data['ifc_evidence']['quantity_name']='Volume'
    elif mutation=='changed_qto':data['variables']['Q']='5'
    elif mutation=='changed_formula':data['expression']='Q*2'
    elif mutation=='source_changed':p.write_text(p.read_text()+'\n/* changed */')
    elif mutation=='proof_changed':proof.write_text('changed')
    if mutation=='same_reviewer':
        formula.save(app,'P','Q',data,expected_revision=0,reason='test')
        before=app.store.current_digest('P')
        with pytest.raises((ValueError,PermissionError)):formula.review(app,'P','Q',expected_revision=1,reviewer='author',note='invalid')
    else:
        before=app.store.current_digest('P')
        with pytest.raises((ValueError,PermissionError)):formula.save(app,'P','Q',data,expected_revision=0,reason='test')
    assert app.store.current_digest('P')==before and app.open_project('P')['boq']==[]
    app.store.close()


def test_generic_ifc_quantity_blocks_manual_or_cad_second_claim(tmp_path):
    from core.takeoff import manual_formula_register as formula
    from core.drawings.ifc_pipeline import quantity_formula_data
    from core.takeoff.commit_guards import validate_commit_rows
    app,p,proof,proposal,args=identity_case(tmp_path);app.review_ifc_identity('P',**args)
    data=quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    formula.save(app,'P','Q',data,expected_revision=0,reason='QTO')
    formula.review(app,'P','Q',expected_revision=1,reviewer='reviewer',note='checked')
    formula.commit(app,'P','Q',expected_revision=1);before=app.store.current_digest('P')
    candidate={'id':'other','source_id':'different-session-operation','member_code':'B1','system':'F1',
        'params':{'cad_evidence':{'floor_id':'F1','member_id':'B1'}},
        'quantities':[{'unit':'m','amount':'4','code':'different'}]}
    with pytest.raises(ValueError,match='IFC'):validate_commit_rows(app.open_project('P'),[candidate],source_id='different-session-operation')
    assert app.store.current_digest('P')==before;app.store.close()


@pytest.mark.parametrize('new_guid',[False,True])
def test_ifc_revision_amendment_uses_existing_journal_without_history_rewrite(tmp_path,new_guid):
    from copy import deepcopy
    from hashlib import sha256
    from core.takeoff import manual_formula_register as formula
    from core.takeoff import manual_formula_amendments as amendments
    from core.drawings.ifc_pipeline import quantity_formula_data
    import ifcopenshell
    from decimal import Decimal
    app,p,proof,proposal,args=identity_case(tmp_path);app.review_ifc_identity('P',**args)
    olddata=quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    formula.save(app,'P','Q',olddata,expected_revision=0,reason='QTO')
    formula.review(app,'P','Q',expected_revision=1,reviewer='reviewer',note='checked')
    formula.commit(app,'P','Q',expected_revision=1);original=deepcopy(app.open_project('P'))
    m=ifcopenshell.open(str(p));m.by_type('IfcQuantityLength')[0].LengthValue=5.
    gid=proposal['global_id']
    if new_guid:
        obj=m.by_guid(gid);obj.GlobalId=ifcopenshell.guid.new();gid=obj.GlobalId
    newpath=tmp_path/'R2.ifc';m.write(str(newpath))
    proposed=app.save_ifc_identity_proposal('P',str(newpath),revision='R2',global_id=gid,floor_id='F1',member_id='B1',author='author',reference='Explicit same physical member R2',expected_digest=app.store.current_digest('P'),source_sha256=sha256(newpath.read_bytes()).hexdigest())
    revision_proof=tmp_path/'revision-mapping.txt'
    revision_proof.write_text('Explicit synthetic same physical B1: '+proposal['global_id']+' -> '+gid+'; new source '+sha256(newpath.read_bytes()).hexdigest())
    newargs={**args,'proposal_id':proposed['id'],'evidence_path':str(revision_proof),'evidence_sha256':sha256(revision_proof.read_bytes()).hexdigest(),'expected_digest':app.store.current_digest('P')}
    with pytest.raises(ValueError,match='Revision'):app.review_ifc_identity('P',**newargs)
    app.review_ifc_identity('P',**newargs,supersedes=proposal['id'])
    with pytest.raises(ValueError,match='قدیمی'):quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    newdata=quantity_formula_data(app,'P',proposed['id'],'Length',author='author')
    a=amendments.proposal(app,'P','Q',newdata,expected_revision=1,created_by='author',reason='Explicit revised QTO')
    amendments.review(app,'P',a['id'],expected_revision=1,reviewer='reviewer',note='Delta 1 m, source and owner checked')
    amendments.apply(app,'P',a['id'],expected_revision=1)
    project=app.open_project('P')
    assert project['takeoffs']==original['takeoffs']
    assert project['manual_formula_register']==original['manual_formula_register']
    assert Decimal(str(project['boq'][0]['quantity']))==5
    assert Decimal(str(project['manual_formula_amendments'][a['id']]['quantity']))-Decimal(original['manual_formula_register']['Q']['quantity'])==1
    before=app.store.current_digest('P')
    with pytest.raises((ValueError,RuntimeError)):amendments.apply(app,'P',a['id'],expected_revision=1)
    assert app.store.current_digest('P')==before
    app.store.close()


def test_ifc_qto_real_qt_preview_review_and_boq(tmp_path):
    from PySide6.QtWidgets import QApplication,QPushButton,QLineEdit,QTreeWidget,QCheckBox,QLabel
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,p,proof,proposal,args=identity_case(tmp_path);app.review_ifc_identity('P',**args)
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id='P');w.show();w.open_drawing(str(p))
    QTest.keyClicks(w.ifc_revision,'R1');QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton)
    dlg=w._ifc_inspector;QTest.keyClicks(dlg.findChild(QLineEdit,'ifc_search'),proposal['global_id'])
    tree=dlg.findChild(QTreeWidget,'ifc_tree');tree.setCurrentItem(tree.topLevelItem(0).child(0))
    QTest.keyClicks(dlg.findChild(QLineEdit,'ifc_author'),'author')
    QTest.keyClicks(dlg.findChild(QLineEdit,'ifc_review_note'),'Checked QTO and SI unit')
    QTest.mouseClick(dlg.findChild(QPushButton,'ifc_quantity_preview'),Qt.LeftButton)
    assert app.open_project('P').get('manual_formula_register'),dlg.findChild(QLabel,'ifc_review_outcome').text()
    confirm=dlg.findChild(QCheckBox,'ifc_confirm_quantity')
    from PySide6.QtCore import QPoint
    QTest.mouseClick(confirm,Qt.LeftButton,pos=QPoint(confirm.width()-8,confirm.height()//2))
    assert confirm.isChecked()
    QTest.mouseClick(dlg.findChild(QPushButton,'ifc_quantity_review'),Qt.LeftButton)
    QTest.mouseClick(dlg.findChild(QPushButton,'ifc_quantity_commit'),Qt.LeftButton)
    assert app.open_project('P')['boq'],dlg.findChild(QLabel,'ifc_review_outcome').text()
    assert str(app.open_project('P')['boq'][0]['quantity'])=='4'
    w.close();qt.processEvents();app.store.close()


def crosswalk_case(tmp_path):
    import ezdxf,json,hashlib
    from core.drawings.dwg_takeoff import DWGTakeoffEngine
    from core.drawings.takeoff_session import DrawingTakeoffSession
    app,p,proof,proposal,args=identity_case(tmp_path);app.review_ifc_identity('P',**args)
    d=ezdxf.new('R2018');d.units=6;entity=d.modelspace().add_line((0,0),(4,0));drawing=tmp_path/'same-beam.dxf';d.saveas(drawing)
    doc=DWGTakeoffEngine.with_array_support().import_file(drawing)
    session=DrawingTakeoffSession(str(drawing));item=session.add_cad_entity(doc,entity.dxf.handle,'length',takeoff_code='TEST',floor_id='F1',member_id='B1',quantity_owner='B1',created_by='author',reference='explicit synthetic same beam')
    session.review_cad_entity(item.id,reviewer='reviewer',note='synthetic reviewed identity')
    saved=app.save_drawing_takeoff_session('P',session)
    evidence={'policy':'reviewed_reference_point_v1','project_id':'P','proposal_id':proposal['id'],
        'session_id':saved['session_id'],'item_id':item.id,'ifc_sha256':proposal['document']['source_sha256'],
        'drawing_sha256':hashlib.sha256(drawing.read_bytes()).hexdigest(),'ifc_origin_m':['1000000','7','0'],
        'drawing_anchor_xy':['0','0'],'ifc_to_drawing_si':['1','0','0','1','-1000000','-7'],
        'physical_identity_reference':'Explicit synthetic B1 correspondence; not a real design approval',
        'unit_evidence_reference':'IFC metre; DXF INSUNITS metre; reference coordinates supplied'}
    proofpath=tmp_path/'crosswalk.json';proofpath.write_text(json.dumps(evidence),encoding='utf-8')
    kw=dict(proposal_id=proposal['id'],session_id=saved['session_id'],item_id=item.id,author='author',reviewer='reviewer',
        evidence_path=str(proofpath),evidence_sha256=hashlib.sha256(proofpath.read_bytes()).hexdigest(),expected_digest=app.store.current_digest('P'))
    return app,p,drawing,session,proposal,kw


def test_reviewed_crosswalk_real_sources_sqlite_and_immutable(tmp_path):
    from copy import deepcopy
    app,p,drawing,session,proposal,kw=crosswalk_case(tmp_path)
    result=app.save_ifc_crosswalk('P',**kw)
    assert result['global_id']==proposal['global_id'] and result['member_id']=='B1'
    assert result['drawing']['handle']==session.items[0].cad_evidence['handle']
    before=app.store.current_digest('P');modified=deepcopy(app.open_project('P'))
    modified['ifc_2d_crosswalks'][0]['member_id']='other'
    with pytest.raises(ValueError,match='IFC'):app.store.save('P',modified,expected_digest=before)
    assert app.store.current_digest('P')==before and app.open_project('P')['boq']==[]
    app.store.close()
    from core.platform.application import StructuralProApp
    reopened=StructuralProApp(tmp_path/'app');assert reopened.open_project('P')['ifc_2d_crosswalks'][0]==result
    assert reopened.store.integrity_check()['ok'];reopened.store.close()


def test_crosswalk_real_qt_bidirectional_selection(tmp_path):
    from PySide6.QtWidgets import QApplication,QPushButton,QLineEdit,QTreeWidget
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,p,drawing,session,proposal,kw=crosswalk_case(tmp_path)
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id='P');w.show();w.open_drawing(str(p))
    QTest.keyClicks(w.ifc_revision,'R1');QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton)
    inspector=w._ifc_inspector
    QTest.keyClicks(inspector.findChild(QLineEdit,'ifc_search'),proposal['global_id'])
    tree=inspector.findChild(QTreeWidget,'ifc_tree');tree.setCurrentItem(tree.topLevelItem(0).child(0))
    QTest.keyClicks(inspector.findChild(QLineEdit,'ifc_author'),'author')
    inspector.findChild(QLineEdit,'ifc_crosswalk_evidence').setText(kw['evidence_path'])
    QTest.mouseClick(inspector.findChild(QPushButton,'ifc_save_crosswalk'),Qt.LeftButton)
    assert app.open_project('P').get('ifc_2d_crosswalks')
    link=app.open_project('P')['ifc_2d_crosswalks'][0]
    QTest.mouseClick(inspector.findChild(QPushButton,'ifc_show_crosswalk'),Qt.LeftButton)
    other=w._ifc_crosswalk_window
    handle=link['drawing']['handle'];assert other._cad_handle_items[handle].isSelected()
    inspector.findChild(QLineEdit,'ifc_search').clear()
    candidates=[tree.topLevelItem(i).child(j) for i in range(tree.topLevelItemCount()) for j in range(tree.topLevelItem(i).childCount())]
    tree.setCurrentItem(next(x for x in candidates if x.data(0,Qt.UserRole)!=proposal['global_id']))
    w.highlight_ifc_member('');other.canvas.scene.clearSelection()
    other.canvas.set_mode('cad_select');other.reset_zoom();other.canvas.set_mode('cad_select')
    item=other._cad_handle_items[handle]
    point=other.canvas.mapFromScene(item.sceneBoundingRect().center())
    QTest.mouseClick(other.canvas.viewport(),Qt.LeftButton,pos=point)
    assert w._ifc_selected_global_id==proposal['global_id']
    assert tree.currentItem().data(0,Qt.UserRole)==proposal['global_id']
    w.highlight_ifc_member('');other.canvas.scene.clearSelection()
    w.highlight_ifc_member(proposal['global_id'])
    assert item.isSelected()
    w.close();qt.processEvents();app.store.close()


@pytest.mark.parametrize('bad',['same_actor','wrong_transform','changed_source','changed_proof','wrong_member','stale','duplicate'])
def test_crosswalk_negative_atomic(tmp_path,bad):
    import json,hashlib
    app,p,drawing,session,proposal,kw=crosswalk_case(tmp_path)
    if bad=='same_actor':kw['reviewer']='author'
    elif bad=='wrong_transform':
        from pathlib import Path
        proof=Path(kw['evidence_path']);data=json.loads(proof.read_text());data['ifc_to_drawing_si'][-1]='-8';proof.write_text(json.dumps(data));kw['evidence_sha256']=hashlib.sha256(proof.read_bytes()).hexdigest()
    elif bad=='changed_source':drawing.write_bytes(drawing.read_bytes()+b'\n')
    elif bad=='changed_proof':
        from pathlib import Path
        Path(kw['evidence_path']).write_text('{}')
    elif bad=='wrong_member':
        from pathlib import Path
        proof=Path(kw['evidence_path']);data=json.loads(proof.read_text());data['proposal_id']='wrong';proof.write_text(json.dumps(data));kw['evidence_sha256']=hashlib.sha256(proof.read_bytes()).hexdigest()
    elif bad=='stale':app.add_project_floor('P','دوم',level='F2')
    elif bad=='duplicate':app.save_ifc_crosswalk('P',**kw);kw['expected_digest']=app.store.current_digest('P')
    before=app.store.current_digest('P')
    with pytest.raises((ValueError,PermissionError,RuntimeError)):
        app.save_ifc_crosswalk('P',**kw)
    assert app.store.current_digest('P')==before and app.open_project('P')['boq']==[]
    app.store.close()


def test_ifc_column_explicit_detail_uses_existing_specialist_and_boq(tmp_path):
    import json,hashlib,ifcopenshell
    from decimal import Decimal
    from test_column_stage22 import column
    app,p,proof,proposal,args=identity_case(tmp_path)
    # Independent source/detail: one .4 x .5 x 3 m column, not inferred rebar.
    m=ifcopenshell.open(str(p));obj=m.by_type('IfcColumn')[0]
    solid=obj.Representation.Representations[0].Items[0]
    solid.SweptArea.XDim=.4;solid.SweptArea.YDim=.5
    qset=next(r.RelatingPropertyDefinition for r in obj.IsDefinedBy if r.RelatingPropertyDefinition.is_a('IfcElementQuantity'))
    qset.Quantities=[m.create_entity('IfcQuantityVolume',Name='GrossVolume',VolumeValue=.6),m.create_entity('IfcQuantityVolume',Name='NetVolume',VolumeValue=.6)]
    source=tmp_path/'column.ifc';m.write(str(source))
    app.add_project_member('P','C1','F1','column')
    mapping=app.save_ifc_identity_proposal('P',str(source),revision='R1',global_id=obj.GlobalId,floor_id='F1',member_id='C1',author='author',reference='explicit independent column C1',expected_digest=app.store.current_digest('P'),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    column_proof=tmp_path/'column-mapping.txt'
    column_proof.write_text('Explicit synthetic C1 / F1 column mapping '+obj.GlobalId+'; source '+hashlib.sha256(source.read_bytes()).hexdigest())
    app.review_ifc_identity('P',**{**args,'proposal_id':mapping['id'],'evidence_path':str(column_proof),'evidence_sha256':hashlib.sha256(column_proof.read_bytes()).hexdigest(),'expected_digest':app.store.current_digest('P')})
    data=column(count=1);data['member_id']='C1';data['floor_id']='F1';data.pop('source')
    detail=tmp_path/'column-detail.json';detail.write_text(json.dumps(data),encoding='utf-8')
    saved=app.save_ifc_column_detail('P',proposal_id=mapping['id'],detail_path=str(detail),detail_sha256=hashlib.sha256(detail.read_bytes()).hexdigest(),author='author',reviewer='reviewer')
    assert saved['status']=='draft'
    report=app.preview_structural_member('P','column','F1','C1');assert report['ready'],report['blockers']
    q={r['unit']:Decimal(str(r['quantity'])) for r in report['rows']}
    assert q=={'m3':Decimal('.6'),'m2':Decimal('2.7'),'kg':Decimal('21.488')}
    app.commit_structural_member('P','column','F1','C1',expected_revision=1)
    assert len(app.open_project('P')['boq'])==3
    assert all(r['provenance']['ifc_identity']['proposal_id']==mapping['id'] for r in app.open_project('P')['takeoffs'])
    app.store.close()


def test_pdf_crosswalk_reuses_verified_page_and_calibration(tmp_path):
    import fitz,json,hashlib
    from core.drawings.takeoff_session import DrawingTakeoffSession
    from core.drawings.graphical_takeoff import Point
    app,p,proof,proposal,args=identity_case(tmp_path);app.review_ifc_identity('P',**args)
    pdf=tmp_path/'beam.pdf';document=fitz.open();page=document.new_page(width=100,height=100)
    page.draw_rect(fitz.Rect(0,0,40,10));document.save(pdf);document.close()
    session=DrawingTakeoffSession(str(pdf));session.calibrate(1,10,1)
    item=session.add_polygon([Point(0,0),Point(40,0),Point(40,10),Point(0,10)],floor_id='F1',member_id='B1',quantity_owner='reviewed B1',takeoff_code='TEST')
    saved=app.save_drawing_takeoff_session('P',session)
    data={'policy':'reviewed_reference_point_v1','project_id':'P','proposal_id':proposal['id'],'session_id':saved['session_id'],'item_id':item.id,'ifc_sha256':proposal['document']['source_sha256'],'drawing_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'ifc_origin_m':['1000000','7','0'],'drawing_anchor_xy':['0','0'],'ifc_to_drawing_si':['1','0','0','1','-1000000','-7'],'physical_identity_reference':'Explicit synthetic B1 mapping','unit_evidence_reference':'IFC metre, PDF calibrated .1 m/reference pixel'}
    path=tmp_path/'pdf-crosswalk.json';path.write_text(json.dumps(data))
    link=app.save_ifc_crosswalk('P',proposal_id=proposal['id'],session_id=saved['session_id'],item_id=item.id,author='author',reviewer='reviewer',evidence_path=str(path),evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),expected_digest=app.store.current_digest('P'))
    assert link['drawing']['page']==1 and link['drawing']['handle'] is None
    assert app.open_project('P')['boq']==[];app.store.close()


def test_cad_committed_first_blocks_ifc_duplicate_quantity(tmp_path):
    from core.takeoff import manual_formula_register as formula
    from core.drawings.ifc_pipeline import quantity_formula_data
    app,p,drawing,session,proposal,kw=crosswalk_case(tmp_path)
    app.save_ifc_crosswalk('P',**kw)
    app.commit_drawing_takeoff_to_boq('P',kw['session_id'],[kw['item_id']],expected_session_revision=1)
    data=quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    formula.save(app,'P','Q',data,expected_revision=0,reason='QTO')
    formula.review(app,'P','Q',expected_revision=1,reviewer='reviewer',note='checked')
    before=app.store.current_digest('P')
    with pytest.raises(ValueError,match='IFC'):formula.commit(app,'P','Q',expected_revision=1)
    assert app.store.current_digest('P')==before and len(app.open_project('P')['takeoffs'])==1
    app.store.close()


def test_ifc_commit_rechecks_source_after_quantity_review(tmp_path):
    from core.takeoff import manual_formula_register as formula
    from core.drawings.ifc_pipeline import quantity_formula_data
    app,p,proof,proposal,args=identity_case(tmp_path);app.review_ifc_identity('P',**args)
    data=quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    formula.save(app,'P','Q',data,expected_revision=0,reason='QTO')
    formula.review(app,'P','Q',expected_revision=1,reviewer='reviewer',note='checked')
    p.write_text(p.read_text()+'\n/* changed after review */')
    before=app.store.current_digest('P')
    with pytest.raises(ValueError,match='تغییر'):formula.commit(app,'P','Q',expected_revision=1)
    assert app.store.current_digest('P')==before and app.open_project('P')['boq']==[]
    app.store.close()


def test_crosswalk_close_does_not_call_deleted_scene(tmp_path,monkeypatch):
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,p,drawing,session,proposal,kw=crosswalk_case(tmp_path);link=app.save_ifc_crosswalk('P',**kw)
    qt=QApplication.instance() or QApplication([]);errors=[]
    monkeypatch.setattr(sys,'excepthook',lambda typ,value,tb:errors.append(str(value)))
    w=GraphicalTakeoffDialog(app_service=app,project_id='P');w.show();w.open_drawing(str(p))
    other=w.open_ifc_crosswalk(link['id']);w.close()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);qt.processEvents()
    assert errors==[]
    app.store.close()


@pytest.mark.parametrize('ifc_first',[False,True])
def test_pdf_line_ifc_second_payment_rejected_both_directions(tmp_path,ifc_first):
    import fitz,json,hashlib
    from core.drawings.takeoff_session import DrawingTakeoffSession
    from core.drawings.graphical_takeoff import Point
    from core.drawings.ifc_pipeline import quantity_formula_data
    from core.takeoff import manual_formula_register as formula
    app,p,proof,proposal,args=identity_case(tmp_path);app.review_ifc_identity('P',**args)
    pdf=tmp_path/'line.pdf';document=fitz.open();page=document.new_page(width=100,height=100);page.draw_line((0,0),(40,0));document.save(pdf);document.close()
    session=DrawingTakeoffSession(str(pdf));session.calibrate(1,10,1);item=session.add_length([Point(0,0),Point(40,0)],takeoff_code='TEST')
    saved=app.save_drawing_takeoff_session('P',session)
    evidence={'policy':'reviewed_reference_point_v1','project_id':'P','proposal_id':proposal['id'],'session_id':saved['session_id'],'item_id':item.id,'ifc_sha256':proposal['document']['source_sha256'],'drawing_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'ifc_origin_m':['1000000','7','0'],'drawing_anchor_xy':['0','0'],'ifc_to_drawing_si':['1','0','0','1','-1000000','-7'],'physical_identity_reference':'Explicit synthetic B1 reviewed source owner','unit_evidence_reference':'.1m/reference pixel and IFC metre'}
    path=tmp_path/'mapping.json';path.write_text(json.dumps(evidence))
    app.save_ifc_crosswalk('P',proposal_id=proposal['id'],session_id=saved['session_id'],item_id=item.id,author='author',reviewer='reviewer',evidence_path=str(path),evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),expected_digest=app.store.current_digest('P'))
    data=quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    formula.save(app,'P','Q',data,expected_revision=0,reason='QTO');formula.review(app,'P','Q',expected_revision=1,reviewer='reviewer',note='checked')
    if ifc_first:
        formula.commit(app,'P','Q',expected_revision=1);before=app.store.current_digest('P')
        with pytest.raises(ValueError,match='IFC'):app.commit_drawing_takeoff_to_boq('P',saved['session_id'],[item.id],expected_session_revision=1)
    else:
        app.commit_drawing_takeoff_to_boq('P',saved['session_id'],[item.id],expected_session_revision=1);before=app.store.current_digest('P')
        with pytest.raises(ValueError,match='IFC'):formula.commit(app,'P','Q',expected_revision=1)
    assert app.store.current_digest('P')==before and len(app.open_project('P')['takeoffs'])==1
    app.store.close()


def test_same_global_id_cannot_change_physical_member_across_revisions(tmp_path):
    import ifcopenshell,hashlib
    app,p,proof,proposal,args=identity_case(tmp_path)
    app.review_ifc_identity('P',**args)
    app.add_project_member('P','B2','F1','beam')
    model=ifcopenshell.open(str(p));model.by_guid(proposal['global_id']).Name='Changed label only'
    revised=tmp_path/'renamed.ifc';model.write(str(revised))
    candidate=app.save_ifc_identity_proposal('P',str(revised),revision='R2',global_id=proposal['global_id'],floor_id='F1',member_id='B2',author='author',reference='Proposed different owner; must be rejected',expected_digest=app.store.current_digest('P'),source_sha256=hashlib.sha256(revised.read_bytes()).hexdigest())
    before=app.store.current_digest('P')
    with pytest.raises(ValueError,match='GlobalId'):
        app.review_ifc_identity('P',**{**args,'proposal_id':candidate['id'],'expected_digest':before})
    assert app.store.current_digest('P')==before and app.open_project('P')['boq']==[]
    app.store.close()
