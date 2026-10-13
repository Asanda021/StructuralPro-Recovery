"""Persistent undo/redo of pending formula edits with monotonic identity epochs."""
from copy import deepcopy
import json,zlib,base64
from core.takeoff.manual_formula_register import read,verified,preserve_originals,graph,text,revision
from core.takeoff.formulas import evaluate_rows

def pack(value):return base64.b64encode(zlib.compress(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode())).decode()
def unpack(value):
    if isinstance(value,dict):return deepcopy(value)
    try:return json.loads(zlib.decompress(base64.b64decode(value,validate=True)))
    except Exception as exc:raise ValueError('تصویر تاریخچه فرمول معتبر نیست') from exc

def record(project,before,after,reason):
    stack=project.setdefault('manual_formula_undo',[])
    stack.append({'before':pack(before),'after':pack(after),'reason':reason})
    project['manual_formula_redo']=[]
    epochs=project.setdefault('manual_formula_epochs',{})
    for k,v in after.items():epochs[k]=max(epochs.get(k,0),v['revision'])

def delete(service,pid,keys,*,expected_revisions,reason):
    reason=text(reason,'علت حذف');project,token=read(service,pid);reg=verified(project);before=deepcopy(reg)
    if not keys or len(keys)!=len(set(keys)) or set(keys)!=set(expected_revisions):raise ValueError('انتخاب و نسخه‌ها باید صریح باشند')
    for k in keys:
        revision(expected_revisions[k],reg[k]['revision'])
        if reg[k]['status']=='committed':raise ValueError('فرمول مورد استفاده در BOQ قطعی قابل حذف نیست')
    if any(set(r['data']['references'].values()) & set(keys) for k,r in reg.items() if k not in keys):raise ValueError('فرمول مرجع ردیف دیگر قابل حذف نیست')
    for k in keys:project.setdefault('manual_formula_deleted',{})[k]=deepcopy(reg.pop(k))
    evaluate_rows(graph(reg));record(project,before,reg,reason);project['manual_formula_register']=preserve_originals(project,reg)
    service.store.save(pid,project,expected_digest=token);return deepcopy(reg)

def step(service,pid,*,redo=False):
    project,token=read(service,pid);reg=verified(project);name='manual_formula_redo' if redo else 'manual_formula_undo';other='manual_formula_undo' if redo else 'manual_formula_redo';stack=project.get(name,[])
    if not stack:raise ValueError('عملیات قابل واگرد یا تکرار وجود ندارد')
    operation=stack[-1];target=unpack(operation['after' if redo else 'before'])
    for k,r in reg.items():
        if r['status']=='committed' and target.get(k)!=r:raise ValueError('واگرد یا تکرار مقدار قطعی را تغییر می‌دهد')
    # Undo never revives a stale approval. Every restored row receives a fresh
    # version, including rows recovered after deletion.
    epochs=project.setdefault('manual_formula_epochs',{})
    for k,r in target.items():
        if r['status']=='committed':continue
        epochs[k]=max(epochs.get(k,0),reg.get(k,{}).get('revision',0),r['revision'])+1
        r.update(revision=epochs[k],status='draft');r.pop('review',None)
    values=evaluate_rows(graph(target))
    for k,r in target.items():r['quantity']=values[k]
    for k,r in reg.items():
        if k not in target:project.setdefault('manual_formula_deleted',{})[k]=deepcopy(r)
    for k in target:project.setdefault('manual_formula_deleted',{}).pop(k,None)
    stack.pop();project.setdefault(other,[]).append(operation)
    project['manual_formula_register']=preserve_originals(project,target)
    project.setdefault('manual_formula_history',[]).append({'row_id':'گروه','revision':0,'reason':('تکرار: ' if redo else 'واگرد: ')+operation['reason'],'previous':reg,'at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()})
    service.store.save(pid,project,expected_digest=token);return deepcopy(target)
