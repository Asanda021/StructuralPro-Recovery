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
        if action=='review' and (before['status']!='draft' or a['status']!='reviewed' or text(a['review']['reviewer'],'بازبین').casefold()==text(a['created_by'],'سازنده').casefold()):raise ValueError('بازبینی مستقل معتبر نیست')
        if action=='apply':
            financial_block(previous)
            if before['status']!='reviewed' or a['status']!='applied':raise ValueError('اعمال اصلاحیه تکراری یا بدون بازبینی است')
            check_base(previous,before);pointer={**pointer,a['row_id']:aid}
    if updated.get(FIELDS[1],{})!=pointer:raise ValueError('نمای مؤثر اصلاحیه بدون مجوز تغییر کرده است')
    if previous.get('takeoffs',[])!=updated.get('takeoffs',[]):raise ValueError('اصل ریزمتره قطعی باید محفوظ بماند')

# Beam corrections share this immutable correction service, financial gate,
# digest/revision boundaries and the same ProjectStore transaction.
FOUNDATION_KINDS = frozenset(('tie_beam','isolated_footing','strip_footing','mat_footing','pile_cap'))
STRUCTURAL_POLICIES = ('column_specialist_v1','foundation_tie_specialist_v1')

BEAM_FIELDS=('beam_amendments','beam_amendment_applied','beam_legacy_links')


def beam_review_payload(a):
    if a.get('kind')=='legacy_link':return {'mapping':a['mapping']}
    value={'proposal':a['proposal'],'rows':a['rows'],'delta':a['delta']}
    if 'migration' in a:value['migration']=a['migration']
    if 'evidence' in a:value['evidence']=a['evidence']
    return value

def beam_migration_evidence(migration):
    from pathlib import Path
    document=Path(text(migration.get('evidence_path'),'مسیر مدرک مهاجرت'))
    expected=text(migration.get('evidence_sha256'),'هش مدرک مهاجرت')
    text(migration.get('evidence_reference'),'مرجع مدرک مهاجرت')
    if not document.is_file() or sha256(document.read_bytes()).hexdigest()!=expected:raise ValueError('مدرک واقعی مهاجرت در دسترس نیست یا تغییر کرده است')

def beam_migration_identity(old,new):
    if old.get('measurement_policy')=='beam_specialist_v1':raise ValueError('این تیر قبلاً دارای قرارداد جدید است؛ مهاجرت تکراری ممنوع')
    if any(new.get(k)!=old.get(k) for k in ('floor_id','beam_id')):raise ValueError('هویت تاریخی تیر قابل تغییر نیست')
    source=old.get('source');target=new.get('source')
    if not isinstance(source,dict) or not isinstance(target,dict) or not source.get('source_id'):raise ValueError('منشأ تاریخی معتبر نیازمند تکمیل مستقل است')
    for key,value in source.items():
        if key in ('plan_ref','detail_ref') and value in (None,''):continue
        if target.get(key)!=value:raise ValueError('منشأ تاریخی معتبر تغییر کرده است')
    if set(target)-set(source)-{'plan_ref','detail_ref'}:raise ValueError('افزودن هویت منبع خارج از قرارداد مهاجرت ممنوع')
    def identifiers(value):
        if isinstance(value,dict):return ({str(value['id'])} if value.get('id') is not None else set())|set().union(*(identifiers(v) for v in value.values()),set())
        if isinstance(value,list):return set().union(*(identifiers(v) for v in value),set())
        return set()
    if not identifiers(old)<=identifiers(new):raise ValueError('شناسه تاریخی جزء حذف یا تغییر کرده است')
    for group in new.get('bars',{}).values():
        if group.get('status')!='confirmed':continue
        for series in group.get('segments',[group]):text(series.get('shape_ref'),'شکل مستند هر سری برای مهاجرت')


def beam_original(project,key):
    original=project.get('beam_detail_register',{}).get(key)
    if original is None:
        original=project.get('reviewed_structural_members',{}).get(key)
        if original and original.get('data',{}).get('measurement_policy') not in STRUCTURAL_POLICIES:raise ValueError('این گردش فقط ستون است')
    if original is None:
        original=project.get('reviewed_aec_systems',{}).get(key)
        if original and original.get('data',{}).get('measurement_policy') not in ('roof_specialist_v1','steel_specialist_v1','architecture_specialist_v1','shear_wall_specialist_v1','stair_specialist_reviewed_v1'):raise ValueError('این گردش نیازمند قرارداد تخصصی سقف است')
    if original is None:raise KeyError(key)
    return original

def beam_current(project,key):
    original=beam_original(project,key)
    aid=project.get(BEAM_FIELDS[1],{}).get(key)
    if not aid:return deepcopy(original)
    a=project.get(BEAM_FIELDS[0],{})[aid]
    if a['status']!='applied' or a['beam_key']!=key or a['original_digest']!=digest(original) or a['review']['digest']!=digest(beam_review_payload(a)):raise ValueError('اصلاحیه تیر با اصل و بازبینی مطابقت ندارد')
    return {**deepcopy(original),'data':deepcopy(a['proposal']),'revision':a['base_revision']+1,'amendment_id':aid}

