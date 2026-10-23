from pathlib import Path
import sys,json,shutil,hashlib
repo=Path(sys.argv[1]).resolve();root=Path(sys.argv[2]).resolve();root.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(repo),str(repo/'tests')]
from test_phase2_priority5_complete import test_group_ownership_and_crosswalk_native_qt,test_crosswalk_group_migration_is_append_only_atomic_and_reopens
from core.platform.application import StructuralProApp
receipts=[]
for mode in ('split','merge'):
 folder=root/mode;folder.mkdir()
 test_crosswalk_group_migration_is_append_only_atomic_and_reopens(folder,mode,'dwg')
 app=StructuralProApp(folder/'app');project=app.open_project('P')
 for link in project['ifc_2d_crosswalks']:
  conversion=link['drawing']['conversion'];assert conversion['exit_code']==0 and conversion['provider']=='ACadSharp bridge'
  dwg=Path(link['drawing']['path']);assert dwg.read_bytes()[:6]==b'AC1032'
  assert hashlib.sha256(dwg.read_bytes()).hexdigest()==conversion['source_sha256']
  dxf=Path('/tmp/p5-converted')/(conversion['output_sha256']+'.dxf')
  assert hashlib.sha256(dxf.read_bytes()).hexdigest()==conversion['output_sha256']
  shutil.copy2(dxf,folder/(conversion['output_sha256']+'.dxf'))
 assert app.store.integrity_check()['ok']
 receipts.append({'mode':mode,'boq':project['boq'],'crosswalks':project['ifc_2d_crosswalks'],'amendments':project['manual_formula_amendments'],'integrity':True})
 app.store.close()
for mode in ('split','merge'):
 folder=root/('qt-'+mode);folder.mkdir();test_group_ownership_and_crosswalk_native_qt(folder,'dwg',mode)
(root/'receipt.json').write_text(json.dumps({'real_dwg_version':'AC1032','decoder':'ACadSharp 3.8.0.0 MIT','scenarios':receipts,'qt_split':True,'qt_merge':True},ensure_ascii=False,indent=2))
print('4 real AC1032/IFC4 group scenarios PASS; split, merge, native Qt split and merge; source hashes and SQLite verified')
