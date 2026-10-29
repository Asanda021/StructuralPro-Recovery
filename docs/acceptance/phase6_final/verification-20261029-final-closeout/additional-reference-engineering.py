# Replay snapshot: source probe ran locally on efaab3c5; paths adjusted for reproducibility. Not a product module.
from pathlib import Path
from collections import Counter
import json,ifcopenshell
from core.drawings.bim_adapter import BIMAdapter
from core.bim.ifc import DeepIFCAdapter
root=Path('/tmp/p6-community-audit')
rows=json.loads((root/'sources.json').read_text())
for i,row in enumerate(rows):
 path=root/(str(i)+'.ifc')
 if not path.exists():continue
 try:
  model=ifcopenshell.open(str(path));row.update(schema=model.schema,element_count=len(model.by_type('IfcElement')),types=dict(Counter(x.is_a() for x in model.by_type('IfcElement'))),site_count=len(model.by_type('IfcSite')))
  document=BIMAdapter().read_document(path,revision='COMMUNITY-SOURCE-AUDIT')
  row.update(engineering_contract='ACCEPTED',source_ledger_count=len(document['elements']))
  contract=DeepIFCAdapter().read_display_contract(path,revision='COMMUNITY-SOURCE-AUDIT')
  row.update(display_contract='ACCEPTED_BOUNDED',quantity_authority=contract['quantity_authority'])
 except Exception as exc:
  row.update(contract_status='REJECTED',error_class=type(exc).__name__)
  # Only controlled short product error category. No raw names or coordinates.
  msg=str(exc)
  row['reason']=('SCHEMA_NOT_IFC4' if 'Schema' in msg else 'SPATIAL_OWNERSHIP_AMBIGUOUS' if 'فضایی' in msg or 'طبقه' in msg else 'QUANTITY_UNIT_UNSUPPORTED' if 'واحد' in msg else 'PLACEMENT_UNSUPPORTED' if 'Placement' in msg else 'GEOMETRY_CAPACITY' if 'ظرفیت' in msg else 'OTHER_CONTRACT_REJECTION')
 print(json.dumps(row),flush=True)
Path('docs/acceptance/phase6_final/verification-20261029-final-closeout/additional-independent-sources.json').write_text(json.dumps(rows,indent=2))
