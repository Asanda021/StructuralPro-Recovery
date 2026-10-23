from pathlib import Path
from hashlib import sha256
from decimal import Decimal
from copy import deepcopy
import sys,json
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root/'repo'),str(root/'repo/tests')]
manifest=json.loads((root/'Manifest.json').read_text())
def verify():
 for name,expected in manifest['files'].items():
  path=root/name
  assert path.is_file() and sha256(path.read_bytes()).hexdigest()==expected,name
def comparable(value,key=None):
 # Comparison only: resolve source aliases in a fresh projection. Never mutate
 # approved historical payloads or recompute their signed review digests.
 if isinstance(value,dict):return {k:comparable(v,k) for k,v in value.items()}
 if isinstance(value,list):return [comparable(v) for v in value]
 if key in ('path','source_path','evidence_path','group_evidence_path') and isinstance(value,str):
  p=Path(value);assert p.is_file();resolved=p.resolve();assert resolved.is_relative_to(root)
  return str(resolved)
 return value
verify();aliases=[]
try:
 for original,destination in manifest['path_map'].items():
  source=Path(original);held=source.with_name(source.name+'.independent-held');assert not held.exists()
  if source.exists() or source.is_symlink():source.rename(held)
  source.symlink_to(root/destination,target_is_directory=True);aliases.append((source,held))
 from core.platform.application import StructuralProApp
 from core.drawings.bim_adapter import BIMAdapter
 from core.drawings.ifc_pipeline import crosswalk_group_records
 from core.takeoff.manual_formula_amendments import IFC_TRANSFER,ifc_transfer_payload,effective_takeoffs
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from PySide6.QtWidgets import QApplication
 qt=QApplication.instance() or QApplication([]);receipts=[]
 prefixes=('test_group_transfer_changes_on','test_crosswalk_group_migration','test_group_ownership_and_cross','test_group_documented_delta','test_split_and_merge','test_existing_reports')
 candidates=[p for p in (root/'samples/targeted').iterdir() if p.name.startswith(prefixes)]+list((root/'samples/dwg').iterdir())
 for folder in candidates:
  if not (folder/'app').is_dir():continue
  service=StructuralProApp(folder/'app');project=service.open_project('P');assert service.store.integrity_check()['ok']
  events=[a for a in project.get('manual_formula_amendments',{}).values() if a.get('kind')==IFC_TRANSFER];assert events
  expected=Decimal('12' if 'split_and_merge' in folder.name else '7' if 'documented_delta' in folder.name else '6')
  assert sum(Decimal(str(r['quantity'])) for r in project['boq'])==expected
  current=effective_takeoffs(project,project['takeoffs'])
  for event in events:
   assert Decimal(event['previous_total'])==6 and Decimal(event['current_total'])==(7 if expected==7 else 6)
   assert all(row in project['takeoffs'] for row in event['consumed_rows'])
   assert not {r['source_id'] for r in event['consumed_rows']} & {r['source_id'] for r in current}
   prior=deepcopy(project);prior['manual_formula_amendments'].pop(event['id'])
   payload=ifc_transfer_payload(prior,lineage_id=event['lineage_id'],evidence_path=event['evidence_path'],evidence_sha256=event['evidence_sha256'],author=event['created_by'],reviewer=event['reviewer'],expected_digest=event['expected_project_digest'])
   assert comparable({k:event[k] for k in payload})==comparable(payload)
  for binding in project['ifc_identity_reviews']:
   path=Path(binding['document']['source_path']);assert path.resolve().is_relative_to(root)
   assert BIMAdapter().read_document(path,revision=binding['document']['revision'])['source_sha256']==binding['document']['source_sha256']
  links=[x for x in project.get('ifc_2d_crosswalks',[]) if x.get('lineage_id')]
  for lineage in {x['lineage_id'] for x in links}:
   item=next(x for x in links if x['lineage_id']==lineage);prior=deepcopy(project)
   prior['ifc_2d_crosswalks']=[x for x in project['ifc_2d_crosswalks'] if not x.get('lineage_id')]
   actual=crosswalk_group_records(prior,lineage_id=lineage,evidence_path=item['group_evidence_path'],evidence_sha256=item['group_evidence_sha256'],author=item['author'],reviewer=item['reviewer'],reviewer_role=item['reviewer_role'])
   stable=lambda rows:[{k:v for k,v in r.items() if k!='created_at'} for r in rows]
   assert comparable(stable(actual))==comparable(stable([r for r in links if r['lineage_id']==lineage]))
  if links:
   link=links[-1];w=GraphicalTakeoffDialog(app_service=service,project_id='P');w.show();w.open_drawing(link['ifc_document']['source_path'])
   other=w.open_ifc_crosswalk(link['id']);w.highlight_ifc_member(link['global_id']);qt.processEvents()
   assert any(item.isSelected() for item in w._ifc_handle_items[link['global_id']])
   assert Path(other.session.drawing_source).resolve().is_relative_to(root)
   if other.viewer.kind=='cad':assert other._cad_handle_items[link['drawing']['handle']].isSelected()
   else:assert other.page==link['drawing']['page'] and other.table.currentRow()>=0
   w.close();qt.processEvents()
  receipts.append({'fixture':str(folder.relative_to(root)),'effective_m':str(expected),'groups':len(events),'crosswalks':len(project.get('ifc_2d_crosswalks',[])),'integrity':True});service.store.close()
 assert len(receipts)>=13,receipts
 verify();(root/'readback-receipt.json').write_text(json.dumps({'samples':receipts,'manifest_files':len(manifest['files']),'source_bytes_from_restored_archive_only':True,'signed_records_rewritten':False},indent=2))
 print('PASS independent IFC4/SQLite/BOQ/lineage/Crosswalk/Qt readback:',len(receipts),'samples')
finally:
 for path,held in reversed(aliases):
  if path.is_symlink():path.unlink()
  if held.exists() or held.is_symlink():held.rename(path)
