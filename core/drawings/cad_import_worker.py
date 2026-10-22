"""Private subprocess CAD parser; never creates Qt items or modifies projects."""
import sys,pickle
from pathlib import Path
from core.drawings.dwg_takeoff import DWGTakeoffEngine

def main():
 if Path(sys.argv[1]).suffix.lower()=='.ifc':
  from core.bim.ifc import DeepIFCAdapter
  from core.drawings.bim_adapter import BIMAdapter
  from types import SimpleNamespace
  # Same isolated parser transport as CAD; meshes remain display-only.
  evidence=BIMAdapter().read_document(sys.argv[1],revision='unversioned-preview')
  document=DeepIFCAdapter().read_display_meshes(sys.argv[1])
  if document.source_sha256!=evidence['source_sha256']:raise ValueError('منبع IFC هنگام بارگذاری تغییر کرده است')
  meshes=list(document.meshes)
  header=SimpleNamespace(entities=[],_entity_count=len(meshes),_ifc_header=(document.source,document.source_sha256,document.omitted_ids))
  with Path(sys.argv[2]).open('wb') as f:
   pickle.dump(header,f,protocol=5)
   for start in range(0,len(meshes),100):pickle.dump(meshes[start:start+100],f,protocol=5)
  return
 doc=DWGTakeoffEngine.with_array_support().import_file(sys.argv[1])
 from collections import Counter
 doc._layer_counts=Counter(e.layer for e in doc.entities);coords=[]
 for e in doc.entities:
  d=e.data;coords.extend(d.get('display_points',d.get('points',[])))
  for k in ('start','end','center','insert'):
   if d.get(k) is not None:coords.append(d[k])
  if e.entity_type=='CIRCLE':
   x,y=d['center'];r=d['radius'];coords.extend(((x-r,y-r),(x+r,y+r)))
 doc._render_bounds=(min(x for x,y in coords),max(x for x,y in coords),min(y for x,y in coords),max(y for x,y in coords)) if coords else (0,1,0,1)
 entities=doc.entities;doc.entities=[];doc._entity_count=len(entities)
 with Path(sys.argv[2]).open('wb') as f:
  pickle.dump(doc,f,protocol=5)
  for start in range(0,len(entities),1000):pickle.dump(entities[start:start+1000],f,protocol=5)
if __name__=='__main__':main()