def beam_rows(data,version,*,_historical_tie=False):
    if data.get('measurement_policy') in ('roof_specialist_v1','steel_specialist_v1','architecture_specialist_v1','shear_wall_specialist_v1','stair_specialist_reviewed_v1'):
        from core.takeoff.reviewed_aec import specialist_module
        return specialist_module(data).takeoffs(data,version)
    from core.takeoff.beam_detail import preview_beam
    from core.takeoff.engine import TakeoffEngine
    if data.get('measurement_policy') in STRUCTURAL_POLICIES:
        from core.takeoff.reviewed_structural import preview_member
        r=preview_member(data,TakeoffEngine(),_historical_tie=_historical_tie)
    else:r=preview_beam(data,TakeoffEngine())
    if not r['ready']:raise ValueError('تیر پیشنهادی ناقص است: '+'؛ '.join(r['blockers']))
    return [{'id':v['source_id'],'source_id':v['source_id'],'member_code':data.get('beam_id',data.get('member_id')),'system':data['floor_id'],'domain':v['domain'],'item':v['code'],'description':v['description'],'params':deepcopy(v['params']),'provenance':deepcopy(data['source']),'revision':version,'quantities':[{'code':v['code'],'title':v['description'],'unit':v['unit'],'amount':v['quantity'],'formula':v['formula'],'price_code':None,'unit_price':None}]} for v in r['rows']]

def beam_effective_takeoffs(project,rows):
    result=deepcopy(rows)
    for key,aid in project.get(BEAM_FIELDS[1],{}).items():
        record=beam_current(project,key);a=project[BEAM_FIELDS[0]][aid]
        computed=beam_rows(record['data'],record['revision'],_historical_tie=a.get('kind')=='foundation_amendment' and a['status']=='applied' and 'starters' not in a['proposal'].get('rebars',{}))
        if computed!=a['rows']:raise ValueError('مقادیر مؤثر تیر با دیتایل بازبینی‌شده مطابقت ندارند')
        ids=set(beam_original(project,key).get('committed_source_ids',[]))
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

def beam_create(service,pid,floor,beam,data,*,expected_revision,created_by,reason,migration=None,column=False,foundation_kind=None,evidence=None,roof_kind=None):
    from core.takeoff.beam_detail import _beam_key
    project,token=read(service,pid);key=_beam_key(floor,beam)
    if foundation_kind is not None and foundation_kind not in FOUNDATION_KINDS:raise ValueError('نوع پی یا شناژ معتبر نیست')
    if roof_kind is not None:
        from core.takeoff.roof_detail import KINDS
        from core.takeoff.steel_detail import KINDS as STEEL_KINDS
        from core.takeoff.architecture_detail import KINDS as ARCH_KINDS
        if roof_kind not in KINDS+STEEL_KINDS+ARCH_KINDS+('shear_wall','stair'):raise ValueError('نوع سقف معتبر نیست')
    if roof_kind and (migration is not None or column or foundation_kind):raise ValueError('مهاجرت یا تغییر خانواده در اصلاحیه سقف مجاز نیست')
    structural=column or foundation_kind is not None
    if roof_kind:
        from core.takeoff.reviewed_aec import _id
        key=_id(roof_kind,floor,beam)
    elif structural:
        from core.takeoff.reviewed_structural import _key
        key=_key(foundation_kind or 'column',floor,beam)
    old=beam_current(project,key);revision(expected_revision,old['revision'])
    if old['status']!='committed' and not (migration is not None and old['status']=='draft'):raise ValueError('اصلاحیه فقط برای تیر قطعی یا مهاجرت پیش‌نویس است')
    d=deepcopy(data)
    if (roof_kind and d.get('kind')!=roof_kind) or (structural and d.get('kind')!=(foundation_kind or 'column')) or (not structural and not roof_kind and d.get('kind') not in (None,'beam')):raise ValueError('تغییر نوع عضو در اصلاحیه ممنوع است')
    if d.get('measurement_policy')!=(old['data'].get('measurement_policy') if roof_kind else 'foundation_tie_specialist_v1' if foundation_kind else 'column_specialist_v1' if column else 'beam_specialist_v1'):raise ValueError('اصلاحیه تیر نیازمند قرارداد تخصصی معتبر است')
    if migration is not None:
        beam_migration_identity(old['data'],d);beam_migration_evidence(migration)
    else:
        for field in (('floor_id','system_id','building_id','axis','source') if roof_kind else ('floor_id','member_id','building_id','axis','source') if structural else ('floor_id','beam_id','source')):
            if d.get(field)!=old['data'].get(field):raise ValueError('تغییر هویت یا منبع اصلی تیر نیازمند گردش مستقل است')
    if d.get('measurement_policy')=='stair_specialist_reviewed_v1':
        from core.takeoff.stair_detail import validate_amendment
        validate_amendment(old['data'],d)
    if d.get('measurement_policy')=='shear_wall_specialist_v1':
        from core.takeoff.shear_wall_detail import validate_amendment
        validate_amendment(old['data'],d)
    rows=beam_rows(d,old['revision']+1)
    if d.get('measurement_policy')=='architecture_specialist_v1':
        from core.takeoff.architecture_detail import validate_amendment
        validate_amendment(old['data'],d,beam_rows(old['data'],old['revision']),rows)
    current_rows=beam_effective_takeoffs(project,project.get('takeoffs',[]))
    current_ids=set(beam_original(project,key).get('committed_source_ids',[]))
    if old.get('amendment_id'):current_ids|={r['source_id'] for r in project[BEAM_FIELDS[0]][old['amendment_id']]['rows']}
    temporary=deepcopy(project);temporary['takeoffs']=[r for r in current_rows if r['source_id'] not in current_ids]
    from core.takeoff.commit_guards import validate_commit_rows
    validate_commit_rows(temporary,rows,source_id=d['source']['source_id'],expected_current_registry=('reviewed_aec_systems' if roof_kind else 'reviewed_structural_members' if structural else 'beam_detail_register',key))
    before={r['source_id']:number(r['quantities'][0]['amount'],'مقدار مبنا') for r in current_rows if r['source_id'] in current_ids};after={r['source_id']:number(r['quantities'][0]['amount'],'مقدار پیشنهاد') for r in rows}
    from core.commercial.exact_values import wire,exact
    @exact
    def delta():return {k:wire(after.get(k,number(0,'صفر'))-before.get(k,number(0,'صفر'))) for k in sorted(set(before)|set(after))}
    a={'id':'BA-'+uuid4().hex,'beam_key':key,'revision':1,'base_revision':old['revision'],'base_digest':digest(old),'original_digest':digest(beam_original(project,key)),'previous':deepcopy(old),'proposal':d,'rows':rows,'delta':delta(),'created_by':text(created_by,'سازنده'),'reason':text(reason,'علت اصلاح'),'status':'draft','created_at':datetime.now(timezone.utc).isoformat()}
    if column:a['kind']='column_amendment'
    if foundation_kind or roof_kind:
        if not isinstance(evidence,dict):raise ValueError('مدرک جدید اصلاحیه لازم است')
        beam_migration_evidence(evidence)
        if any(v.get('beam_key')==key and v.get('status') in ('draft','reviewed') for v in project.get(BEAM_FIELDS[0],{}).values()):raise ValueError('اصلاحیه باز تکراری ممنوع است')
        a.update(kind='roof_amendment' if roof_kind else 'foundation_amendment',evidence=deepcopy(evidence))
    if migration is not None:a['migration']={**deepcopy(migration),'version':1,'from_policy':old['data'].get('measurement_policy'),'to_policy':'beam_specialist_v1'}
    project.setdefault(BEAM_FIELDS[0],{})[a['id']]=a;service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'beam_create','id':a['id']});return deepcopy(a)

