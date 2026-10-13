"""Immutable takeoff correction journal; existing evaluator and BOQ remain shared."""
from copy import deepcopy
from hashlib import sha256
from datetime import datetime,timezone
from uuid import uuid4
import json
from core.takeoff.manual_formula_register import clean,read,verified,graph,fingerprints,revision,text,POLICY
from core.takeoff.formulas import evaluate_rows
from core.commercial.exact_values import number

FIELDS=('manual_formula_amendments','manual_formula_applied')

def digest(value):return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def effective(project,register):
    result=deepcopy(register)
    for key,aid in project.get('manual_formula_applied',{}).items():
        a=project.get('manual_formula_amendments',{})[aid];original=register[key]
        if a['status']!='applied' or a['row_id']!=key or a['original_digest']!=digest(original) or a['review']['digest']!=digest(a['proposal']):raise ValueError('اصلاحیه مؤثر با اصل و بازبینی مطابقت ندارد')
        result[key]={**deepcopy(original),'data':deepcopy(a['proposal']),'quantity':a['quantity'],'revision':a['base_revision']+1,'review':{'digest':'pending','reviewer':a['review']['reviewer']},'amendment_id':aid}
    # The original approval does not approve the changed graph. New effective rows
    # are bound to their correction review; original committed dependents cannot
    # change implicitly (apply blocks that case).
    hashes=fingerprints(result)
    for row in result.values():
        if row.get('amendment_id'):row['review']['digest']=hashes[next(k for k,v in result.items() if v is row)]
    return result

def financial_block(project):
    for name in ('statement_periods','estimate','contract','contracts','financial_requests','contract_change_requests','settlement_requests','statement_amendments','commercial_contract','contract_basis','finance','finance_ledger','payments','commercial_finance','project_finance','financial_policy','user_pricebook_review','financial_owner_id','statement_amendment_policy'):
        if project.get(name):raise ValueError('اعمال اصلاح متره به مبنای مالی نیازمند گردش الحاقیه یا مجوز مالی مستقل است')
    if any(project.get('metadata',{}).get(k) for k in ('contract','financial_policy','financial_owner_id')):raise ValueError('سیاست یا قرارداد مالی نیازمند مجوز مستقل است')
    if any(row.get('unit_price') is not None or row.get('price_code') for row in project.get('boq',[])):
        raise ValueError('مبنای دارای نرخ مالی نیازمند مجوز مستقل است')

def proposal(service,pid,key,data,*,expected_revision,created_by,reason):
    actor=text(created_by,'سازنده اصلاحیه');reason=text(reason,'علت اصلاح');project,token=read(service,pid);reg=verified(project);old=reg[key];revision(expected_revision,old['revision'])
    if old['status']!='committed':raise ValueError('اصلاحیه فقط برای ردیف قطعی است')
    d=clean(data)
    for field in ('source_id','family','unit','member','floor','references'):
        if d[field]!=old['data'][field]:raise ValueError('تغییر هویت، محل، واحد یا مراجع نیازمند گردش مستقل است')
    candidate=deepcopy(reg);candidate[key]['data']=d;values=evaluate_rows(graph(candidate))
    if number(values[key],'مقدار اصلاح')<=0:raise ValueError('مقدار اصلاح باید مثبت باشد')
    a={'id':'MA-'+uuid4().hex,'row_id':key,'source_id':d['source_id'],'revision':1,'base_revision':old['revision'],'created_by':actor,'reason':reason,'created_at':datetime.now(timezone.utc).isoformat(),'original_digest':digest(project['manual_formula_register'][key]),'base_digest':digest(old),'proposal':d,'quantity':values[key],'status':'draft','numeric_policy':POLICY}
    project.setdefault('manual_formula_amendments',{})[a['id']]=a
    service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'create','id':a['id']});return deepcopy(a)

def check_base(project,a):
    current=verified(project)[a['row_id']]
    if current['revision']!=a['base_revision'] or digest(current)!=a['base_digest']:raise RuntimeError('مبنای اصلاحیه تغییر کرده است؛ اصلاحیه تازه لازم است')
    return current

def review(service,pid,aid,*,expected_revision,reviewer,note):
    actor=text(reviewer,'بازبین مستقل');note=text(note,'یادداشت کنترل');project,token=read(service,pid);a=project['manual_formula_amendments'][aid];revision(expected_revision,a['revision']);check_base(project,a)
    if a['status']!='draft':raise ValueError('اصلاحیه قابل بازبینی نیست')
    if actor.casefold()==a['created_by'].casefold():raise ValueError('سازنده نمی‌تواند بازبین اصلاحیه خودش باشد')
    a.update(status='reviewed',review={'reviewer':actor,'note':note,'digest':digest(a['proposal']),'at':datetime.now(timezone.utc).isoformat()})
    service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'review','id':aid});return deepcopy(a)

