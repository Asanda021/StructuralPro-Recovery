"""New acceptance cases use real IFC4/CAD, canonical SQLite and Qt."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from test_phase2_priority5_closure import crosswalk_case


def revised_crosswalk_case(tmp_path):
    import ifcopenshell
    app, source, drawing, session, proposal, kw = crosswalk_case(tmp_path)
    first = app.save_ifc_crosswalk('P', **kw)
    model = ifcopenshell.open(str(source))
    model.by_guid(proposal['global_id']).Name = 'Explicit R2 name; same physical B1'
    newer = tmp_path / 'R2.ifc'; model.write(str(newer))
    new = app.save_ifc_identity_proposal('P', str(newer), revision='R2', global_id=proposal['global_id'],
        floor_id='F1', member_id='B1', author='author', reference='Explicit R1/R2 mapping',
        source_sha256=sha256(newer.read_bytes()).hexdigest(), expected_digest=app.store.current_digest('P'))
    proof = tmp_path / 'identity-R2.txt'; proof.write_text('Synthetic independently reviewed B1 R1 to R2')
    app.review_ifc_identity('P', proposal_id=new['id'], reviewer='reviewer',
        evidence_path=str(proof), evidence_sha256=sha256(proof.read_bytes()).hexdigest(),
        note='Reviewed same owner and source change', supersedes=proposal['id'],
        expected_digest=app.store.current_digest('P'))
    evidence = json.loads(open(kw['evidence_path']).read())
    evidence.update(proposal_id=new['id'], ifc_sha256=sha256(newer.read_bytes()).hexdigest(), supersedes=first['id'])
    path = tmp_path / 'crosswalk-R2.json'; path.write_text(json.dumps(evidence))
    args = {**kw, 'proposal_id':new['id'], 'evidence_path':str(path),
        'evidence_sha256':sha256(path.read_bytes()).hexdigest(), 'supersedes':first['id'],
        'expected_digest':app.store.current_digest('P')}
    return app, newer, new, first, args


def test_positive_crosswalk_revision_keeps_original_and_reopens(tmp_path):
    app, newer, new, first, args = revised_crosswalk_case(tmp_path)
    migrated = app.save_ifc_crosswalk('P', **args)
    assert migrated['revision'] == 2 and migrated['supersedes'] == first['id']
    assert migrated['ifc_document']['revision'] == 'R2'
    assert app.open_project('P')['ifc_2d_crosswalks'] == [first, migrated]
    assert app.open_project('P')['boq'] == []
    before = app.store.current_digest('P')
    with pytest.raises((ValueError, RuntimeError)):
        app.save_ifc_crosswalk('P', **{**args, 'expected_digest':before})
    assert app.store.current_digest('P') == before
    app.store.close()
    from core.platform.application import StructuralProApp
    restored = StructuralProApp(tmp_path/'app')
    assert restored.open_project('P')['ifc_2d_crosswalks'] == [first, migrated]
    assert restored.store.integrity_check()['ok']
    restored.store.close()


@pytest.mark.parametrize('bad', ['missing_prior', 'changed_evidence', 'stale_cas', 'same_reviewer'])
def test_crosswalk_migration_rejection_is_atomic(tmp_path, bad):
    app, newer, new, first, args = revised_crosswalk_case(tmp_path)
    if bad == 'missing_prior': args['supersedes'] = 'unknown'
    elif bad == 'changed_evidence': open(args['evidence_path'], 'w').write('{}')
    elif bad == 'stale_cas': args['expected_digest'] = 'old'
    else: args['reviewer'] = 'author'
    before = app.store.current_digest('P')
    with pytest.raises((ValueError, RuntimeError, PermissionError)):
        app.save_ifc_crosswalk('P', **args)
    assert app.store.current_digest('P') == before
    app.store.close()


def test_generic_ifc_amendment_native_qt_keeps_original_boq(tmp_path):
    from test_phase2_priority5_closure import identity_case
    from core.drawings.ifc_pipeline import quantity_formula_data
    from core.takeoff import manual_formula_register as register
    from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit, QComboBox, QTreeWidget, QLabel
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from app.graphical_takeoff import GraphicalTakeoffDialog
    import ifcopenshell
    app, source, proof, proposal, kw = identity_case(tmp_path)
    app.review_ifc_identity('P', **kw)
    data = quantity_formula_data(app,'P',proposal['id'],'Length',author='author')
    register.save(app,'P','Q',data,expected_revision=0,reason='Explicit QTO oracle 4m')
    register.review(app,'P','Q',expected_revision=1,reviewer='reviewer',note='4m checked')
    register.commit(app,'P','Q',expected_revision=1)
    original = deepcopy(app.open_project('P'))
    model = ifcopenshell.open(str(source)); model.by_type('IfcQuantityLength')[0].LengthValue = 5.
    newer=tmp_path/'R2.ifc';model.write(str(newer))
    new=app.save_ifc_identity_proposal('P',str(newer),revision='R2',global_id=proposal['global_id'],floor_id='F1',member_id='B1',author='author',reference='Synthetic explicit revised length 5m',source_sha256=sha256(newer.read_bytes()).hexdigest(),expected_digest=app.store.current_digest('P'))
    app.review_ifc_identity('P', **{**kw, 'proposal_id':new['id'],'expected_digest':app.store.current_digest('P')}, supersedes=proposal['id'])
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id='P'); w.show(); w.open_drawing(str(newer)); w.ifc_revision.setText('R2')
    QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton)
    dialog=w._ifc_inspector
    try:
        dialog.findChild(QLineEdit,'ifc_search').setText(new['global_id'])
        tree=dialog.findChild(QTreeWidget,'ifc_tree'); tree.setCurrentItem(tree.topLevelItem(0).child(0))
        dialog.findChild(QLineEdit,'ifc_author').setText('author')
        dialog.findChild(QLineEdit,'ifc_review_note').setText('Independent corrected QTO 4 -> 5m')
        rows=dialog.findChild(QComboBox,'ifc_amend_row')
        assert rows is not None, 'IFC inspector has no native amendment workflow'
        assert rows.count() == 1; rows.setCurrentIndex(0)
        dialog.findChild(QLineEdit,'ifc_amend_reason').setText('Explicit revision correction evidence; original retained')
        for action in ('preview','create','review','apply'):
            QTest.mouseClick(dialog.findChild(QPushButton,'ifc_amend_'+action),Qt.LeftButton)
            qt.processEvents()
            assert 'انجام نشد' not in dialog.findChild(QLabel,'ifc_review_outcome').text(), dialog.findChild(QLabel,'ifc_review_outcome').text()
        project=app.open_project('P')
        assert project['takeoffs']==original['takeoffs']
        assert project['manual_formula_register']==original['manual_formula_register']
        assert str(project['boq'][0]['quantity']) in ('5','5.0')
        assert len(project['manual_formula_amendments'])==1
        assert '1' in dialog.findChild(QLabel,'ifc_amend_summary').text()
        before=app.store.current_digest('P')
        QTest.mouseClick(dialog.findChild(QPushButton,'ifc_amend_apply'),Qt.LeftButton)
        assert app.store.current_digest('P')==before
        dialog.grab().save(str(tmp_path/'ifc-amendment.png'))
    finally:
        w.close();qt.processEvents();app.store.close()


def column_revision_case(tmp_path):
    from test_phase2_priority5_closure import identity_case
    from test_column_stage22 import column
    import ifcopenshell
    app, source, proof, unused, kw=identity_case(tmp_path)
    app.add_project_member('P','C1','F1','column')
    model=ifcopenshell.open(str(source)); obj=model.by_type('IfcColumn')[0]
    solid=obj.Representation.Representations[0].Items[0]
    solid.SweptArea.XDim=.4;solid.SweptArea.YDim=.5
    qset=next(x.RelatingPropertyDefinition for x in obj.IsDefinedBy if x.RelatingPropertyDefinition.is_a('IfcElementQuantity'))
    qset.Quantities=[model.create_entity('IfcQuantityVolume',Name='GrossVolume',VolumeValue=.6),model.create_entity('IfcQuantityVolume',Name='NetVolume',VolumeValue=.6)]
    path=tmp_path/'C1-R1.ifc';model.write(str(path))
    old=app.save_ifc_identity_proposal('P',str(path),revision='R1',global_id=obj.GlobalId,floor_id='F1',member_id='C1',author='author',reference='Explicit C1 fixture',source_sha256=sha256(path.read_bytes()).hexdigest(),expected_digest=app.store.current_digest('P'))
    app.review_ifc_identity('P',**{**kw,'proposal_id':old['id'],'expected_digest':app.store.current_digest('P')})
    detail=column(count=1);detail.update(floor_id='F1',member_id='C1');detail.pop('source')
    d1=tmp_path/'C1-R1.json';d1.write_text(json.dumps(detail))
    app.save_ifc_column_detail('P',proposal_id=old['id'],detail_path=str(d1),detail_sha256=sha256(d1.read_bytes()).hexdigest(),author='author',reviewer='reviewer')
    app.commit_structural_member('P','column','F1','C1',expected_revision=1)
    original=deepcopy(app.open_project('P'))
    solid.SweptArea.XDim=.5
    for q in qset.Quantities:q.VolumeValue=.75
    p2=tmp_path/'C1-R2.ifc';model.write(str(p2))
    new=app.save_ifc_identity_proposal('P',str(p2),revision='R2',global_id=obj.GlobalId,floor_id='F1',member_id='C1',author='author',reference='Same C1, explicit width .5m in R2',source_sha256=sha256(p2.read_bytes()).hexdigest(),expected_digest=app.store.current_digest('P'))
    app.review_ifc_identity('P',**{**kw,'proposal_id':new['id'],'expected_digest':app.store.current_digest('P')},supersedes=old['id'])
    detail['geometry']['width']='.5'
    for face in detail['formwork']['surfaces']:face['gross_area_m2']='1.5'
    d2=tmp_path/'C1-R2.json';d2.write_text(json.dumps(detail))
    data=deepcopy(detail)
    data['source']={'mode':'manual','source_id':'ifc-column:P:F1:C1','plan_ref':sha256(p2.read_bytes()).hexdigest(),'detail_ref':sha256(d2.read_bytes()).hexdigest(),'ifc_identity':{'proposal_id':new['id'],'author':'author','reviewer':'reviewer','detail_path':str(d2.resolve()),'detail_sha256':sha256(d2.read_bytes()).hexdigest()}}
    return app,p2,new,d2,data,original


def test_ifc_column_amendment_source_revision_uses_existing_journal(tmp_path):
    from decimal import Decimal
    app,p2,new,detail,data,original=column_revision_case(tmp_path)
    a=app.create_column_amendment('P','F1','C1',data,expected_revision=1,created_by='author',reason='Explicit .4 to .5m width; independent external detail')
    app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='reviewer',note='Geometry and complete detail checked')
    app.apply_beam_amendment('P',a['id'],expected_revision=1)
    current=app.open_project('P')
    assert current['takeoffs']==original['takeoffs']
    assert current['reviewed_structural_members']==original['reviewed_structural_members']
    assert {r['unit']:Decimal(str(r['quantity'])) for r in current['boq']}=={'m3':Decimal('.75'),'m2':Decimal('3'),'kg':Decimal('21.488')}
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.apply_beam_amendment('P',a['id'],expected_revision=1)
    assert app.store.current_digest('P')==before
    app.store.close()


def test_ifc_column_revision_amendment_real_qt_and_reopen(tmp_path):
    from decimal import Decimal
    from PySide6.QtWidgets import QApplication,QPushButton,QLineEdit,QComboBox,QTreeWidget,QLabel
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,source,new,detail,data,original=column_revision_case(tmp_path)
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id='P');w.show();w.open_drawing(str(source));w.ifc_revision.setText('R2');QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton)
    dialog=w._ifc_inspector
    try:
        dialog.findChild(QLineEdit,'ifc_search').setText(new['global_id'])
        tree=dialog.findChild(QTreeWidget,'ifc_tree');tree.setCurrentItem(tree.topLevelItem(0).child(0))
        dialog.findChild(QLineEdit,'ifc_author').setText('author')
        dialog.findChild(QLineEdit,'ifc_review_note').setText('Synthetic independent complete R2 detail')
        rows=dialog.findChild(QComboBox,'ifc_amend_row')
        assert rows.count()==1, 'committed IFC column missing from amendment UI'
        rows.setCurrentIndex(0)
        dialog.findChild(QLineEdit,'ifc_amend_detail').setText(str(detail))
        dialog.findChild(QLineEdit,'ifc_amend_reason').setText('Explicit corrected width and face areas; no rebar inference')
        for step in ('preview','create','review','apply'):
            QTest.mouseClick(dialog.findChild(QPushButton,'ifc_amend_'+step),Qt.LeftButton);qt.processEvents()
            assert 'انجام نشد' not in dialog.findChild(QLabel,'ifc_review_outcome').text(), dialog.findChild(QLabel,'ifc_review_outcome').text()
        project=app.open_project('P')
        assert project['takeoffs']==original['takeoffs'] and project['reviewed_structural_members']==original['reviewed_structural_members']
        assert {r['unit']:Decimal(str(r['quantity'])) for r in project['boq']}=={'m3':Decimal('.75'),'m2':Decimal('3'),'kg':Decimal('21.488')}
        dialog.grab().save(str(tmp_path/'column-amendment-qt.png'))
    finally:w.close();qt.processEvents();app.store.close()
    from core.platform.application import StructuralProApp
    restored=StructuralProApp(tmp_path/'app')
    assert restored.open_project('P')['takeoffs']==original['takeoffs']
    assert restored.get_structural_member('P','column','F1','C1')['revision']==2
    assert restored.store.integrity_check()['ok'];restored.store.close()


def test_crosswalk_revision_migration_native_qt_selects_current_source(tmp_path):
    from PySide6.QtWidgets import QApplication,QPushButton,QLineEdit,QTreeWidget,QLabel
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,source,new,first,args=revised_crosswalk_case(tmp_path)
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id='P');w.show();w.open_drawing(str(source));w.ifc_revision.setText('R2');QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton)
    dialog=w._ifc_inspector
    try:
        dialog.findChild(QLineEdit,'ifc_search').setText(new['global_id'])
        tree=dialog.findChild(QTreeWidget,'ifc_tree');tree.setCurrentItem(tree.topLevelItem(0).child(0))
        dialog.findChild(QLineEdit,'ifc_author').setText('author')
        prior=dialog.findChild(QLineEdit,'ifc_crosswalk_supersedes')
        assert prior is not None, 'revision migration is absent in native inspector'
        prior.setText(first['id'])
        dialog.findChild(QLineEdit,'ifc_crosswalk_evidence').setText(args['evidence_path'])
        QTest.mouseClick(dialog.findChild(QPushButton,'ifc_save_crosswalk'),Qt.LeftButton)
        assert 'انجام نشد' not in dialog.findChild(QLabel,'ifc_review_outcome').text(),dialog.findChild(QLabel,'ifc_review_outcome').text()
        assert len(app.open_project('P')['ifc_2d_crosswalks'])==2
        QTest.mouseClick(dialog.findChild(QPushButton,'ifc_show_crosswalk'),Qt.LeftButton)
        other=w._ifc_crosswalk_window
        assert other._cad_handle_items[first['drawing']['handle']].isSelected()
        with pytest.raises(ValueError):w.open_ifc_crosswalk(first['id'])
    finally:w.close();qt.processEvents();app.store.close()


@pytest.mark.parametrize('bad',['changed_detail','changed_ifc','same_reviewer','stale_revision','financial_lock'])
def test_ifc_column_amendment_negative_atomic(tmp_path,bad):
    app,source,new,detail,data,original=column_revision_case(tmp_path)
    before=app.store.current_digest('P')
    if bad=='changed_detail':detail.write_text('{}')
    elif bad=='changed_ifc':source.write_bytes(source.read_bytes()+b'\n')
    if bad in ('changed_detail','changed_ifc','stale_revision'):
        with pytest.raises((ValueError,RuntimeError)):
            app.create_column_amendment('P','F1','C1',data,expected_revision=0 if bad=='stale_revision' else 1,created_by='author',reason='Documented correction')
        assert app.store.current_digest('P')==before
    else:
        a=app.create_column_amendment('P','F1','C1',data,expected_revision=1,created_by='author',reason='Documented correction')
        if bad=='same_reviewer':
            before=app.store.current_digest('P')
            with pytest.raises((ValueError,PermissionError)):app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='author',note='invalid self review')
        else:
            app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='reviewer',note='Independent complete detail')
            project=app.open_project('P');project['statement_periods']=[{'id':'issued','amount':'100'}];app.store.save('P',project)
            before=app.store.current_digest('P')
            with pytest.raises(ValueError):app.apply_beam_amendment('P',a['id'],expected_revision=1)
        assert app.store.current_digest('P')==before
    assert app.open_project('P')['takeoffs']==original['takeoffs']
    app.store.close()


def test_multipage_pdf_ifc_native_crosswalk_and_bidirectional_selection(tmp_path):
    import fitz
    from test_phase2_priority5_closure import identity_case
    from core.drawings.takeoff_session import DrawingTakeoffSession
    from core.drawings.graphical_takeoff import Point
    from PySide6.QtWidgets import QApplication,QPushButton,QLineEdit,QTreeWidget,QLabel
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,source,proof,proposal,kw=identity_case(tmp_path);app.review_ifc_identity('P',**kw)
    path=tmp_path/'multifloor.pdf';pdf=fitz.open()
    for i in range(3):pdf.new_page(width=100,height=100).draw_rect(fitz.Rect(0,0,40,10))
    pdf.save(path);pdf.close()
    session=DrawingTakeoffSession(str(path));session.current_page=2;session.calibrate(2,10,1)
    item=session.add_polygon([Point(0,0),Point(40,0),Point(40,10),Point(0,10)],floor_id='F1',member_id='B1',quantity_owner='Explicit reviewed B1 scope',takeoff_code='TEST')
    assert item.page==2
    saved=app.save_drawing_takeoff_session('P',session)
    evidence={'policy':'reviewed_reference_point_v1','project_id':'P','proposal_id':proposal['id'],'session_id':saved['session_id'],'item_id':item.id,'ifc_sha256':proposal['document']['source_sha256'],'drawing_sha256':sha256(path.read_bytes()).hexdigest(),'ifc_origin_m':['1000000','7','0'],'drawing_anchor_xy':['0','0'],'ifc_to_drawing_si':['1','0','0','1','-1000000','-7'],'physical_identity_reference':'Synthetic B1 floor plan checked independently','unit_evidence_reference':'PDF page 2 reference 10 -> 1m; IFC metre'}
    mapping=tmp_path/'pdf-link.json';mapping.write_text(json.dumps(evidence))
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id='P');w.show();w.open_drawing(str(source));w.ifc_revision.setText('R1');QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton)
    dialog=w._ifc_inspector
    try:
        dialog.findChild(QLineEdit,'ifc_search').setText(proposal['global_id']);tree=dialog.findChild(QTreeWidget,'ifc_tree');tree.setCurrentItem(tree.topLevelItem(0).child(0))
        dialog.findChild(QLineEdit,'ifc_author').setText('author');dialog.findChild(QLineEdit,'ifc_crosswalk_evidence').setText(str(mapping))
        QTest.mouseClick(dialog.findChild(QPushButton,'ifc_save_crosswalk'),Qt.LeftButton)
        assert 'انجام نشد' not in dialog.findChild(QLabel,'ifc_review_outcome').text(),dialog.findChild(QLabel,'ifc_review_outcome').text()
        QTest.mouseClick(dialog.findChild(QPushButton,'ifc_show_crosswalk'),Qt.LeftButton);qt.processEvents()
        other=w._ifc_crosswalk_window
        assert other.page==2 and other.viewer.kind=='pdf'
        w.highlight_ifc_member('');other.table.clearSelection()
        rect=other.table.visualItemRect(other.table.item(0,0))
        QTest.mouseClick(other.table.viewport(),Qt.LeftButton,pos=rect.center());qt.processEvents()
        assert w._ifc_selected_global_id==proposal['global_id']
        assert tree.currentItem().data(0,Qt.UserRole)==proposal['global_id']
        other.table.clearSelection();w.highlight_ifc_member('');w.highlight_ifc_member(proposal['global_id']);qt.processEvents()
        assert other.table.currentRow()==0
        other.grab().save(str(tmp_path/'pdf-ifc-linked-qt.png'))
    finally:w.close();qt.processEvents();app.store.close()


def quantity_lineage_case(tmp_path, mode='split', changed_total=False):
    import ifcopenshell
    from test_phase2_priority5_closure import identity_case
    from test_phase2_priority5_ifc_lineage_chat import _review
    app,path,proof,unused,kw=identity_case(tmp_path)
    app.add_project_member('P','B2','F1','beam');app.add_project_member('P','B3','F1','beam')
    model=ifcopenshell.open(str(path));beam=model.by_type('IfcBeam')[0];other=model.by_type('IfcColumn')[0]
    def length(obj,value):
        qs=next(x.RelatingPropertyDefinition for x in obj.IsDefinedBy if x.RelatingPropertyDefinition.is_a('IfcElementQuantity'))
        qs.Quantities[0].LengthValue=value
    length(beam,6 if mode=='split' else 2);length(other,4)
    oldpath=tmp_path/'old-quantities.ifc';model.write(str(oldpath))
    old=[_review(app,oldpath,revision='R1',gid=beam.GlobalId,member='B1',proof=proof)]
    if mode=='merge':old.append(_review(app,oldpath,revision='R1',gid=other.GlobalId,member='B2',proof=proof))
    beam.GlobalId=ifcopenshell.guid.new();other.GlobalId=ifcopenshell.guid.new()
    length(beam,2 if mode=='split' else 6);length(other,5 if changed_total else 4)
    newpath=tmp_path/'new-quantities.ifc';model.write(str(newpath))
    new=[_review(app,newpath,revision='R2',gid=beam.GlobalId,member='B2' if mode=='split' else 'B3',proof=proof)]
    if mode=='split':new.append(_review(app,newpath,revision='R2',gid=other.GlobalId,member='B3',proof=proof))
    edges=[{'previous_proposal_id':a,'current_proposal_id':b,'physical_scope_reference':'Explicit synthetic segment ownership'} for a in old for b in new]
    evidence={'policy':'reviewed_ifc_lineage_v1','project_id':'P','mode':mode,'previous_proposal_ids':old,'current_proposal_ids':new,'previous_source_sha256':sha256(oldpath.read_bytes()).hexdigest(),'current_source_sha256':sha256(newpath.read_bytes()).hexdigest(),'edges':edges}
    ep=tmp_path/'lineage.json';ep.write_text(json.dumps(evidence))
    event=app.review_ifc_identity_lineage('P',mode=mode,previous_proposal_ids=old,current_proposal_ids=new,author='author',reviewer='reviewer',evidence_path=str(ep),evidence_sha256=sha256(ep.read_bytes()).hexdigest(),note='Explicit synthetic topology, not payment',expected_digest=app.store.current_digest('P'))
    allocation={'policy':'reviewed_ifc_quantity_allocation_v1','project_id':'P','lineage_id':event['id'],'quantity_name':'Length','unit':'m','previous':[{'proposal_id':p,'quantity':str(q),'scope_reference':'Old synthetic member explicit full length'} for p,q in zip(old,[6] if mode=='split' else [2,4])],'current':[{'proposal_id':p,'quantity':str(q),'scope_reference':'Current independently dimensioned segment'} for p,q in zip(new,[2,5 if changed_total else 4] if mode=='split' else [6])]}
    alloc=tmp_path/'allocation.json';alloc.write_text(json.dumps(allocation))
    args={'lineage_id':event['id'],'evidence_path':str(alloc),'evidence_sha256':sha256(alloc.read_bytes()).hexdigest(),'author':'author','reviewer':'reviewer','expected_digest':app.store.current_digest('P')}
    return app,args,alloc,allocation


@pytest.mark.parametrize('mode',['split','merge'])
def test_real_ifc_lineage_quantity_oracle_never_authorizes_payment(tmp_path,mode):
    app,args,proof,data=quantity_lineage_case(tmp_path,mode)
    before=app.store.current_digest('P')
    assert hasattr(app,'assess_ifc_lineage_quantities'), 'independent quantity reconciliation is missing'
    result=app.assess_ifc_lineage_quantities('P',**args)
    assert result['previous_total']=='6' and result['current_total']=='6' and result['delta']=='0'
    assert result['commit_allowed'] is False and result['payable_rows']==[]
    assert app.store.current_digest('P')==before
    app.store.close()


@pytest.mark.parametrize('bad',['missing_table','wrong_quantity','duplicate','changed_proof','self_review','stale'])
def test_lineage_quantity_assessment_bad_evidence_is_atomic(tmp_path,bad):
    app,args,proof,data=quantity_lineage_case(tmp_path)
    assert hasattr(app,'assess_ifc_lineage_quantities')
    if bad=='missing_table':data.pop('current')
    elif bad=='wrong_quantity':data['current'][0]['quantity']='3'
    elif bad=='duplicate':data['current'][1]['proposal_id']=data['current'][0]['proposal_id']
    elif bad=='self_review':args['reviewer']='author'
    elif bad=='stale':args['expected_digest']='old'
    if bad=='changed_proof':proof.write_text('{}')
    else:proof.write_text(json.dumps(data));args['evidence_sha256']=sha256(proof.read_bytes()).hexdigest()
    before=app.store.current_digest('P')
    with pytest.raises((ValueError,RuntimeError,PermissionError)):
        app.assess_ifc_lineage_quantities('P',**args)
    assert app.store.current_digest('P')==before;app.store.close()


def test_quantity_delta_requires_explicit_change_evidence_and_remains_nonfinancial(tmp_path):
    app,args,path,data=quantity_lineage_case(tmp_path,changed_total=True)
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.assess_ifc_lineage_quantities('P',**args)
    assert app.store.current_digest('P')==before
    data['quantity_change_reference']='Explicit synthetic revised segment increases 4m to 5m; not a payment approval'
    path.write_text(json.dumps(data));args['evidence_sha256']=sha256(path.read_bytes()).hexdigest()
    report=app.assess_ifc_lineage_quantities('P',**args)
    assert report['delta']=='1' and report['previous_total']=='6' and report['current_total']=='7'
    assert report['commit_allowed'] is False and report['payable_rows']==[]
    assert app.store.current_digest('P')==before
    app.store.close()