def beam_review(service,pid,aid,*,expected_revision,reviewer,note):
    if read(service,pid)[0].get('beam_amendments',{}).get(aid,{}).get('kind')=='legacy_link':return mapping_transition(service,pid,aid,'review',expected_revision=expected_revision,reviewer=reviewer,note=note)
    project,token=read(service,pid);a=project[BEAM_FIELDS[0]][aid];revision(expected_revision,a['revision']);beam_base(project,a);actor=text(reviewer,'بازبین مستقل')
    if a.get('migration'):beam_migration_evidence(a['migration'])
    if a.get('kind') in ('foundation_amendment','roof_amendment'):beam_migration_evidence(a['evidence'])
    if a['status']!='draft' or actor.casefold()==a['created_by'].casefold():raise ValueError('بازبینی مستقل اصلاحیه تیر معتبر نیست')
    if beam_rows(a['proposal'],a['base_revision']+1)!=a['rows']:raise ValueError('مقدار پیشنهاد تغییر کرده است')
    a.update(status='reviewed',review={'reviewer':actor,'note':text(note,'یادداشت کنترل'),'digest':digest(beam_review_payload(a))});service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'beam_review','id':aid});return deepcopy(a)

def beam_apply(service,pid,aid,*,expected_revision):
    if read(service,pid)[0].get('beam_amendments',{}).get(aid,{}).get('kind')=='legacy_link':return mapping_transition(service,pid,aid,'apply',expected_revision=expected_revision)
    project,token=read(service,pid);a=project[BEAM_FIELDS[0]][aid];revision(expected_revision,a['revision'])
    if a['status']!='reviewed' or a['review']['digest']!=digest(beam_review_payload(a)):raise ValueError('اعمال تکراری یا بدون بازبینی معتبر ممنوع است')
    beam_base(project,a);financial_block(project)
    if a.get('kind') in ('foundation_amendment','roof_amendment') and beam_rows(a['proposal'],a['base_revision']+1)!=a['rows']:raise ValueError('دیتایل اصلاحیه با قرارداد جاری کامل نیست')
    if a.get('migration'):beam_migration_evidence(a['migration'])
    if a.get('kind') in ('foundation_amendment','roof_amendment'):beam_migration_evidence(a['evidence'])
    a.update(status='applied',applied_at=datetime.now(timezone.utc).isoformat())
    if a.get('migration') and a['previous']['status']=='draft':
        project['beam_detail_register'][a['beam_key']]={**deepcopy(a['previous']),'data':deepcopy(a['proposal']),'revision':a['base_revision']+1,'migration_id':aid,'updated_at':a['applied_at']}
        project.setdefault('beam_detail_history',[]).append({'beam_key':a['beam_key'],'revision':a['base_revision']+1,'previous':deepcopy(a['previous']),'reason':a['reason'],'migration_id':aid,'at':a['applied_at']})
    else:project.setdefault(BEAM_FIELDS[1],{})[a['beam_key']]=aid
    from core.takeoff.commit_guards import rebuild_project_boq
    _,project['boq']=rebuild_project_boq(project,project.get('takeoffs',[]));service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'beam_apply','id':aid});return deepcopy(a)

def beam_checked_delta(project,a):
    from core.commercial.exact_values import wire,exact
    base=beam_current(project,a['beam_key']);ids=set(beam_original(project,a['beam_key']).get('committed_source_ids',[]))
    if base.get('amendment_id'):ids|={r['source_id'] for r in project[BEAM_FIELDS[0]][base['amendment_id']]['rows']}
    before={r['source_id']:number(r['quantities'][0]['amount'],'مبنا') for r in beam_effective_takeoffs(project,project.get('takeoffs',[])) if r['source_id'] in ids};after={r['source_id']:number(r['quantities'][0]['amount'],'پیشنهاد') for r in a['rows']}
    @exact
    def calc():return {k:wire(after.get(k,number(0,'صفر'))-before.get(k,number(0,'صفر'))) for k in sorted(set(before)|set(after))}
    return calc()

