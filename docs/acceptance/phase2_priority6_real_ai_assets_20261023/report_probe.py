import sys,json,subprocess
from pathlib import Path
root=Path('/workspace/scratch/61dce18379e6/p6-ai-real');sys.path[:0]=[str(root),str(root/'tests')]
from test_phase2_priority5_complete import case
out=root.parent/'p6-ai-evidence/report-sample';out.mkdir(exist_ok=True)
app,args,_,_=case(out);app.apply_ifc_quantity_transfer('P',**args)
before=app.store.current_digest('P')
for fmt in ['pdf','xlsx','docx','csv']:app.export_manual_formula_report('P',out/f'effective.{fmt}',format=fmt)
assert app.store.current_digest('P')==before;app.store.close()
subprocess.run([sys.executable,str(root/'docs/acceptance/phase2_priority6_assets_20261023/report-readback.py'),str(out),str(out/'readback.json')],check=True)
