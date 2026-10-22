"""Real ACadSharp/IFC4/Qt/SQLite scenario; synthetic, no design approval."""
from pathlib import Path
import sys,json,shutil
from hashlib import sha256
root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=True)
repo=Path(__file__).resolve().parents[3];sys.path[:0]=[str(repo),str(repo/'tests')]
from test_phase2_priority5_closure import identity_case
from core.drawings.dwg_takeoff import DWGTakeoffEngine
from core.cad.external_dwg_provider_v1 import ACadSharpDWGProvider
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.ifc_pipeline import quantity_formula_data
from core.takeoff import manual_formula_register as formula
from app.graphical_takeoff import GraphicalTakeoffDialog
from PySide6.QtWidgets import QApplication,QPushButton,QLineEdit,QTreeWidget,QLabel
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import ifcopenshell

service,p,proof,unused,kw=identity_case(root)
m=ifcopenshell.open(str(p));beam=m.by_type('IfcBeam')[0]
qset=next(x.RelatingPropertyDefinition for x in beam.IsDefinedBy if x.RelatingPropertyDefinition.is_a('IfcElementQuantity'))
qset.Quantities[0].LengthValue=5.
source=root/'beam-5m.ifc';m.write(str(source))
proposal=service.save_ifc_identity_proposal('P',str(source),revision='R1',global_id=beam.GlobalId,floor_id='F1',member_id='B1',author='author',reference='Synthetic independent 5m beam QTO paired with CAD 3-4-5 line',source_sha256=sha256(source.read_bytes()).hexdigest(),expected_digest=service.store.current_digest('P'))
service.review_ifc_identity('P',**{**kw,'proposal_id':proposal['id'],'expected_digest':service.store.current_digest('P')})
dwg=root/'reference.dwg';shutil.copy2(repo/'docs/acceptance/phase2_priority4_cad_20261021_assets/synthetic-ac1032.dwg',dwg)
assert dwg.read_bytes()[:6]==b'AC1032'
doc=DWGTakeoffEngine.with_array_support().import_file(dwg)
converted=Path('/tmp/p5-converted')/(doc.conversion['output_sha256']+'.dxf');dxf=root/'converted.dxf';shutil.copy2(converted,dxf)
assert sha256(dxf.read_bytes()).hexdigest()==doc.conversion['output_sha256']
entity=next(x for x in doc.entities if x.entity_type=='LINE' and '/' not in x.handle)
assert entity.data['length']==5
session=DrawingTakeoffSession(str(dwg));item=session.add_cad_entity(doc,entity.handle,'length',takeoff_code='SYNTHETIC',floor_id='F1',member_id='B1',quantity_owner='Synthetic sole B1 owner explicitly reviewed',created_by='author',reference='Independent 3-4-5 triangle: 5m')
session.review_cad_entity(item.id,reviewer='reviewer',note='Independent analytical length 5m')
saved=service.save_drawing_takeoff_session('P',session)
evidence={'policy':'reviewed_reference_point_v1','project_id':'P','proposal_id':proposal['id'],'session_id':saved['session_id'],'item_id':item.id,'ifc_sha256':sha256(source.read_bytes()).hexdigest(),'drawing_sha256':sha256(dwg.read_bytes()).hexdigest(),'ifc_origin_m':['1000000','7','0'],'drawing_anchor_xy':['0','0'],'ifc_to_drawing_si':['1','0','0','1','-1000000','-7'],'physical_identity_reference':'Synthetic B1 explicit same 5m quantity owner; not automatic geometry equality','unit_evidence_reference':'IFC metre and CAD explicit INSUNITS metre'}
linkproof=root/'crosswalk.json';linkproof.write_text(json.dumps(evidence))
qt=QApplication.instance() or QApplication([])
w=GraphicalTakeoffDialog(app_service=service,project_id='P');w.show();w.open_drawing(str(source));w.ifc_revision.setText('R1');QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton)
dialog=w._ifc_inspector
try:
 dialog.findChild(QLineEdit,'ifc_search').setText(proposal['global_id']);tree=dialog.findChild(QTreeWidget,'ifc_tree');tree.setCurrentItem(tree.topLevelItem(0).child(0))
 dialog.findChild(QLineEdit,'ifc_author').setText('author');dialog.findChild(QLineEdit,'ifc_crosswalk_evidence').setText(str(linkproof))
 QTest.mouseClick(dialog.findChild(QPushButton,'ifc_save_crosswalk'),Qt.LeftButton)
 assert 'انجام نشد' not in dialog.findChild(QLabel,'ifc_review_outcome').text(),dialog.findChild(QLabel,'ifc_review_outcome').text()
 link=service.open_project('P')['ifc_2d_crosswalks'][0]
 assert link['drawing']['conversion']==doc.conversion, 'DWG and DXF provenance missing in Crosswalk'
 QTest.mouseClick(dialog.findChild(QPushButton,'ifc_show_crosswalk'),Qt.LeftButton);other=w._ifc_crosswalk_window
 assert other._cad_handle_items[entity.handle].isSelected()
 w.highlight_ifc_member('');other.canvas.scene.clearSelection();other.canvas.set_mode('cad_select');other.reset_zoom();other.canvas.set_mode('cad_select')
 qitem=other._cad_handle_items[entity.handle];point=other.canvas.mapFromScene(qitem.mapToScene(qitem.line().pointAt(.95)))
 QTest.mouseClick(other.canvas.viewport(),Qt.LeftButton,pos=point);assert w._ifc_selected_global_id==beam.GlobalId
 dialog.grab().save(str(root/'dwg-ifc-inspector.png'));other.grab().save(str(root/'dwg-linked.png'))
 data=quantity_formula_data(service,'P',proposal['id'],'Length',author='author')
 formula.save(service,'P','Q',data,expected_revision=0,reason='Explicit 5m QTO, not material')
 formula.review(service,'P','Q',expected_revision=1,reviewer='reviewer',note='Independent 5m oracle');formula.commit(service,'P','Q',expected_revision=1)
 before=service.store.current_digest('P')
 try:service.commit_drawing_takeoff_to_boq('P',saved['session_id'],[item.id],expected_session_revision=1)
 except ValueError:pass
 else:raise AssertionError('DWG/IFC duplicate paid')
 assert service.store.current_digest('P')==before
 assert service.store.integrity_check()['ok']
 result={'schema':'IFC4','dwg_version':'AC1032','converter':doc.conversion,'oracle_m':'5','ifc_qto_m':data['variables']['Q'],'cad_length_m':item.quantity,'boq_m':service.open_project('P')['boq'][0]['quantity'],'crosswalk':link,'duplicate_rejected_atomically':True,'sqlite_integrity':'ok','native_qt_bidirectional':True,'synthetic':True}
 (root/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
finally:w.close();qt.processEvents();service.store.close()