def beam_guard(previous,updated,command):
    from core.takeoff.roof_detail import physical_identity_guard
    physical_identity_guard(updated)
    from core.takeoff.steel_detail import physical_identity_guard as steel_guard
    steel_guard(updated)
    from core.takeoff.architecture_detail import guard as architecture_guard
    architecture_guard(previous,updated)
    from core.takeoff.shear_wall_detail import guard as wall_guard
    wall_guard(previous,updated)
    from core.takeoff.stair_detail import guard as stair_guard
    stair_guard(previous,updated)
    from core.takeoff.bored_pile_detail import guard as pile_guard
    pile_guard(previous,updated)
    for key,record in previous.get('reviewed_aec_systems',{}).items():
        new=updated.get('reviewed_aec_systems',{}).get(key)
        if new and record['data'].get('kind') in ('steel_frame','steel_deck') and record['data'].get('measurement_policy')!=new['data'].get('measurement_policy') and 'steel_specialist_v1' in (record['data'].get('measurement_policy'),new['data'].get('measurement_policy')):raise ValueError('تغییر قرارداد تاریخی فولاد نیازمند مهاجرت صریح است')
    for snapshot in previous.get('aec_system_history',[]):
        if snapshot not in updated.get('aec_system_history',[]):raise ValueError('حذف یا تغییر تاریخچه سقف ممنوع است')
    for snapshot in previous.get('structural_member_history',[]):
        if snapshot.get('previous',{}).get('data',{}).get('measurement_policy') in STRUCTURAL_POLICIES and snapshot not in updated.get('structural_member_history',[]):raise ValueError('حذف یا تغییر تاریخچه ستون ممنوع است')
    mapping_guard(previous,updated,command)
    if isinstance(command,dict) and command.get('action','').startswith('mapping_'):return
    for snapshot in previous.get('beam_detail_history',[]):
        if snapshot.get('migration_id') and snapshot not in updated.get('beam_detail_history',[]):raise ValueError('حذف یا تغییر اصل تاریخچه مهاجرت ممنوع است')
    protected=set()
    for key,r in previous.get('beam_detail_register',{}).items():
        if r.get('status')!='committed':continue
        if updated.get('beam_detail_register',{}).get(key)!=r:raise ValueError('اصل تیر قطعی قابل بازنویسی نیست')
        protected.update(r.get('committed_source_ids',[]))
    for sid in protected:
        if [r for r in previous.get('takeoffs',[]) if r.get('source_id')==sid]!=[r for r in updated.get('takeoffs',[]) if r.get('source_id')==sid]:raise ValueError('اصل ردیف تیر قطعی تغییر کرده است')
    for key,r in previous.get('reviewed_structural_members',{}).items():
        if r.get('status')=='committed' and r.get('data',{}).get('measurement_policy') in STRUCTURAL_POLICIES:
            if updated.get('reviewed_structural_members',{}).get(key)!=r:raise ValueError('اصل ستون قطعی قابل تغییر نیست')
            protected.update(r.get('committed_source_ids',[]))
            for sid in r.get('committed_source_ids',[]):
                if [v for v in previous.get('takeoffs',[]) if v.get('source_id')==sid]!=[v for v in updated.get('takeoffs',[]) if v.get('source_id')==sid]:raise ValueError('اصل برداشت ستون قطعی قابل تغییر نیست')
    for key,r in previous.get('reviewed_aec_systems',{}).items():
        if r.get('status')=='committed' and r.get('data',{}).get('measurement_policy') in ('roof_specialist_v1','steel_specialist_v1','architecture_specialist_v1','shear_wall_specialist_v1','stair_specialist_reviewed_v1'):
            if updated.get('reviewed_aec_systems',{}).get(key)!=r:raise ValueError('اصل سقف قطعی قابل تغییر نیست')
            protected.update(r.get('committed_source_ids',[]))
            for sid in r.get('committed_source_ids',[]):
                if [v for v in previous.get('takeoffs',[]) if v.get('source_id')==sid]!=[v for v in updated.get('takeoffs',[]) if v.get('source_id')==sid]:raise ValueError('اصل ریزمتره سقف قطعی تغییر کرده است')
    changed=any(previous.get(f,{})!=updated.get(f,{}) for f in BEAM_FIELDS)
    if changed:
        if not isinstance(command,dict) or command.get('action') not in ('beam_create','beam_review','beam_apply'):raise ValueError('اصلاحیه تیر فقط از خدمات رسمی ثبت می‌شود')
        aid=command['id'];old=previous.get(BEAM_FIELDS[0],{});new=updated.get(BEAM_FIELDS[0],{});a=new.get(aid)
        if not a or set(old)-set(new) or any(v!=new.get(k) for k,v in old.items() if k!=aid) or set(new)-set(old)-{aid}:raise ValueError('تغییر غیرمجاز دفتر اصلاحیه تیر')
        pointer=previous.get(BEAM_FIELDS[1],{});action=command['action']
        if a.get('migration'):beam_migration_evidence(a['migration'])
        if a.get('kind') in ('foundation_amendment','roof_amendment'):beam_migration_evidence(a['evidence'])
        if action=='beam_create':
            if aid in old or a['status']!='draft':raise ValueError('ثبت اصلاحیه تیر تکراری است')
            base=beam_base(previous,a)
            roof=base['data'].get('measurement_policy') in ('roof_specialist_v1','steel_specialist_v1','architecture_specialist_v1','shear_wall_specialist_v1','stair_specialist_reviewed_v1')
            if roof and any(v.get('beam_key')==a['beam_key'] and v.get('status') in ('draft','reviewed') for v in old.values()):raise ValueError('اصلاحیه باز تکراری سقف ممنوع است')
            structural=base['data'].get('measurement_policy') in STRUCTURAL_POLICIES
            expected_kind='roof_amendment' if roof else 'foundation_amendment' if base['data'].get('measurement_policy')=='foundation_tie_specialist_v1' else 'column_amendment' if structural else None
            if a.get('kind')!=expected_kind or ((structural or roof) and (a['proposal'].get('kind')!=base['data'].get('kind') or a['proposal'].get('measurement_policy')!=base['data'].get('measurement_policy'))) or (not structural and not roof and a['proposal'].get('kind') not in (None,'beam')):raise ValueError('نوع عضو یا گردش اصلاحیه نامعتبر است')
            if a['previous']!=base or a['original_digest']!=digest(beam_original(previous,a['beam_key'])) or (not a.get('migration') and any(a['proposal'].get(k)!=base['data'].get(k) for k in (('floor_id','system_id','building_id','axis','source') if roof else ('floor_id','member_id','building_id','axis','source') if structural else ('floor_id','beam_id','source')))) or a['delta']!=beam_checked_delta(previous,a):raise ValueError('مبنا، هویت یا دلتا معتبر نیست')
            if a.get('migration'):
                beam_migration_identity(base['data'],a['proposal']);beam_migration_evidence(a['migration'])
                if a['migration'].get('from_policy')!=base['data'].get('measurement_policy') or a['migration'].get('to_policy')!='beam_specialist_v1' or a['migration'].get('version')!=1:raise ValueError('قرارداد مهاجرت معتبر نیست')
            if beam_rows(a['proposal'],a['base_revision']+1)!=a['rows']:raise ValueError('مقادیر پیشنهادی نامعتبرند')
            if base['data'].get('measurement_policy')=='stair_specialist_reviewed_v1':
                from core.takeoff.stair_detail import validate_amendment
                validate_amendment(base['data'],a['proposal'])
            if base['data'].get('measurement_policy')=='shear_wall_specialist_v1':
                from core.takeoff.shear_wall_detail import validate_amendment
                validate_amendment(base['data'],a['proposal'])
            if base['data'].get('measurement_policy')=='architecture_specialist_v1':
                from core.takeoff.architecture_detail import validate_amendment
                validate_amendment(base['data'],a['proposal'],beam_rows(base['data'],base['revision']),a['rows'])
        else:
            before=old.get(aid);allowed={'status','review'} if action=='beam_review' else {'status','applied_at'}
            if not before or {k:v for k,v in before.items() if k not in allowed}!={k:v for k,v in a.items() if k not in allowed}:raise ValueError('اصل اصلاحیه تیر تغییر کرده است')
            beam_base(previous,before)
            if a['proposal'].get('measurement_policy')=='stair_specialist_reviewed_v1':
                from core.takeoff.stair_detail import check_reviewer
                check_reviewer(a['proposal'],a['review']['reviewer'])
            if a['proposal'].get('measurement_policy')=='shear_wall_specialist_v1':
                from core.takeoff.shear_wall_detail import check_reviewer
                check_reviewer(a['proposal'],a['review']['reviewer'])
            if action=='beam_review':
                text(a['review']['reviewer'],'بازبین مستقل');text(a['review']['note'],'یادداشت بازبینی')
                if before['status']!='draft' or a['status']!='reviewed' or text(a['review']['reviewer'],'بازبین').casefold()==text(a['created_by'],'سازنده').casefold() or a['review']['digest']!=digest(beam_review_payload(a)):raise ValueError('بازبینی تیر معتبر نیست')
            else:
                financial_block(previous)
                if a.get('kind') in ('foundation_amendment','roof_amendment') and beam_rows(a['proposal'],a['base_revision']+1)!=a['rows']:raise ValueError('دیتایل اصلاحیه با قرارداد جاری کامل نیست')
                if before['status']!='reviewed' or a['status']!='applied':raise ValueError('اعمال تکراری یا بدون بازبینی')
                if not(a.get('migration') and a['previous']['status']=='draft'):pointer={**pointer,a['beam_key']:aid}
        expected_register=deepcopy(previous.get('beam_detail_register',{}))
        if action=='beam_apply' and a.get('migration') and a['previous']['status']=='draft':
            beam_migration_evidence(a['migration'])
            expected_register[a['beam_key']]={**deepcopy(a['previous']),'data':deepcopy(a['proposal']),'revision':a['base_revision']+1,'migration_id':aid,'updated_at':a['applied_at']}
        if updated.get('beam_detail_register',{})!=expected_register:raise ValueError('نسخه تاریخی خارج از مهاجرت مجاز تغییر کرد')
        if updated.get(BEAM_FIELDS[1],{})!=pointer or previous.get('takeoffs',[])!=updated.get('takeoffs',[]):raise ValueError('اصل یا اشاره‌گر اصلاحیه تیر غیرمجاز تغییر کرد')
    if protected or updated.get(BEAM_FIELDS[1]):
        from core.takeoff.commit_guards import rebuild_project_boq
        _,boq=rebuild_project_boq(updated,updated.get('takeoffs',[]))
        current=protected|{r['source_id'] for aid in updated.get(BEAM_FIELDS[1],{}).values() for r in updated[BEAM_FIELDS[0]][aid]['rows']}
        def view(rows):return [(r.get('source_ids') or [r.get('source_id')],r['unit'],r['item_code'],number(r['quantity'],'مقدار')) for r in rows if current&set(r.get('source_ids') or [r.get('source_id')])]
        if view(boq)!=view(updated.get('boq',[])):raise ValueError('BOQ مؤثر تیر با دفتر اصلاحیه مطابقت ندارد')


