"""Read restored bytes using audited aliases, never rewrite approval source paths."""
from pathlib import Path
from decimal import Decimal
from contextlib import ExitStack,contextmanager
import json,sys,sqlite3

repo=Path(sys.argv[1]).resolve();bundle=Path(sys.argv[2]).resolve();output=Path(sys.argv[3]).resolve()
sys.path.insert(0,str(repo))
from core.platform.application import StructuralProApp
from core.drawings.bim_adapter import BIMAdapter
from app.graphical_takeoff import GraphicalTakeoffDialog
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent

@contextmanager
def alias(original,replacement):
    original=Path(original);held=Path(str(original)+'.p5-restore-held')
    if held.exists():raise RuntimeError('Existing held path; refusing overwrite')
    existed=original.exists()
    if existed:original.rename(held)
    original.parent.mkdir(parents=True,exist_ok=True);original.symlink_to(replacement,target_is_directory=True)
    try:yield
    finally:
        original.unlink()
        if existed:held.rename(original)

paths=json.loads((repo/'docs/acceptance/phase2_priority5_verified_assets_20261022/sample-paths.json').read_text())
ui=bundle/'samples/ui';dwg=bundle/'samples/dwg';receipts=[]
qt=QApplication.instance() or QApplication([])
with ExitStack() as stack:
    stack.enter_context(alias(paths['final_ui_original'],ui))
    stack.enter_context(alias(paths['dwg_original'],dwg))
    patterns=[('generic','test_generic_ifc_amendment_nat*'),('column','test_ifc_column_revision_amend*'),('migration','test_crosswalk_revision_migrat*'),('pdf','test_multipage_pdf_ifc_native_*')]
    for kind,pattern in patterns:
        case=next(x for x in ui.glob(pattern) if x.is_dir() and not x.is_symlink())
        service=StructuralProApp(case/'app');project=service.open_project('P')
        assert service.store.integrity_check()['ok']
        if kind=='generic':assert project['boq'][0]['quantity']==5 and Decimal(str(project['takeoffs'][0]['quantities'][0]['amount']))==4
        if kind=='column':assert any(str(x['quantity']) in ('0.75','.75') for x in project['boq'] if x['unit']=='m3')
        links=project.get('ifc_2d_crosswalks',[])
        r={'scenario':kind,'takeoffs':len(project['takeoffs']),'boq':project['boq'],'crosswalks':len(links),'integrity':'ok'}
        if links:
            link=links[-1];source=Path(link['ifc_document']['source_path'])
            assert source.resolve().is_relative_to(bundle)
            d=BIMAdapter().read_document(source,revision=link['ifc_document']['revision']);assert d['source_sha256']==link['ifc_document']['source_sha256']
            w=GraphicalTakeoffDialog(app_service=service,project_id='P');w.open_drawing(str(source));w.ifc_revision.setText(link['ifc_document']['revision'])
            other=w.open_ifc_crosswalk(link['id']);assert Path(other.viewer.path).resolve().is_relative_to(bundle)
            if kind=='pdf':assert other.page==2
            else:assert other._cad_handle_items[link['drawing']['handle']].isSelected()
            w.close();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);qt.processEvents();r['native_qt_restored_crosswalk']=True
        receipts.append(r);service.store.close()
    service=StructuralProApp(dwg/'app');p=service.open_project('P');assert p['boq'][0]['quantity']==5 and service.store.integrity_check()['ok']
    link=p['ifc_2d_crosswalks'][0];assert link['drawing']['conversion']['provider']=='ACadSharp bridge'
    source=Path(link['ifc_document']['source_path']);assert source.resolve().is_relative_to(bundle)
    w=GraphicalTakeoffDialog(app_service=service,project_id='P');w.open_drawing(str(source));w.ifc_revision.setText('R1');other=w.open_ifc_crosswalk(link['id'])
    assert other._cad_handle_items[link['drawing']['handle']].isSelected();w.close();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);qt.processEvents()
    receipts.append({'scenario':'dwg','boq_m':5,'dwg_sha256':link['drawing']['source_sha256'],'conversion':link['drawing']['conversion'],'native_qt_restored_crosswalk':True,'integrity':'ok'});service.store.close()
    # The split/merge samples remain explicitly nonfinancial. Their evidence and
    # real IFC inputs are restored; no unimplemented payment transfer is claimed.
    for case in ui.glob('test_real_ifc_lineage_quantity*'):
        if case.is_symlink() or not (case/'app').exists():continue
        service=StructuralProApp(case/'app');p=service.open_project('P');assert len(p['ifc_identity_lineages'])==1 and p['boq']==[]
        event=p['ifc_identity_lineages'][0]
        for item in p['ifc_identity_reviews']:
            path=Path(item['document']['source_path']);assert path.resolve().is_relative_to(bundle);BIMAdapter().read_document(path,revision=item['document']['revision'])
        receipts.append({'scenario':'lineage-'+event['mode'],'nonfinancial':True,'boq':p['boq'],'integrity':service.store.integrity_check()['ok']});service.store.close()
output.write_text(json.dumps({'restored_root':str(bundle),'code_head':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'readback':receipts},ensure_ascii=False,indent=2))
print('Restored IFC/SQLite/native crosswalk/amendment/lineage readback PASS')
