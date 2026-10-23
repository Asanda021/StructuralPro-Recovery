import os,sys,json,time,hashlib,subprocess,dataclasses
from pathlib import Path
root=Path('/workspace/scratch/61dce18379e6/p6-ai-real');out=root.parent/'p6-ai-evidence'/os.environ.get('ATTEMPT','attempt2');out.mkdir(exist_ok=True);assets=root.parent/'p6-ai-assets'
os.environ['STRUCTURALPRO_AI_RUNTIME_DIR']=str(assets/'runtime-linux/llama-b10549');os.environ['STRUCTURALPRO_AI_MODEL_DIR']=str(assets)
sys.path[:0]=[str(root),str(root/'tests')]
from PIL import Image,ImageDraw
im=Image.new('RGB',(512,384),'white');d=ImageDraw.Draw(im);d.rectangle((60,60,450,320),outline='black',width=4);d.rectangle((200,140,280,220),outline='red',width=3);d.text((70,30),'SYNTHETIC PLAN - NO SCALE - NO DIMENSIONS',fill='black');d.text((205,175),'OPENING?',fill='black');im.save(out/'plan.png')
from test_phase2_priority5_complete import case
from core.ai.local_engine import LocalAIEngine
sample=out/'sample';sample.mkdir(exist_ok=True)
app,args,ep,allocation=case(sample);project=app.open_project('P');before=app.store.current_digest('P');boq=project['boq']
context={'name':project['name'],'takeoffs':[{'member_code':'B1','quantities':[{'amount':'6','unit':'m','source':'Explicit synthetic IFC R1 QTO Length'}]}]}
(out/'project-input.json').write_text(json.dumps(context,ensure_ascii=False,indent=2))
realrun=subprocess.run;commands=[]
def record(argv,**kw):
 started=time.monotonic();n=len(commands)
 try:r=realrun(argv,**kw)
 except Exception as exc:
  commands.append({'command':argv,'seconds':time.monotonic()-started,'error':str(exc)});(out/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2));raise
 entry={'command':argv,'cwd':kw.get('cwd'),'exit_code':r.returncode,'seconds':time.monotonic()-started}
 (out/f'run-{n}.stdout').write_text(r.stdout or '');(out/f'run-{n}.stderr').write_text(r.stderr or '')
 commands.append(entry);(out/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2));return r
subprocess.run=record
cases=[('standard','A','چرا باید مدارک و بازبینی مستقل قبل از پرداخت بررسی شوند؟ کوتاه و بدون عدد توضیح بده.',None,False),('standard','B','Summarize only the documented member and its recorded length in the supplied evidence. Do not infer materials or prices.',context,False),('standard','C','The slab has no documented length, width or thickness. State what evidence is missing and why no volume can be approved. Do not give numeric examples.',None,False),('pro','vision','Describe visible boundaries and the red rectangle. This is a synthetic unscaled plan. Identify missing evidence. Suggestions only; human review is mandatory.',context,True),('enterprise','vision','Describe the outer and inner boundaries. No documented scale or dimensions exist. Suggestions only; require human review.',context,True)]
results=[]
for edition,label,prompt,data,vision in cases:
 e=LocalAIEngine(edition=edition,n_ctx=4096);started=time.monotonic()
 r=e.answer_with_image(out/'plan.png',prompt,data) if vision else e.answer(prompt,data)
 row={'edition':edition,'scenario':label,'prompt':prompt,'seconds':time.monotonic()-started,'response':dataclasses.asdict(r),'load_error':e._load_error}
 assert r.requires_user_confirmation and not r.quantity_authority
 assert app.store.current_digest('P')==before and app.open_project('P')['boq']==boq
 results.append(row);(out/'real-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(edition,label,r.source,flush=True)
app.store.close();(out/'data-safety.json').write_text(json.dumps({'before_digest':before,'after_digest':before,'boq_unchanged':True,'cases':len(results)}))