def inspect_beam_history(service,pid):
    from core.takeoff.beam_detail import preview_beam
    project,_=read(service,pid);result=[];linked=set()
    entries=project.get('beam_detail_register',{})
    if not isinstance(entries,dict):return [{'status':'INCOMPATIBLE','blockers':['ساختار دفتر تیر نامعتبر است']}]
    for key,original in entries.items():
        try:
            record=beam_current(project,key);data=record['data'];source=data.get('source',{});linked.update(original.get('committed_source_ids',[]))
            probe=deepcopy(data);probe['measurement_policy']='beam_specialist_v1'
            report=preview_beam(probe,service.takeoff)
            valid_version=type(record.get('revision')) is int and record['revision']>=1
            valid_source=isinstance(source,dict) and bool(source.get('source_id'))
            status='CURRENT_CONTRACT' if data.get('measurement_policy')=='beam_specialist_v1' and report['ready'] else 'LEGACY_REVIEW_REQUIRED' if report['ready'] else 'NEEDS_ENGINEER_INPUT'
            if not valid_version or not valid_source:status='INCOMPATIBLE'
            result.append({'beam_key':key,'status':status,'revision':record.get('revision'),'record_status':record.get('status'),'measurement_policy':data.get('measurement_policy'),'source_id':source.get('source_id'),'variable_units':deepcopy(data.get('geometry',{}).get('variable_units')),'blockers':report['blockers'],'migration_id':record.get('migration_id') or record.get('amendment_id')})
        except (ValueError,TypeError,KeyError,AttributeError):result.append({'beam_key':key,'status':'INCOMPATIBLE','blockers':['نسخه، قرارداد یا ساختار تاریخی نامعتبر؛ اصلاح مستقل لازم است']})
    for row in project.get('takeoffs',[]):
        if isinstance(row,dict) and row.get('item') in ('beam','beam_concrete','بتن_تیر') and row.get('source_id') not in linked:result.append({'source_id':row.get('source_id'),'status':'UNLINKED_LEGACY','blockers':['ریزقلم تاریخی فاقد دفتر تیر و دیتایل مستقل؛ مهاجرت خودکار ممنوع']})
    for assembly in project.get('takeoff_assemblies',[]):
        if isinstance(assembly,dict) and assembly.get('assembly_code') in ('concrete_beam','beam_concrete'):result.append({'source_id':assembly.get('source_id'),'status':'UNLINKED_LEGACY','blockers':['مجموعه تاریخی تیر قرارداد مستقل دارد؛ نگاشت به دفتر تیر و مجوز مالی لازم است؛ تبدیل خودکار ممنوع']})
    return result


