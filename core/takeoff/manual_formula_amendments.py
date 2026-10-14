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
    if 'variable_units' not in d:raise ValueError('اصلاحیه تازه نیازمند واحد ساختاریافته و کنترل ابعادی است')
    if 'variable_units' in old['data'] and 'variable_units' not in d:raise ValueError('حذف قرارداد واحد در اصلاحیه مجاز نیست')
    for field in ('source_id','family','unit','member','floor','references','block','location'):
        if d.get(field)!=old['data'].get(field):raise ValueError('تغییر هویت، محل، واحد یا مراجع نیازمند گردش مستقل است')
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
    if not project.get('manual_formula_applied'):return beam_effective_takeoffs(project,rows)
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
    return beam_effective_takeoffs(project,result)

def guard(previous,updated,command):
    beam_guard(previous,updated,command)
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

# Beam corrections share this immutable correction service, financial gate,
# digest/revision boundaries and the same ProjectStore transaction.
BEAM_FIELDS=('beam_amendments','beam_amendment_applied')

def beam_current(project,key):
    original=project.get('beam_detail_register',{}).get(key)
    if original is None:raise KeyError(key)
    aid=project.get(BEAM_FIELDS[1],{}).get(key)
    if not aid:return deepcopy(original)
    a=project.get(BEAM_FIELDS[0],{})[aid]
    if a['status']!='applied' or a['beam_key']!=key or a['original_digest']!=digest(original) or a['review']['digest']!=digest({'proposal':a['proposal'],'rows':a['rows'],'delta':a['delta']}):raise ValueError('اصلاحیه تیر با اصل و بازبینی مطابقت ندارد')
    return {**deepcopy(original),'data':deepcopy(a['proposal']),'revision':a['base_revision']+1,'amendment_id':aid}

def beam_rows(data,version):
    from core.takeoff.beam_detail import preview_beam
    from core.takeoff.engine import TakeoffEngine
    r=preview_beam(data,TakeoffEngine())
    if not r['ready']:raise ValueError('تیر پیشنهادی ناقص است: '+'؛ '.join(r['blockers']))
    return [{'id':v['source_id'],'source_id':v['source_id'],'member_code':data['beam_id'],'system':data['floor_id'],'domain':v['domain'],'item':v['code'],'description':v['description'],'params':deepcopy(v['params']),'provenance':deepcopy(data['source']),'revision':version,'quantities':[{'code':v['code'],'title':v['description'],'unit':v['unit'],'amount':v['quantity'],'formula':v['formula'],'price_code':None,'unit_price':None}]} for v in r['rows']]

def beam_effective_takeoffs(project,rows):
    result=deepcopy(rows)
    for key,aid in project.get(BEAM_FIELDS[1],{}).items():
        record=beam_current(project,key);a=project[BEAM_FIELDS[0]][aid]
        computed=beam_rows(record['data'],record['revision'])
        if computed!=a['rows']:raise ValueError('مقادیر مؤثر تیر با دیتایل بازبینی‌شده مطابقت ندارند')
        ids=set(project['beam_detail_register'][key]['committed_source_ids'])
        if not ids<=set(v['source_id'] for v in result):raise ValueError('اصل تیر در ریزمتره یافت نشد')
        result=[v for v in result if v['source_id'] not in ids]+deepcopy(a['rows'])
    ids=[v['source_id'] for v in result]
    if len(ids)!=len(set(ids)):raise ValueError('منبع مؤثر متره تکراری است')
    from core.takeoff.commit_guards import _intersection_ids
    used=set()
    for row in result:
        ids=_intersection_ids(row)
        if used&ids:raise ValueError('کسر هندسی مؤثر تکراری است')
        used.update(ids)
    return result

def beam_base(project,a):
    current=beam_current(project,a['beam_key'])
    if current['revision']!=a['base_revision'] or digest(current)!=a['base_digest']:raise RuntimeError('مبنای اصلاحیه تیر تغییر کرده است')
    return current

