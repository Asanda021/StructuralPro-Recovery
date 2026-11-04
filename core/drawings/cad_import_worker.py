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
  # Identical bounded preview policy to DrawingViewerModel: large sources
  # open with exactly one authentic member instead of failing the whole UI.
  from core.drawings.viewer_model import DrawingViewerModel
  viewer=DrawingViewerModel().open(sys.argv[1])
  document=viewer.ifc_document
  if document.source_sha256!=evidence['source_sha256']:raise ValueError('منبع IFC هنگام بارگذاری تغییر کرده است')
  meshes=list(document.meshes)
  header=SimpleNamespace(entities=[],_entity_count=len(meshes),
   _ifc_header=(document.source,document.source_sha256,document.omitted_ids,
                document.source_roster))
  with Path(sys.argv[2]).open('wb') as f:
   pickle.dump(header,f,protocol=5)
   for start in range(0,len(meshes),100):pickle.dump(meshes[start:start+100],f,protocol=5)
  return
 # Exactly the same strict -> source-native display fallback as the
 # synchronous Windows viewer; never fabricate payable CAD evidence here.
 from core.drawings.viewer_model import DrawingViewerModel
 doc=DrawingViewerModel().open(sys.argv[1]).cad_document
 from core.drawings.cad_large_scene import cad_preview_index
 # A large plan may contain millions of vertex coordinates.  Reduce
 # bounds incrementally instead of duplicating all vertices into coords[].
 doc._render_bounds,doc._layer_counts,doc._type_counts=cad_preview_index(doc.entities)
 entities=doc.entities;doc.entities=[];doc._entity_count=len(entities)
 with Path(sys.argv[2]).open('wb') as f:
  pickle.dump(doc,f,protocol=5)
  for start in range(0,len(entities),1000):pickle.dump(entities[start:start+1000],f,protocol=5)
if __name__=='__main__':main()