# Links describe identity only. They never construct engineering data or payable rows.
MAPPING_UNITS={'beam':'m3','beam_concrete':'m3','بتن_تیر':'m3','concrete':'m3','rebar':'kg','reinforcement':'kg','formwork':'m2'}

def mapping_record_rows(project,ids):
    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):raise ValueError('انتخاب منبع یکتا و غیرخالی لازم است')
    rows=[]
    for sid in ids:
        text(sid,'شناسه واقعی منبع');matches=[r for r in project.get('takeoffs',[]) if r.get('source_id')==sid]
        if len(matches)!=1:raise ValueError('منبع تاریخی مفقود یا تکراری است')
        row=matches[0]
        if type(row.get('revision')) is not int or row['revision']<1:raise ValueError('نسخه تاریخی معتبر لازم است')
        qs=row.get('quantities')
        if not isinstance(qs,list) or not qs:raise ValueError('کمیت تاریخی نامشخص است')
        from core.takeoff.units import normalize_unit
        for q in qs:
            if q.get('code') not in MAPPING_UNITS or normalize_unit(q.get('unit'))!=MAPPING_UNITS[q['code']]:raise ValueError('عملیات یا واحد تاریخی با قرارداد نگاشت سازگار نیست')
            if number(q.get('amount'),'مقدار تاریخی')<0:raise ValueError('مقدار تاریخی منفی است')
        rows.append(deepcopy(row))
    assemblies=[]
    for group in project.get('takeoff_assemblies',[]):
        members=set(group.get('component_source_ids',[]))
        if members&set(ids):
            if group.get('assembly_code') not in ('concrete_beam','beam_concrete') or not members<=set(ids):raise ValueError('همه اجزای مستقل مجموعه تیر باید صریحاً انتخاب شوند')
            assemblies.append(deepcopy(group))
    return rows,assemblies

def mapping_target(project,target):
    from core.takeoff.beam_detail import _beam_key
    if not isinstance(target,dict) or set(target)!={'floor_id','beam_id','source_id','plan_ref','detail_ref'}:raise ValueError('عضو، طبقه، منبع و مراجع واقعی مقصد لازم است')
    for k,v in target.items():text(v,k)
    key=_beam_key(target['floor_id'],target['beam_id']);record=project.get('beam_detail_register',{}).get(key)
    if record and record.get('data',{}).get('source',{}).get('source_id')!=target['source_id']:raise ValueError('منبع مقصد با دفتر تیر مطابقت ندارد')
    for other,r in project.get('beam_detail_register',{}).items():
        if other!=key and r.get('data',{}).get('source',{}).get('source_id')==target['source_id']:raise ValueError('منبع فیزیکی مقصد به تیر دیگری تعلق دارد')
    for aid in set(project.get('beam_legacy_links',{}).values()):
        m=project['beam_amendments'][aid]['mapping'];same_key=m['beam_key']==key;same_source=m['target']['source_id']==target['source_id']
        if same_key!=same_source:raise ValueError('هویت فیزیکی مقصد با نگاشت قبلی ناسازگار است')
    return key,deepcopy(record)

