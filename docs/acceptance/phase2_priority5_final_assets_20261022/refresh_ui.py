from pathlib import Path
import sys,json,subprocess
sys.path.insert(0,'.')
from core.platform.application import StructuralProApp
from core.collaboration.workspace import User
from PySide6.QtWidgets import QApplication,QLineEdit,QTreeWidget
from PySide6.QtCore import QCoreApplication,QEvent
from app.graphical_takeoff import GraphicalTakeoffDialog
root=Path('/workspace/scratch/61dce18379e6/p5-evidence/samples')
service=StructuralProApp(root/'app');service.collaboration.add_user(User('author','نویسنده آزمون','editor'));service.collaboration.add_user(User('reviewer','بازبین آزمون','reviewer'))
project=service.open_project('P');link=project['ifc_2d_crosswalks'][0]
qt=QApplication.instance() or QApplication([]);w=GraphicalTakeoffDialog(app_service=service,project_id='P');w.show();w.open_drawing(link['ifc_document']['source_path']);w.ifc_revision.setText('R1');w.open_ifc_inspector()
dlg=w._ifc_inspector;dlg.findChild(QLineEdit,'ifc_search').setText(link['global_id']);tree=dlg.findChild(QTreeWidget,'ifc_tree');tree.setCurrentItem(tree.topLevelItem(0).child(0));qt.processEvents();dlg.grab().save(str(root/'ifc-inspector.png'));dlg.close()
other=w.open_ifc_crosswalk(link['id']);w.resize(1400,850);other.resize(1400,850);qt.processEvents();w.grab().save(str(root/'ifc-model.png'));other.grab().save(str(root/'cad-linked.png'))
w.close();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);qt.processEvents();service.store.close()
(root/'execution-tree.json').write_text(json.dumps({'local_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'synthetic_role_registration':True,'financial_writes':False},indent=2))
print('Qt screenshots refreshed from existing SQLite; no financial writes')