def beam_create(service,pid,floor,beam,data,*,expected_revision,created_by,reason):
    from core.takeoff.beam_detail import _beam_key
    project,token=read(service,pid);key=_beam_key(floor,beam);old=beam_current(project,key);revision(expected_revision,old['revision'])
    if old['status']!='committed':raise ValueError('اصلاحیه فقط برای تیر قطعی است')
    d=deepcopy(data)
    if d.get('measurement_policy')!='beam_specialist_v1':raise ValueError('اصلاحیه تیر نیازمند قرارداد تخصصی معتبر است')
    for field in ('floor_id','beam_id','source'):
        if d.get(field)!=old['data'].get(field):raise ValueError('تغییر هویت یا منبع اصلی تیر نیازمند گردش مستقل است')
    rows=beam_rows(d,old['revision']+1)
    current_rows=beam_effective_takeoffs(project,project.get('takeoffs',[]))
    current_ids=set(project['beam_detail_register'][key]['committed_source_ids'])
    if old.get('amendment_id'):current_ids|={r['source_id'] for r in project[BEAM_FIELDS[0]][old['amendment_id']]['rows']}
    temporary=deepcopy(project);temporary['takeoffs']=[r for r in current_rows if r['source_id'] not in current_ids]
    from core.takeoff.commit_guards import validate_commit_rows
    validate_commit_rows(temporary,rows,source_id=d['source']['source_id'],expected_current_registry=('beam_detail_register',key))
    before={r['source_id']:number(r['quantities'][0]['amount'],'مقدار مبنا') for r in current_rows if r['source_id'] in current_ids};after={r['source_id']:number(r['quantities'][0]['amount'],'مقدار پیشنهاد') for r in rows}
    from core.commercial.exact_values import wire,exact
    @exact
    def delta():return {k:wire(after.get(k,number(0,'صفر'))-before.get(k,number(0,'صفر'))) for k in sorted(set(before)|set(after))}
    a={'id':'BA-'+uuid4().hex,'beam_key':key,'revision':1,'base_revision':old['revision'],'base_digest':digest(old),'original_digest':digest(project['beam_detail_register'][key]),'previous':deepcopy(old),'proposal':d,'rows':rows,'delta':delta(),'created_by':text(created_by,'سازنده'),'reason':text(reason,'علت اصلاح'),'status':'draft','created_at':datetime.now(timezone.utc).isoformat()}
    project.setdefault(BEAM_FIELDS[0],{})[a['id']]=a;service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'beam_create','id':a['id']});return deepcopy(a)

def beam_review(service,pid,aid,*,expected_revision,reviewer,note):
    project,token=read(service,pid);a=project[BEAM_FIELDS[0]][aid];revision(expected_revision,a['revision']);beam_base(project,a);actor=text(reviewer,'بازبین مستقل')
    if a['status']!='draft' or actor.casefold()==a['created_by'].casefold():raise ValueError('بازبینی مستقل اصلاحیه تیر معتبر نیست')
    if beam_rows(a['proposal'],a['base_revision']+1)!=a['rows']:raise ValueError('مقدار پیشنهاد تغییر کرده است')
    a.update(status='reviewed',review={'reviewer':actor,'note':text(note,'یادداشت کنترل'),'digest':digest({'proposal':a['proposal'],'rows':a['rows'],'delta':a['delta']})});service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'beam_review','id':aid});return deepcopy(a)

def beam_apply(service,pid,aid,*,expected_revision):
    project,token=read(service,pid);a=project[BEAM_FIELDS[0]][aid];revision(expected_revision,a['revision'])
    if a['status']!='reviewed' or a['review']['digest']!=digest({'proposal':a['proposal'],'rows':a['rows'],'delta':a['delta']}):raise ValueError('اعمال تکراری یا بدون بازبینی معتبر ممنوع است')
    beam_base(project,a);financial_block(project)
    a.update(status='applied',applied_at=datetime.now(timezone.utc).isoformat());project.setdefault(BEAM_FIELDS[1],{})[a['beam_key']]=aid
    from core.takeoff.commit_guards import rebuild_project_boq
    _,project['boq']=rebuild_project_boq(project,project.get('takeoffs',[]));service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'beam_apply','id':aid});return deepcopy(a)

def beam_checked_delta(project,a):
    from core.commercial.exact_values import wire,exact
    base=beam_current(project,a['beam_key']);ids=set(project['beam_detail_register'][a['beam_key']]['committed_source_ids'])
    if base.get('amendment_id'):ids|={r['source_id'] for r in project[BEAM_FIELDS[0]][base['amendment_id']]['rows']}
    before={r['source_id']:number(r['quantities'][0]['amount'],'مبنا') for r in beam_effective_takeoffs(project,project.get('takeoffs',[])) if r['source_id'] in ids};after={r['source_id']:number(r['quantities'][0]['amount'],'پیشنهاد') for r in a['rows']}
    @exact
    def calc():return {k:wire(after.get(k,number(0,'صفر'))-before.get(k,number(0,'صفر'))) for k in sorted(set(before)|set(after))}
    return calc()

