# Replay snapshot: source probe ran locally on efaab3c5; paths adjusted for reproducibility. Not a product module.
from pathlib import Path
import hashlib,json
from scripts.diagnostics.p6_g2_heating_sanitary_original_ui import examine,pump
from PySide6.QtWidgets import QApplication
from app.graphical_takeoff import GraphicalTakeoffDialog
out=Path('docs/acceptance/phase6_final/verification-20261029-final-closeout')
path=Path('/tmp/p6-community-audit/0.ifc');sha=hashlib.sha256(path.read_bytes()).hexdigest()
result='previous-evidence-retained'
print('original GUI exit',result,flush=True)
app=QApplication.instance() or QApplication([]);gui=GraphicalTakeoffDialog();gui.show();report={'status':'NOT_EXECUTED','source_sha256':sha}
try:
 gui.ifc_revision.setText("COMMUNITY-INDEPENDENT-SOURCE");gui.open_cad_async(path)
 assert pump(app,lambda:gui._cad_job is None)
 gui.open_ifc_3d();assert pump(app,lambda:gui._ifc_3d_loader is None)
 view=gui._ifc_3d_dialog
 covers=[x for x in view.scene.display_catalog['members'] if x['ifc_type']=='IfcCovering' and x['status']!='without_geometry']
 assert covers
 view.batch_type.setCurrentIndex(view.batch_type.findData('IfcCovering'));view.batch_size.setValue(1);view.batch_page.setValue(1)
 assert view.request_selected_batch();assert pump(app,lambda:gui._ifc_3d_loader is None)
 scene=view.scene;scene.validate_source();assert scene.source_sha256==sha
 assert len(scene.meshes)==1 and scene.meshes[0].ifc_type=='IfcCovering'
 view.canvas.choose_member(scene.meshes[0].global_id);assert view.canvas.selected_id==scene.meshes[0].global_id
 assert not gui.session.items and scene.quantity_authority is False
 report.update(status='PASS_REAL_IFCCOVERING_BATCH_AND_PICK',source_member_count=scene.display_catalog['source_member_count'],source_covering_count=len(covers),displayed=1,quantity_authority=False,boq_written=False)
except Exception as e:
 import traceback;traceback.print_exc();report.update(status='BLOCKED',error_class=type(e).__name__)
finally:
 gui.cancel_ifc_3d_loading();gui.close();app.processEvents();(out/'additional-covering-original-gui.json').write_text(json.dumps(report,indent=2));print(report)