def mapping_validate(project,mapping,*,applied=False):
    beam_migration_evidence(mapping['evidence']);rows,assemblies=mapping_record_rows(project,mapping['source_ids'])
    if rows!=mapping['original_rows'] or assemblies!=mapping['original_assemblies']:raise RuntimeError('اصل داده تاریخی پس از پیشنهاد تغییر کرده است')
    key,record=mapping_target(project,mapping['target'])
    if key!=mapping['beam_key'] or record!=mapping['target_snapshot']:raise RuntimeError('نسخه مقصد نگاشت تغییر کرده است')
    if not applied and any(sid in project.get('beam_legacy_links',{}) for sid in mapping['source_ids']):raise ValueError('منبع تاریخی قبلاً نگاشت شده است')
    known=set().union(*(set(r.get('committed_source_ids',[])) for r in project.get('beam_detail_register',{}).values()),set())
    if set(mapping['source_ids'])&known:raise ValueError('منبع از قبل به دفتر معتبر متصل است')
    linked_ids=[]
    if record:linked_ids+=record.get('committed_source_ids',[])
    for sid,aid in project.get('beam_legacy_links',{}).items():
        if sid not in mapping['source_ids'] and project['beam_amendments'][aid]['mapping']['beam_key']==key:linked_ids.append(sid)
    if record:
        from core.takeoff.beam_detail import preview_beam
        from core.takeoff.engine import TakeoffEngine
        report=preview_beam(record['data'],TakeoffEngine())
        from core.commercial.exact_values import exact
        @exact
        def totals(values):
            result={}
            for unit,amount in values:result[unit]=result.get(unit,number(0,'صفر صریح'))+number(amount,'مقدار مستند')
            return result
        historic=totals((MAPPING_UNITS[q['code']],q['amount']) for row in rows for q in row['quantities'])
        current=totals((q['unit'],q['quantity']) for q in report['rows'] if report['ready'] or q['unit']!='kg')
        if any(unit in current and current[unit]!=amount for unit,amount in historic.items()):raise ValueError('مقدار تاریخی با مقدار مستند مقصد برابر نیست؛ تطبیق مهندسی مستقل لازم است')

    prior=[r for r in project.get('takeoffs',[]) if r.get('source_id') in linked_ids]
    def operation(q):return (MAPPING_UNITS.get(q['code']),q['unit'])
    if {operation(q) for r in rows for q in r['quantities']}&{operation(q) for r in prior for q in r['quantities']}:raise ValueError('عملیات هم‌واحد برای تیر مقصد مبهم یا تکراری است؛ تطبیق مهندسی مستقل لازم است')

def mapping_create(service,pid,*,source_ids,target,created_by,reason,evidence_path,evidence_sha256,evidence_reference):
    project,token=read(service,pid);rows,assemblies=mapping_record_rows(project,source_ids);key,snapshot=mapping_target(project,target)
    mapping={'version':1,'project_id':pid,'source_ids':deepcopy(source_ids),'target':deepcopy(target),'beam_key':key,'target_snapshot':snapshot,'original_rows':rows,'original_assemblies':assemblies,'evidence':{'evidence_path':evidence_path,'evidence_sha256':evidence_sha256,'evidence_reference':evidence_reference},'needs_detail':True}
    mapping_validate(project,mapping)
    a={'id':'BA-'+uuid4().hex,'kind':'legacy_link','beam_key':key,'revision':1,'status':'draft','created_by':text(created_by,'سازنده نگاشت'),'reason':text(reason,'علت نگاشت'),'mapping':mapping,'created_at':datetime.now(timezone.utc).isoformat()}
    project.setdefault('beam_amendments',{})[a['id']]=a;service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'mapping_create','id':a['id']});return deepcopy(a)

def mapping_transition(service,pid,aid,action,*,expected_revision,reviewer=None,note=None):
    project,token=read(service,pid);a=project['beam_amendments'][aid];revision(expected_revision,a['revision']);mapping_validate(project,a['mapping'])
    if action=='review':
        actor=text(reviewer,'بازبین مستقل');text(note,'یادداشت بازبینی')
        if a['status']!='draft' or actor.casefold()==a['created_by'].casefold():raise ValueError('بازبینی مستقل معتبر نیست')
        a.update(status='reviewed',review={'reviewer':actor,'note':note,'digest':digest(beam_review_payload(a))})
    else:
        financial_block(project)
        if a['status']!='reviewed' or a['review']['digest']!=digest(beam_review_payload(a)):raise ValueError('اعمال بدون بازبینی یا تکراری ممنوع')
        a.update(status='applied',applied_at=datetime.now(timezone.utc).isoformat());project.setdefault('beam_legacy_links',{}).update({sid:aid for sid in a['mapping']['source_ids']})
    service.store.save(pid,project,expected_digest=token,manual_formula_command={'action':'mapping_'+action,'id':aid});return deepcopy(a)

