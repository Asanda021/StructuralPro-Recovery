"""Versioned manual formula orchestration over the existing evaluator/store/BOQ.

No specialised engineering assumptions or alternative calculation engine.
"""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
import ast
from pathlib import Path
from core.takeoff.formulas import evaluate_rows
from core.takeoff.units import normalize_unit
from core.takeoff.commit_guards import require_source_unused,validate_commit_rows,rebuild_project_boq
from core.commercial.exact_values import number

POLICY='decimal512_exact_no_rounding_v1'

def catalog():
    path=Path(__file__).resolve().parents[2]/'docs/aec_priority_1_9_master_inventory_20261013.json'
    rows=json.loads(path.read_text())['items']
    if len(rows)!=85 or len({r['code'] for r in rows})!=85:raise ValueError('کتابخانه مرجع خانواده‌ها نامعتبر است')
    return deepcopy(rows)

def text(value,label):
    if not isinstance(value,str) or not value.strip() or len(value)>4096:raise ValueError(label+' باید صریح و معتبر باشد')
    return value.strip()

def revision(value,current):
    if type(value) is not int or value!=current:raise RuntimeError('نسخه ردیف تغییر کرده است')

def clean(data):
    if not isinstance(data,dict):raise ValueError('ساختار ورودی فرمول نامعتبر است')
    allowed={'family','title','floor','member','unit','expression','variables','references','source_id','basis','deductions','block','location','variable_units','unit_policy','ifc_evidence'}
    if set(data)-allowed:raise ValueError('فیلد تعریف‌نشده در قرارداد فرمول')
    d=deepcopy(data)
    for k,label in {'family':'خانواده','title':'شرح','floor':'طبقه','member':'شناسه عضو','expression':'فرمول','source_id':'منبع','basis':'مبنای محاسبه و واحد ورودی‌ها'}.items():d[k]=text(d.get(k),label)
    if d['family'] not in {r['code'] for r in catalog()}:raise ValueError('خانواده در کتابخانه مرجع نیست')
    for k in ('block','location'):
        if k in d:d[k]=text(d[k],'بلوک یا محل')
    d['unit']=normalize_unit(d.get('unit'))
    for key in ('variables','references'):
        if not isinstance(d.get(key),dict) or len(d[key])>128:raise ValueError('پارامترها و مراجع باید صریح باشند')
        if any(not isinstance(k,str) or not k.isidentifier() or len(k)>64 for k in d[key]):raise ValueError('نام پارامتر معتبر نیست')
    for k,v in d['variables'].items():number(v,'پارامتر '+k,True)
    if 'variable_units' in d or 'unit_policy' in d:
        if d.get('unit_policy')!='dimensional_decimal_v1' or not isinstance(d.get('variable_units'),dict) or set(d['variable_units'])!=set(d['variables']):raise ValueError('واحد ساختاریافته همه پارامترها باید صریح و نسخه‌دار باشد')
        d['variable_units']={k:normalize_unit(v) for k,v in d['variable_units'].items()}
    for k,v in d['references'].items():d['references'][k]=text(v,'مرجع ردیف')
    deductions=d.get('deductions',[])
    if not isinstance(deductions,list) or len(deductions)>128:raise ValueError('فهرست کسورات نامعتبر است')
    ids=set()
    for item in deductions:
        if not isinstance(item,dict) or set(item) not in ({'id','quantity','unit','basis'},{'id','variable','quantity','unit','basis','source_id'}):raise ValueError('کسر به شناسه، مقدار، واحد و مبنا نیاز دارد')
        sid=text(item['id'],'شناسه کسر');text(item['basis'],'مبنای کسر');number(item['quantity'],'مقدار کسر')
        if sid in ids or normalize_unit(item['unit'])!=d['unit']:raise ValueError('کسر تکراری یا واحد ناسازگار است')
        variable=item.get('variable',sid)
        if 'source_id' in item:text(item['source_id'],'منبع هندسی کسر')
        if not isinstance(variable,str) or not variable.isidentifier() or variable not in d['variables'] or number(d['variables'][variable],'پارامتر کسر')!=number(item['quantity'],'کسر'):
            raise ValueError('کسر باید به پارامتر همنام و مقدار دقیق در فرمول متصل باشد')
        # A quantity documented in m3 cannot be subtracted as the same numeric
        # value in cm3: both share a dimension, but their physical amounts differ.
        # The deduction variable is an exact *unconverted* copy of item.quantity.
        # Fail closed on any scale mismatch instead of silently changing the BOQ.
        if 'variable_units' in d and d['variable_units'].get(variable)!=normalize_unit(item['unit']):
            raise ValueError('واحد پارامتر کسر باید دقیقاً با واحد مستند کسر برابر باشد')
        try:tree=ast.parse(d['expression'],mode='eval')
        except (SyntaxError,ValueError) as exc:raise ValueError('فرمول کسر معتبر نیست') from exc
        subtracts=[n for n in ast.walk(tree) if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Sub) and isinstance(n.right,ast.Name) and n.right.id==variable]
        if len(subtracts)!=1:raise ValueError('کسر باید دقیقاً یک‌بار به‌صورت صریح در فرمول کم شود')
        ids.add(sid)
    # Deductions are documentary inputs; the expression must explicitly incorporate
    # them. Never silently subtract them a second time.
    d['deductions']=deductions
    return d