def beam_guard(previous,updated,command):
    protected=set()
    for key,r in previous.get('beam_detail_register',{}).items():
        if r.get('status')!='committed':continue
        if updated.get('beam_detail_register',{}).get(key)!=r:raise ValueError('اصل تیر قطعی قابل بازنویسی نیست')
        protected.update(r.get('committed_source_ids',[]))
    for sid in protected:
        if [r for r in previous.get('takeoffs',[]) if r.get('source_id')==sid]!=[r for r in updated.get('takeoffs',[]) if r.get('source_id')==sid]:raise ValueError('اصل ردیف تیر قطعی تغییر کرده است')
    changed=any(previous.get(f,{})!=updated.get(f,{}) for f in BEAM_FIELDS)
    if changed:
        if not isinstance(command,dict) or command.get('action') not in ('beam_create','beam_review','beam_apply'):raise ValueError('اصلاحیه تیر فقط از خدمات رسمی ثبت می‌شود')
        aid=command['id'];old=previous.get(BEAM_FIELDS[0],{});new=updated.get(BEAM_FIELDS[0],{});a=new.get(aid)
        if not a or set(old)-set(new) or any(v!=new.get(k) for k,v in old.items() if k!=aid) or set(new)-set(old)-{aid}:raise ValueError('تغییر غیرمجاز دفتر اصلاحیه تیر')
        pointer=previous.get(BEAM_FIELDS[1],{});action=command['action']
        if action=='beam_create':
            if aid in old or a['status']!='draft':raise ValueError('ثبت اصلاحیه تیر تکراری است')
            base=beam_base(previous,a)
            if a['previous']!=base or a['original_digest']!=digest(previous['beam_detail_register'][a['beam_key']]) or any(a['proposal'].get(k)!=base['data'].get(k) for k in ('floor_id','beam_id','source')) or a['delta']!=beam_checked_delta(previous,a):raise ValueError('مبنا، هویت یا دلتا معتبر نیست')
            if beam_rows(a['proposal'],a['base_revision']+1)!=a['rows']:raise ValueError('مقادیر پیشنهادی نامعتبرند')
        else:
            before=old.get(aid);allowed={'status','review'} if action=='beam_review' else {'status','applied_at'}
            if not before or {k:v for k,v in before.items() if k not in allowed}!={k:v for k,v in a.items() if k not in allowed}:raise ValueError('اصل اصلاحیه تیر تغییر کرده است')
            beam_base(previous,before)
            if action=='beam_review':
                if before['status']!='draft' or a['status']!='reviewed' or a['review']['reviewer'].casefold()==a['created_by'].casefold() or a['review']['digest']!=digest({'proposal':a['proposal'],'rows':a['rows'],'delta':a['delta']}):raise ValueError('بازبینی تیر معتبر نیست')
            else:
                financial_block(previous)
                if before['status']!='reviewed' or a['status']!='applied':raise ValueError('اعمال تکراری یا بدون بازبینی')
                pointer={**pointer,a['beam_key']:aid}
        if updated.get(BEAM_FIELDS[1],{})!=pointer or previous.get('takeoffs',[])!=updated.get('takeoffs',[]):raise ValueError('اصل یا اشاره‌گر اصلاحیه تیر غیرمجاز تغییر کرد')
    if protected or updated.get(BEAM_FIELDS[1]):
        from core.takeoff.commit_guards import rebuild_project_boq
        _,boq=rebuild_project_boq(updated,updated.get('takeoffs',[]))
        current=protected|{r['source_id'] for aid in updated.get(BEAM_FIELDS[1],{}).values() for r in updated[BEAM_FIELDS[0]][aid]['rows']}
        def view(rows):return [(r.get('source_ids') or [r.get('source_id')],r['unit'],r['item_code'],number(r['quantity'],'مقدار')) for r in rows if current&set(r.get('source_ids') or [r.get('source_id')])]
        if view(boq)!=view(updated.get('boq',[])):raise ValueError('BOQ مؤثر تیر با دفتر اصلاحیه مطابقت ندارد')
