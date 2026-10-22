from pathlib import Path
import json,hashlib,zipfile,subprocess,sys,os
root=Path('/workspace/scratch/61dce18379e6/p5-evidence');archive=root/'downloaded.zip';expected=(root/'archive.sha256').read_text().strip()
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
restore=root/'restored';restore.mkdir()
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
 z.extractall(restore)
manifest=json.loads((restore/'Manifest.json').read_text())
for name,digest in manifest['files'].items():assert hashlib.sha256((restore/name).read_bytes()).hexdigest()==digest,name
code=restore/'code';code.mkdir()
def git(*args):return subprocess.run(['git',*args],check=True,capture_output=True,text=True).stdout.strip()
git('init',str(code));git('-C',str(code),'fetch',str(restore/'repository.bundle'),'refs/remotes/origin/feature/phase2-priority1-pdf-specialist-takeoff-20261020');git('-C',str(code),'checkout','--detach',manifest['code_head']);git('-C',str(code),'fsck','--full')
assert git('-C',str(code),'rev-parse','HEAD^{tree}')==manifest['code_tree']
receipt={'archive_sha256':expected,'manifest_files':len(manifest['files']),'head':manifest['code_head'],'tree':manifest['code_tree'],'git_fsck_exit':0,'source_paths_rewritten':False,'root_mapping':'Original task samples moved aside; original path aliases only restored files during readback.'}
# An explicit filesystem root map preserves original immutable SQLite approvals.
original=Path(manifest['original_sample_root']);held=original.with_name('samples-original-held');original.rename(held);original.symlink_to(restore/'samples',target_is_directory=True)
try:
 os.chdir(code);sys.path.insert(0,str(code))
 from core.platform.application import StructuralProApp
 from core.drawings.bim_adapter import BIMAdapter
 from core.collaboration.workspace import User
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import QCoreApplication,QEvent
 from app.graphical_takeoff import GraphicalTakeoffDialog
 app=StructuralProApp(restore/'samples/app');project=app.open_project('P');link=project['ifc_2d_crosswalks'][0]
 for path in [link['evidence_path'],link['ifc_document']['source_path'],link['drawing']['path']]:assert Path(path).resolve().is_relative_to(restore)
 doc=BIMAdapter().read_document(link['ifc_document']['source_path'],revision=link['ifc_document']['revision']);assert doc['source_sha256']==link['ifc_document']['source_sha256']
 assert project['boq'][0]['quantity']==4 or str(project['boq'][0]['quantity'])=='4'
 qt=QApplication.instance() or QApplication([]);w=GraphicalTakeoffDialog(app_service=app,project_id='P');w.show();w.open_drawing(link['ifc_document']['source_path']);other=w.open_ifc_crosswalk(link['id']);qt.processEvents()
 assert w._ifc_selected_global_id in (None,link['global_id'])
 assert other._cad_handle_items[link['drawing']['handle']].isSelected()
 w.close();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);qt.processEvents()
 receipt.update(ifc_elements=len(doc['elements']),storeys=len(doc['storeys']),sqlite_integrity=app.store.integrity_check(),boq_rows=len(project['boq']),crosswalks=len(project['ifc_2d_crosswalks']),approved_identities=len(project['ifc_identity_reviews']),crosswalk_qt_readback=True)
 app.store.close()
 revision=StructuralProApp(restore/'samples/revision/app');p=revision.open_project('P');assert str(p['boq'][0]['quantity'])=='5' and str(p['takeoffs'][0]['quantities'][0]['amount'])=='4';receipt['amendment_original_m']='4';receipt['amendment_effective_m']='5';receipt['amendments']=len(p['manual_formula_amendments']);revision.store.close()
finally:
 original.unlink();held.rename(original)
(root/'restore-pretest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False))
