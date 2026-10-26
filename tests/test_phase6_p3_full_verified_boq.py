"""Real accepted project: independent IFC reviewer + specialist detail + actual BOQ."""
import hashlib
import json

from test_phase2_priority5_closure import identity_case
from test_column_stage22 import column
from core.drawings.project_selection_bridge import VerifiedProjectSelection


def committed_column_case(tmp_path):
    import ifcopenshell
    app, old_path, _proof, _proposal, args = identity_case(tmp_path)
    m = ifcopenshell.open(str(old_path))
    obj = m.by_type('IfcColumn')[0]
    solid = obj.Representation.Representations[0].Items[0]
    solid.SweptArea.XDim=.4; solid.SweptArea.YDim=.5
    qset = next(r.RelatingPropertyDefinition for r in obj.IsDefinedBy
                if r.RelatingPropertyDefinition.is_a('IfcElementQuantity'))
    qset.Quantities=[
        m.create_entity('IfcQuantityVolume',Name='GrossVolume',VolumeValue=.6),
        m.create_entity('IfcQuantityVolume',Name='NetVolume',VolumeValue=.6)]
    source=tmp_path/'actual-column.ifc'
    m.write(str(source))
    app.add_project_member('P','C1','F1','column')
    proposal=app.save_ifc_identity_proposal('P',str(source),revision='R1',
        global_id=obj.GlobalId,floor_id='F1',member_id='C1',
        author='author',reference='Independent reviewed IFC column',
        expected_digest=app.store.current_digest('P'),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    mapping_proof=tmp_path/'column-proof.txt'
    mapping_proof.write_text('Explicit synthetic C1 / F1 column mapping '+obj.GlobalId+
        ' source '+hashlib.sha256(source.read_bytes()).hexdigest())
    app.review_ifc_identity('P',**{**args,'proposal_id':proposal['id'],
        'evidence_path':str(mapping_proof),
        'evidence_sha256':hashlib.sha256(mapping_proof.read_bytes()).hexdigest(),
        'expected_digest':app.store.current_digest('P')})
    data=column(count=1)
    data['member_id']='C1';data['floor_id']='F1';data.pop('source')
    detail=tmp_path/'column-detail.json'
    detail.write_text(json.dumps(data),encoding='utf-8')
    app.save_ifc_column_detail('P',proposal_id=proposal['id'],detail_path=str(detail),
        detail_sha256=hashlib.sha256(detail.read_bytes()).hexdigest(),
        author='author',reviewer='reviewer')
    preview=app.preview_structural_member('P','column','F1','C1')
    assert preview['ready']
    app.commit_structural_member('P','column','F1','C1',expected_revision=1)
    return app, source, obj


def test_actual_ifc_specialist_commit_three_boq_rows_navigate_all_four_views(tmp_path):
    app,source,obj=committed_column_case(tmp_path)
    snapshot=app.open_project('P')
    assert len(snapshot['boq'])==3
    before=app.store.current_digest('P')
    graph=VerifiedProjectSelection(app,'P',
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        revision='R1',real_global_ids={obj.GlobalId})
    gid=obj.GlobalId
    by_member=graph.resolve(origin='tree',identifier='C1',
        source_sha256=graph.source_sha256,revision='R1')
    assert by_member.status=='linked'
    assert by_member.global_ids==(gid,)
    assert len(by_member.boq_row_ids)==3
    for key in by_member.boq_row_ids:
        selected=graph.resolve(origin='boq',identifier=key,
            source_sha256=graph.source_sha256,revision='R1')
        assert selected.status=='linked'
        assert selected.global_ids==(gid,)
        assert selected.member_ids==('C1',)
        assert 'ردیف' in graph.boq_labels[key]
    for origin in ('2d','3d'):
        result=graph.resolve(origin=origin,identifier=gid,
            source_sha256=graph.source_sha256,revision='R1')
        assert result.boq_row_ids==by_member.boq_row_ids
    assert app.store.current_digest('P')==before
    assert snapshot==app.open_project('P')
    app.store.close()


def test_qt_real_boq_row_click_highlights_ifc_member_and_keeps_financial_digest(tmp_path):
    """QTest click on a BOQ row from the committed specialist receipt."""
    import os
    from pathlib import Path
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,source,obj=committed_column_case(tmp_path)
    qt=QApplication.instance() or QApplication([])
    window=GraphicalTakeoffDialog(app_service=app,project_id='P')
    window.show()
    window.open_drawing(str(source))
    window.ifc_revision.setText('R1')
    original=app.store.current_digest('P')
    boqs=app.open_project('P')['boq']
    QTest.mouseClick(window.verified_crossview_button,Qt.MouseButton.LeftButton)
    panel=window._verified_selection_panel
    assert panel is not None,window.status.text()
    assert panel.boq.rowCount()==3
    rectangle=panel.boq.visualRect(panel.boq.model().index(0,0))
    QTest.mouseClick(panel.boq.viewport(),Qt.MouseButton.LeftButton,
                     pos=rectangle.center())
    assert window._ifc_selected_global_id==obj.GlobalId
    assert panel.members.selectedItems()[0].text(0)=='C1'
    assert len(panel.boq.selectionModel().selectedRows())==3
    assert all(item.isSelected() for item in window._ifc_handle_items[obj.GlobalId])
    folder=os.environ.get('STRUCTURALPRO_P6_P3_SCREENSHOT_DIR')
    if folder:
        output=Path(folder);output.mkdir(parents=True,exist_ok=True)
        qt.processEvents()
        assert panel.grab().save(str(output/'p6-p3-real-reviewed-boq-click.png'))
    assert app.store.current_digest('P')==original
    assert app.open_project('P')['boq']==boqs
    window._verified_selection_dialog.close()
    window.close()
    qt.processEvents()
    app.store.close()