def apply(service,pid,aid,*,expected_revision):
    project,token=read(service,pid);a=project['manual_formula_amendments'][aid];revision(expected_revision,a['revision'])
    if a['status']!='reviewed':raise ValueError('اصلاحیه ابتدا باید مستقل بازبینی شود')
    check_base(project,a);financial_block(project)
    if a['review']['digest']!=digest(a['proposal']):raise ValueError('داده اصلاحیه پس از بازبینی تغییر کرده است')
    reg=verified(project);candidate=deepcopy(reg);key=a['row_id'];candidate[key].update(data=deepcopy(a['proposal']),quantity=a['quantity']);values=evaluate_rows(graph(candidate));before=fingerprints(reg);after=fingerprints(candidate)
    for k,row in candidate.items():
        if k==key:continue
        if before[k]!=after[k]:
            if row['status']=='committed':raise ValueError('ردیف قطعی وابسته به اصلاحیه گروهی مستقل نیاز دارد')
            row.update(quantity=values[k],revision=row['revision']+1,status='draft');row.pop('review',None)
            project.setdefault('manual_formula_history',[]).append({'row_id':k,'revision':row['revision'],'previous':reg[k],'reason':a['reason'],'at':datetime.now(timezone.utc).isoformat()})
            project['manual_formula_register'][k]=row
    a.update(status='applied',applied_at=datetime.now(timezone.utc).isoformat());project.setdefault('manual_formula_applied',{})[key]=aid
    from core.takeoff.commit_guards import rebuild_project_boq
    _,project['boq']=rebuild_project_boq(project,project.get('takeoffs',[]));verified(project)
    service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'apply','id':aid});return deepcopy(a)

def effective_takeoffs(project,rows):
    if not project.get('manual_formula_applied'):return rows
    reg=verified(project);by_source={v['data']['source_id']:v for v in reg.values() if v.get('amendment_id')};result=deepcopy(rows)
    for row in result:
        if row.get('source_id') not in by_source:continue
        r=by_source.pop(row['source_id']);row['quantities'][0].update(amount=r['quantity'],formula=r['data']['expression']);row['params']={**deepcopy(r['data']),'intersections':deepcopy(r['data']['deductions'])}
    from core.takeoff.commit_guards import _intersection_ids
    used=set()
    for row in result:
        ids=_intersection_ids(row)
        if ids & used:raise ValueError('منبع هندسی کسر در نمای مؤثر تکراری است')
        used.update(ids)
    if by_source:raise ValueError('اصل متره مؤثر در پروژه یافت نشد')
    return result

def guard(previous,updated,command):
    for key,row in previous.get('manual_formula_register',{}).items():
        if row.get('status')=='committed' and updated.get('manual_formula_register',{}).get(key)!=row:raise ValueError('اصل ردیف قطعی دفتر فرمول قابل تغییر نیست')
    protected_sources={r['data']['source_id'] for r in previous.get('manual_formula_register',{}).values() if r.get('status')=='committed'}
    for sid in protected_sources:
        if [r for r in previous.get('takeoffs',[]) if r.get('source_id')==sid]!=[r for r in updated.get('takeoffs',[]) if r.get('source_id')==sid]:raise ValueError('اصل ریزمتره قطعی فرمول تغییرپذیر نیست')
    if protected_sources:
        from core.takeoff.commit_guards import rebuild_project_boq
        _,expected_boq=rebuild_project_boq(updated,updated.get('takeoffs',[]))
        def controlled(rows):
            result={}
            for row in rows:
                ids=frozenset(row.get('source_ids') or [row.get('source_id')])
                if not ids & protected_sources:continue
                if ids in result:raise ValueError('منبع BOQ قطعی تکراری است')
                result[ids]=(number(row['quantity'],'مقدار قطعی'),row['unit'],row['item_code'])
            return result
        if controlled(expected_boq)!=controlled(updated.get('boq',[])):raise ValueError('BOQ قطعی با فرمول مؤثر بازبینی‌شده مطابقت ندارد')
    changed=[f for f in FIELDS if previous.get(f,{})!=updated.get(f,{})]
    if not changed:return
    if not isinstance(command,dict) or command.get('action') not in {'create','review','apply'}:raise ValueError('اصلاحیه متره فقط از گردش رسمی قابل ثبت است')
    aid=command['id'];old=previous.get(FIELDS[0],{});new=updated.get(FIELDS[0],{})
    if aid not in new or any(v!=new.get(k) for k,v in old.items() if k!=aid) or set(new)-set(old)-{aid}:raise ValueError('تغییر خارج از اصلاحیه انتخابی ممنوع است')
    a=new[aid];action=command['action'];pointer=previous.get(FIELDS[1],{})
    if action=='create':
        if aid in old or a['status']!='draft':raise ValueError('ثبت اصلاحیه تکراری است')
    else:
        before=old.get(aid)
        if not before:raise ValueError('اصلاحیه پایه وجود ندارد')
        allowed={'status','review'} if action=='review' else {'status','applied_at'}
        if {k:v for k,v in before.items() if k not in allowed}!={k:v for k,v in a.items() if k not in allowed}:raise ValueError('اصل داده اصلاحیه ثابت است')
        if action=='review' and (before['status']!='draft' or a['status']!='reviewed' or a['review']['reviewer'].casefold()==a['created_by'].casefold()):raise ValueError('بازبینی مستقل معتبر نیست')
        if action=='apply':
            financial_block(previous)
            if before['status']!='reviewed' or a['status']!='applied':raise ValueError('اعمال اصلاحیه تکراری یا بدون بازبینی است')
            check_base(previous,before);pointer={**pointer,a['row_id']:aid}
    if updated.get(FIELDS[1],{})!=pointer:raise ValueError('نمای مؤثر اصلاحیه بدون مجوز تغییر کرده است')
    if previous.get('takeoffs',[])!=updated.get('takeoffs',[]):raise ValueError('اصل ریزمتره قطعی باید محفوظ بماند')
