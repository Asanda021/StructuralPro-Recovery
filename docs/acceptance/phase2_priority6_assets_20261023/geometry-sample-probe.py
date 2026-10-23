from pathlib import Path
import sys,json
root=Path('/tmp/p6-geometry-sample');root.mkdir(exist_ok=True)
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from test_phase2_priority5_closure import identity_case
from core.ai.project_assistant import ProjectAssistant
from core.platform.application import StructuralProApp
app,path,proof,proposal,args=identity_case(root)
app.review_ifc_identity('P',**args)
before=app.store.current_digest('P')
result=app.ifc_display_geometry('P',proposal['id'])
(root/'geometry-contract.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
qa=ProjectAssistant().review(app.open_project('P'))
(root/'advisory-qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
assert app.store.current_digest('P')==before
app.store.close();app=StructuralProApp(root/'app')
assert app.ifc_display_geometry('P',proposal['id'])==result
assert app.store.integrity_check()['ok']
(root/'receipt.json').write_text(json.dumps({'status':'PASS','project_id':'P','proposal_id':proposal['id'],'source_sha256':result['geometry']['source_sha256'],'digest_unchanged':before,'display_dimension':3,'quantity_authority':False,'sqlite_reopened':True},indent=2))
app.store.close();print('Reviewed IFC geometry and advisory QA roundtrip PASS; no BOQ writes')