def graph(register):return {k:{'expression':r['data']['expression'],'variables':r['data']['variables'],'references':r['data']['references'],'unit':r['data']['unit'],**{k:r['data'][k] for k in ('variable_units','unit_policy') if k in r['data']}} for k,r in register.items()}

def fingerprints(register):
    out={}
    def visit(k):
        if k not in out:
            row=register[k];refs={n:visit(t) for n,t in row['data']['references'].items()}
            out[k]=sha256(json.dumps({'data':row['data'],'references':refs,'policy':POLICY},sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        return out[k]
    for k in register:visit(k)
    return out

def read(service,pid):
    pid=text(pid,'پروژه');digest=service.store.current_digest(pid);service.store._cache.pop(pid,None)
    project=service.store.get(pid)
    if project is None:raise KeyError(pid)
    return deepcopy(project),digest

def verified(project):
    register=deepcopy(project.get('manual_formula_register',{}))
    if not isinstance(register,dict):raise ValueError('دفتر فرمول نامعتبر است')
    for row in register.values():
        if clean(row['data'])!=row['data'] or row.get('numeric_policy')!=POLICY:raise ValueError('قرارداد یا سیاست فرمول ذخیره‌شده معتبر نیست')
    from core.takeoff.manual_formula_amendments import effective
    register=effective(project,register)
    values=evaluate_rows(graph(register));digests=fingerprints(register)
    for key,row in register.items():
        if number(row['quantity'],'مقدار ذخیره‌شده')!=number(values[key],'محاسبه مجدد'):raise ValueError('مقدار ذخیره‌شده با فرمول مطابقت ندارد')
        if row['status'] in {'reviewed','committed'} and row.get('review',{}).get('digest')!=digests[key]:raise ValueError('بازبینی فرمول با ورودی‌ها مطابقت ندارد')
    return register

def preserve_originals(project,register):
    result=deepcopy(register)
    for key,row in project.get('manual_formula_register',{}).items():
        if row.get('status')=='committed':result[key]=deepcopy(row)
    return result

def save_many(service,pid,changes,*,expected_revisions,reason,expected_dependencies=None):
    reason=text(reason,'علت ثبت یا اصلاح');project,digest=read(service,pid);register=verified(project);before=deepcopy(register)
    for target,expected in (expected_dependencies or {}).items():
        if target not in register:raise RuntimeError('ردیف منبع کپی حذف شده است')
        revision(expected,register[target]['revision'])
    if not isinstance(changes,dict) or not changes or set(changes)!=set(expected_revisions):raise ValueError('ردیف‌ها و نسخه‌های گروهی باید صریح باشند')
    for key,data in changes.items():
        text(key,'شناسه ردیف');old=register.get(key);
        if not old and key in project.get('manual_formula_deleted',{}):raise ValueError('شناسه حذف‌شده فقط با واگرد قابل بازیابی است')
        revision(expected_revisions[key],old['revision'] if old else 0);d=clean(data)
        from core.drawings.ifc_pipeline import validate_quantity_handoff
        validate_quantity_handoff(service,project,d)
        if 'variable_units' not in d:raise ValueError('ثبت یا ویرایش تازه نیازمند تعیین صریح واحد ساختاریافته همه پارامترها است')
        if old and 'variable_units' in old['data'] and 'variable_units' not in d:raise ValueError('حذف قرارداد واحد ساختاریافته مجاز نیست')
        if old and old['status']=='committed':raise ValueError('ردیف قطعی قابل تغییر مستقیم نیست')
        if old and d['source_id']!=old['data']['source_id']:raise ValueError('هویت منبع در ویرایش قابل تغییر نیست')
        require_source_unused(project,d['source_id'])
        if d['source_id'] in project.get('deleted_takeoff_sources',[]):raise ValueError('منبع قبلاً استفاده و حذف شده است')
        register[key]={'data':d,'revision':(old['revision'] if old else 0)+1,'status':'draft','numeric_policy':POLICY}
    locations=[(r['data'].get('block',''),r['data']['floor'],r['data'].get('location',''),r['data']['family'],r['data']['member']) for r in register.values()]
    if len(locations)!=len(set(locations)):raise ValueError('همین عضو در همین عملیات و طبقه دوباره متره شده است')
    deduction_sources=[v.get('source_id',v['id']) for r in register.values() for v in r['data']['deductions']]
    if len(deduction_sources)!=len(set(deduction_sources)):raise ValueError('منبع هندسی کسر دوباره استفاده شده است')
    sources=[r['data']['source_id'] for r in register.values()]
    if len(sources)!=len(set(sources)):raise ValueError('منبع فرمول تکراری است')
    values=evaluate_rows(graph(register));oldhash=fingerprints(before);newhash=fingerprints(register);now=datetime.now(timezone.utc).isoformat()
    history=project.setdefault('manual_formula_history',[])
    for k,row in register.items():
        if number(values[k],'مقدار فرمول',True)<0:raise ValueError('مقدار متره نمی‌تواند منفی باشد')
        changed=k not in before or oldhash.get(k)!=newhash[k] or k in changes
        if changed:
            prev=before.get(k)
            if prev and prev['status']=='committed':raise ValueError('اصلاح موجب تغییر منبع وابسته قطعی می‌شود؛ مسیر اصلاح قطعی لازم است')
            if prev and k not in changes:row['revision']=prev['revision']+1
            row.update(status='draft',quantity=values[k],updated_at=now);row.pop('review',None)
            history.append({'row_id':k,'reason':reason,'at':now,'previous':prev,'revision':row['revision']})
    from core.takeoff.manual_formula_history import record
    record(project,before,register,reason)
    project['manual_formula_register']=preserve_originals(project,register);service.store.save(pid,project,expected_digest=digest);return deepcopy(register)

def save(service,pid,key,data,*,expected_revision,reason):
    return save_many(service,pid,{key:data},expected_revisions={key:expected_revision},reason=reason)[key]

def bulk_edit(service,pid,keys,*,changes,expected_revisions,reason):
    reg=load(service,pid)
    if not keys or len(keys)!=len(set(keys)) or set(keys)!=set(expected_revisions):raise ValueError('انتخاب و نسخه‌ها باید یکتا باشند')
    if not isinstance(changes,dict) or not changes or set(changes)-{'variables','variable_units','floor','member','title'}:raise ValueError('فیلد گروهی مجاز نیست')
    proposed={}
    for key in keys:
        row=reg[key];revision(expected_revisions[key],row['revision']);d=deepcopy(row['data'])
        for field,val in changes.items():
            if field in {'variables','variable_units'}:
                if not isinstance(val,dict) or not val or set(val)-set(d.get(field,{})):raise ValueError('ویرایش گروهی فقط پارامتر موجود را تغییر می‌دهد')
                d[field].update(val)
            else:d[field]=val
        proposed[key]=d
    return save_many(service,pid,proposed,expected_revisions=expected_revisions,reason=reason)

def copy_rows(service,pid,keys,*,floor,expected_revisions,reason):
    from uuid import uuid4
    reg=load(service,pid);floor=text(floor,'طبقه مقصد')
    if not keys or len(keys)!=len(set(keys)) or set(keys)!=set(expected_revisions):raise ValueError('انتخاب و نسخه‌ها باید یکتا باشند')
    mapping={k:'MF-'+uuid4().hex for k in keys};changes={}
    for key in keys:
        row=reg[key];revision(expected_revisions[key],row['revision']);d=deepcopy(row['data'])
        if d['floor']==floor:raise ValueError('کپی در همان طبقه نیازمند هویت مستقل است')
        if d['deductions']:raise ValueError('کپی کسورات به هویت و ورودی صریح جدید نیاز دارد')
        if set(d['references'].values())-set(keys):raise ValueError('برای کپی وابستگی باید همه ردیف‌های مرجع انتخاب شوند')
        d.update(floor=floor,source_id='manual-formula:'+uuid4().hex,references={n:mapping[t] for n,t in d['references'].items()})
        changes[mapping[key]]=d
    save_many(service,pid,changes,expected_revisions={k:0 for k in changes},reason=reason,expected_dependencies=expected_revisions);return mapping

def load(service,pid):return verified(read(service,pid)[0])

def review(service,pid,key,*,expected_revision,reviewer,note):
    reviewer=text(reviewer,'بازبین');note=text(note,'یادداشت کنترل فرمول و واحد');project,digest=read(service,pid);reg=verified(project);row=reg[key];revision(expected_revision,row['revision'])
    from core.drawings.ifc_pipeline import validate_quantity_handoff
    validate_quantity_handoff(service,project,row['data'],reviewer=reviewer)
    if row['status']=='committed':raise ValueError('ردیف قطعی دوباره بازبینی نمی‌شود')
    if 'variable_units' not in row['data']:raise ValueError('ردیف تاریخی بدون قرارداد واحد نیازمند مهاجرت صریح و بازبینی است')
    row.update(status='reviewed',review={'reviewer':reviewer,'note':note,'digest':fingerprints(reg)[key],'at':datetime.now(timezone.utc).isoformat()})
    project['manual_formula_register']=preserve_originals(project,reg);service.store.save(pid,project,expected_digest=digest);return deepcopy(row)

def commit(service,pid,key,*,expected_revision):
    project,digest=read(service,pid);reg=verified(project);r=reg[key];revision(expected_revision,r['revision'])
    if 'variable_units' not in r['data']:raise ValueError('انتقال تازه بدون قرارداد واحد ساختاریافته مجاز نیست')
    if r['status']!='reviewed':raise ValueError('انتقال فقط برای فرمول بازبینی‌شده مجاز است')
    d=r['data'];sid=d['source_id'];amount=r['quantity']
    from core.drawings.ifc_pipeline import validate_quantity_handoff
    validate_quantity_handoff(service,project,d,reviewer=r.get('review',{}).get('reviewer'))
    if number(amount,'مقدار')<=0:raise ValueError('مقدار انتقال باید مثبت باشد')
    row={'id':'manual-formula:'+key,'source_id':sid,'member_code':d['member'],'domain':'building','item':d['family'],'params':{**deepcopy(d),'intersections':[deepcopy(v) for v in d['deductions']]},'revision':r['revision'],'system':d['floor'],'description':d['title'],'review':deepcopy(r['review']),'provenance':{'mode':'manual_formula','source_id':sid,'row_id':key,'numeric_policy':POLICY},'quantities':[{'code':d['family'],'title':d['title'],'unit':d['unit'],'amount':amount,'formula':d['expression'],'role':'work','price_code':None,'unit_price':None}]}
    validated=validate_commit_rows(project,[row],source_id=sid)
    project['takeoffs'],project['boq']=rebuild_project_boq(project,project.get('takeoffs',[])+validated)
    r['status']='committed';project['manual_formula_register']=preserve_originals(project,reg);service.store.save(pid,project,expected_digest=digest);return deepcopy(row)