def mapping_guard(previous,updated,command):
    old=previous.get('beam_amendments',{});new=updated.get('beam_amendments',{});links=previous.get('beam_legacy_links',{})
    for sid,aid in links.items():
        a=old[aid]
        target=a['mapping']['target'];key=a['mapping']['beam_key']
        for registered_key,r in updated.get('beam_detail_register',{}).items():
            physical=r.get('data',{}).get('source',{}).get('source_id')
            if physical and ((registered_key==key)!=(physical==target['source_id'])):raise ValueError('تغییر یا استفاده مجدد هویت عضو نگاشت‌شده ممنوع است')
        if new.get(aid)!=a or updated.get('beam_legacy_links',{}).get(sid)!=aid:raise ValueError('اصل نگاشت اعمال‌شده قابل تغییر نیست')
        for row in a['mapping']['original_rows']:
            if [r for r in updated.get('takeoffs',[]) if r.get('source_id')==row['source_id']]!=[row]:raise ValueError('اصل متره نگاشت‌شده قابل تغییر نیست')
        for assembly in a['mapping']['original_assemblies']:
            if assembly not in updated.get('takeoff_assemblies',[]):raise ValueError('اصل مجموعه تاریخی قابل تغییر نیست')
    if links:
        from core.takeoff.commit_guards import rebuild_project_boq
        _,expected=rebuild_project_boq(updated,updated.get('takeoffs',[]))
        def view(rows):return [(r.get('source_ids'),r['unit'],r['item_code'],number(r['quantity'],'کمیت')) for r in rows if set(r.get('source_ids',[]))&set(links)]
        if view(expected)!=view(updated.get('boq',[])):raise ValueError('BOQ مرتبط با اصل نگاشت تغییر کرده است')
    if not isinstance(command,dict) or not command.get('action','').startswith('mapping_'):
        if links!=updated.get('beam_legacy_links',{}):raise ValueError('نگاشت فقط از گردش رسمی مجاز است')
        return
    aid=command['id'];a=new.get(aid);action=command['action']
    if not a or a.get('kind')!='legacy_link' or any(v!=new.get(k) for k,v in old.items() if k!=aid) or set(new)-set(old)-{aid} or set(old)-set(new):raise ValueError('تغییر نامعتبر دفتر نگاشت')
    mapping_validate(previous,a['mapping'])
    expected_links=deepcopy(links)
    if action=='mapping_create':
        if aid in old or a['status']!='draft':raise ValueError('درخواست نگاشت تکراری')
        text(a['created_by'],'سازنده');text(a['reason'],'علت')
    else:
        prior=old.get(aid);allowed={'status','review'} if action=='mapping_review' else {'status','applied_at'}
        if not prior or {k:v for k,v in prior.items() if k not in allowed}!={k:v for k,v in a.items() if k not in allowed}:raise ValueError('پیشنهاد نگاشت تغییر کرد')
        if action=='mapping_review':
            text(a['review']['reviewer'],'بازبین');text(a['review']['note'],'یادداشت')
            if prior['status']!='draft' or a['status']!='reviewed' or text(a['review']['reviewer'],'بازبین').casefold()==text(a['created_by'],'سازنده').casefold() or a['review']['digest']!=digest(beam_review_payload(a)):raise ValueError('بازبینی نگاشت معتبر نیست')
        elif action=='mapping_apply':
            financial_block(previous)
            if prior['status']!='reviewed' or a['status']!='applied' or a['review']['digest']!=digest(beam_review_payload(a)):raise ValueError('اعمال نگاشت نامعتبر است')
            expected_links.update({sid:aid for sid in a['mapping']['source_ids']})
        else:raise ValueError('فرمان نگاشت ناشناخته است')
    if updated.get('beam_legacy_links',{})!=expected_links:raise ValueError('اشاره‌گر نگاشت نامعتبر است')
    for field in ('takeoffs','boq','takeoff_assemblies','beam_detail_register','beam_amendment_applied','beam_detail_history'):
        if previous.get(field)!=updated.get(field):raise ValueError('نگاشت حق تغییر اصل، دفتر تیر یا کمیت مالی را ندارد')

def mapping_inventory(project):
    rows=[];known=set().union(*(set(r.get('committed_source_ids',[])) for r in project.get('beam_detail_register',{}).values()),set());assembly_ids=set().union(*(set(a.get('component_source_ids',[])) for a in project.get('takeoff_assemblies',[]) if a.get('assembly_code') in ('concrete_beam','beam_concrete')),set())
    complete_known=set()
    from core.takeoff.beam_detail import preview_beam
    from core.takeoff.engine import TakeoffEngine
    for key,record in project.get('beam_detail_register',{}).items():
        try:
            current=beam_current(project,key)
            if current['data'].get('measurement_policy')=='beam_specialist_v1' and preview_beam(current['data'],TakeoffEngine())['ready']:complete_known.update(record.get('committed_source_ids',[]))
        except (ValueError,TypeError,KeyError):pass
    try:financial_block(project);locked=False
    except ValueError:locked=True
    for r in project.get('takeoffs',[]):
        if r.get('item') not in MAPPING_UNITS and r.get('source_id') not in assembly_ids:continue
        sid=r.get('source_id');aid=project.get('beam_legacy_links',{}).get(sid);status='LINKED' if aid or sid in known else 'NEEDS_MAPPING';blockers=[]
        try:mapping_record_rows(project,[sid])
        except ValueError as e:
            # Whole assemblies are inspected together; a partial selection is not a defect in their rows.
            if sid in assembly_ids:
                ids=next(a['component_source_ids'] for a in project['takeoff_assemblies'] if sid in a.get('component_source_ids',[]))
                try:mapping_record_rows(project,ids)
                except ValueError as err:status='INCOMPLETE';blockers.append(str(err))
            else:status='SOURCE_DUPLICATE' if sum(x.get('source_id')==sid for x in project.get('takeoffs',[]))>1 else 'INCOMPLETE';blockers.append(str(e))
        proposals=[a for a in project.get('beam_amendments',{}).values() if a.get('kind')=='legacy_link' and sid in a['mapping']['source_ids'] and a['status']!='applied']
        if not aid and len({a['beam_key'] for a in proposals})>1:status='AMBIGUOUS'
        if locked and status=='NEEDS_MAPPING':status='FINANCIAL_LOCKED'
        rows.append({'source_id':sid,'project_id':project.get('id'),'floor':r.get('system'),'member':r.get('member_code'),'operation':r.get('item'),'revision':r.get('revision'),'quantities':deepcopy(r.get('quantities')),'status':status,'financial_locked':locked,'needs_detail':sid not in complete_known or status!='LINKED','evidence_required':not aid and sid not in known,'blockers':blockers,'mapping_id':aid,'target':deepcopy(project['beam_amendments'][aid]['mapping']['target']) if aid else None,'original':deepcopy(r)})
    return rows


def mapping_guard_new_rows(project,incoming,source_id,expected_current_registry):
    targets=set()
    if expected_current_registry and expected_current_registry[0]=='beam_detail_register':targets.add(expected_current_registry[1])
    proposals=[project['beam_amendments'][aid]['mapping'] for aid in set(project.get('beam_legacy_links',{}).values())]
    for m in proposals:
        if m['beam_key'] not in targets and m['target']['source_id']!=source_id:continue
        original_units={MAPPING_UNITS[q['code']] for row in m['original_rows'] for q in row['quantities']}
        if original_units&{MAPPING_UNITS.get(q['code']) for row in incoming for q in row.get('quantities',[])}:raise ValueError('عملیات تیر از منبع تاریخی نگاشت‌شده موجود است؛ ثبت دوباره بدون تطبیق رسمی ممنوع')
