"""Validated commands extending existing project management and SQLite payloads.

No payable BOQ mutation occurs here. Local actor names attribute changes; they
are not authentication. Commands are replayed by the store before commit.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from core.projects.project_model import _identity
from core.takeoff.units import normalize_unit

KEYS = ('buildings','floors','zones','disciplines','project_wbs','project_schedule_tasks',
        'project_control_history','project_control_config','schedule_baselines',
        'progress_documents','progress_weight_sets','progress_reports')


def text(value, label):
    if not isinstance(value,str) or not value.strip():raise ValueError(f'{label}: مقدار صریح الزامی است')
    return value.strip()


def num(value, label, *, signed=False):
    if isinstance(value,bool) or value is None:raise ValueError(f'{label}: عدد معتبر لازم است')
    try:d=Decimal(str(value))
    except Exception as e:raise ValueError(f'{label}: عدد معتبر لازم است') from e
    if not d.is_finite() or abs(d)>Decimal('1e60') or d.as_tuple().exponent < -30 or (d<0 and not signed):
        raise ValueError(f'{label}: عدد خارج از محدوده است')
    return d


def integer(value,label,*,signed=False):
    n=num(value,label,signed=signed)
    if n!=n.to_integral_value():raise ValueError(f'{label}: عدد صحیح لازم است')
    return int(n)


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def evidence(value):
    if not isinstance(value,dict):raise ValueError('مدرک منبع الزامی است')
    path=text(value.get('path'),'مسیر مدرک');sha=text(value.get('sha256'),'هش مدرک')
    if not Path(path).is_file() or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('مدرک موجود نیست یا هش تغییر کرده است')
    return {'path':path,'sha256':sha,'reference':text(value.get('reference'),'مرجع مدرک')}


def find(rows,id,label):
    found=[r for r in rows if _identity(r.get('id'))==_identity(id)]
    if len(found)!=1:raise ValueError(f'{label}: شناسه موجود نیست یا مبهم است')
    return found[0]


def references(p,key,ids,label):
    if not isinstance(ids,list) or len({_identity(x) for x in ids})!=len(ids):raise ValueError(f'{label}: شناسه تکراری یا نامعتبر')
    return [find(p.get(key,[]),x,label)['id'] for x in ids]


def measurement(p,value,unit,activity_id):
    if not isinstance(value,dict) or value.get('kind') not in {'none','boq','explicit'}:raise ValueError('مبنای سنجش صریح لازم است')
    kind=value['kind']
    if kind=='none':return {'kind':'none'}
    if not unit:raise ValueError('واحد سنجش الزامی است')
    if kind=='explicit':
        total=num(value.get('total'),'مقدار مصوب')
        if total<=0:raise ValueError('مقدار مبنا باید مثبت باشد')
        proof=evidence(value.get('source'));approved=text(value.get('approved_by'),'تأییدکننده مبنا')
        return {'kind':kind,'total':str(total),'source':proof,'approved_by':approved,'unit':unit}
    ids=value.get('source_ids')
    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):raise ValueError('شناسه منابع BOQ معتبر نیست')
    from core.reports.aec_office_package import audit_boq
    audit_boq(p)
    selected=[]
    for r in p.get('boq',[]):
        if normalize_unit(r.get('unit',''))!=unit or (value.get('item_code') and r.get('item_code')!=value['item_code']):continue
        sources=r.get('source_ids') or [r.get('source_id')]
        if set(ids)&set(sources):
            if set(ids)!=set(sources):raise ValueError('ردیف تجمیعی باید با تمام منابع خود تخصیص یابد')
            selected.append(r)
    if len(selected)!=1:raise ValueError('ردیف BOQ یکتا و معتبر یافت نشد')
    row=selected[0]
    if row.get('status','active')!='active' or normalize_unit(row.get('unit',''))!=unit:raise ValueError('وضعیت یا واحد BOQ ناسازگار است')
    total=num(row.get('quantity'),'مقدار BOQ')
    if total<=0:raise ValueError('مقدار BOQ باید مثبت باشد')
    for a in p.get('project_schedule_tasks',[]):
        if a['id']!=activity_id and a.get('measurement',{}).get('item_code')==row.get('item_code') and a.get('measurement',{}).get('unit')==unit and set(ids)&set(a.get('measurement',{}).get('source_ids',[])):raise ValueError('منبع مقدار به فعالیت دیگری تخصیص یافته است')
    return {'kind':'boq','source_ids':ids,'total':str(total),'unit':unit,'basis_digest':boq_basis(p,row),'item_code':row.get('item_code')}


def boq_basis(p,row):
    # Cash/current-period fields and display ordering are not quantity revisions.
    keys=('item_code','unit','quantity','source_id','source_ids','source_type','revision','provenance')
    sources=set(row.get('source_ids') or [row.get('source_id')])
    from core.takeoff.manual_formula_amendments import effective_takeoffs
    effective=effective_takeoffs(p,p.get('takeoffs') or [])
    records=[r for r in effective if r.get('source_id') in sources]
    return digest({'quantity':{k:row.get(k) for k in keys},'sources':records})


def basis_stale(p,a):
    m=a.get('measurement',{})
    if m.get('kind')!='boq':return False
    rows=[r for r in p.get('boq',[]) if set(r.get('source_ids') or [r.get('source_id')])==set(m['source_ids']) and r.get('item_code')==m.get('item_code') and normalize_unit(r.get('unit',''))==m.get('unit')]
    return len(rows)!=1 or boq_basis(p,rows[0])!=m['basis_digest']


def hierarchy(rows):
    by={r['id']:r for r in rows}
    if len({_identity(x) for x in by})!=len(rows):raise ValueError('شناسه ساختار تکراری است')
    for r in rows:
        seen={r['id']};parent=r.get('parent_id')
        while parent is not None:
            if parent not in by or parent in seen:raise ValueError('والد WBS نامعتبر یا حلقه وجود دارد')
            seen.add(parent);parent=by[parent].get('parent_id')
    if len({_identity(r['code']) for r in rows})!=len(rows):raise ValueError('کد WBS تکراری است')


def apply(project,command):
    p=deepcopy(project);op=command['op'];data=deepcopy(command.get('data',{}))
    actor=text(command.get('actor'),'مسئول تغییر');reason=text(command.get('reason'),'دلیل تغییر')
    history=p.setdefault('project_control_history',[])
    p.setdefault('project_control_config',{'schema':1})
    result=None
    if op in {'building','floor','zone','discipline','wbs','activity'}:
        key={'building':'buildings','floor':'floors','zone':'zones','discipline':'disciplines','wbs':'project_wbs','activity':'project_schedule_tasks'}[op]
        id=text(data.get('id'),'شناسه');rows=p.setdefault(key,[])
        old=next((r for r in rows if _identity(r.get('id'))==_identity(id)),None)
        if old and old['id']!=id:raise ValueError('املای شناسه موجود قابل تغییر نیست')
        title=text(data.get('title'),'عنوان');r={**deepcopy(old or {}),'id':id,'title':title}
        if op=='floor':
            r.update(name=title,building_id=find(p.get('buildings',[]),data.get('building_id'),'بلوک')['id'],
                     kind=data.get('kind'),level=integer(data.get('level'),'تراز طبقه',signed=True),height=str(num(data.get('height'),'ارتفاع')))
            if r['kind'] not in {'basement','ground','positive','roof'} or Decimal(r['height'])<=0:raise ValueError('نوع طبقه یا ارتفاع نامعتبر است')
        elif op=='zone':r['floor_ids']=references(p,'floors',data.get('floor_ids'),'طبقه')
        elif op=='wbs':r.update(parent_id=data.get('parent_id'),code=text(data.get('code'),'کد WBS'))
        elif op=='activity':
            r.update(code=text(data.get('code'),'کد فعالیت'),wbs_id=find(p.get('project_wbs',[]),data.get('wbs_id'),'WBS')['id'],
                floor_ids=references(p,'floors',data.get('floor_ids'),'طبقه'),zone_ids=references(p,'zones',data.get('zone_ids'),'زون'),
                member_ids=references(p,'members',data.get('member_ids'),'عضو'),discipline_id=find(p.get('disciplines',[]),data.get('discipline_id'),'رشته')['id'],
                unit=normalize_unit(text(data.get('unit'),'واحد')),responsible=text(data.get('responsible'),'مسئول'),status=data.get('status'))
            if r['status'] not in {'todo','in_progress','blocked','done','cancelled'}:raise ValueError('وضعیت فعالیت نامعتبر است')
            for z in r['zone_ids']:
                if not set(find(p['zones'],z,'زون')['floor_ids'])<=set(r['floor_ids']):raise ValueError('زون با طبقات فعالیت ناسازگار است')
            for m in r['member_ids']:
                if find(p['members'],m,'عضو')['floor_id'] not in r['floor_ids']:raise ValueError('عضو با طبقات فعالیت ناسازگار است')
            parent=data.get('parent_activity_id')
            if parent is not None:parent=find(rows,parent,'فعالیت والد')['id']
            r['parent_activity_id']=parent
            r['measurement']=measurement(p,data.get('measurement'),r['unit'],id)
            if old:
                for k in ('schedule','planned_start','planned_end','predecessor_ids'):
                    if k in old:r[k]=old[k]
                if old.get('measurement')!=r['measurement'] and any(x.get('activity_id')==id and x.get('status')=='approved' for x in p.get('progress_documents',[])):
                    raise ValueError('تغییر مبنای فعالیت دارای کارکرد تأییدشده نیازمند فعالیت مستقل و رسیدگی رسمی است')
            # Legacy schedule views can still read the same collection.
            r.setdefault('planned_start','');r.setdefault('planned_end','')
        if old:rows[rows.index(old)]=r
        else:rows.append(r)
        if op=='wbs':hierarchy(rows)
        if op=='activity':hierarchy([{**a,'parent_id':a.get('parent_activity_id')} for a in rows])
        if op=='activity' and len({_identity(a.get('code')) for a in rows})!=len(rows):raise ValueError('کد فعالیت تکراری است')
        result=r
    elif op=='move_activity':
        r=find(p.get('project_schedule_tasks',[]),data.get('id'),'فعالیت');r['wbs_id']=find(p.get('project_wbs',[]),data.get('wbs_id'),'WBS')['id'];result=r
    else:
        # Later priorities extend this same dispatch, not a parallel project model.
        from core.projects.scheduling import schedule_command
        if op.startswith('schedule_'):result=schedule_command(p,op,data,actor,reason)
        elif op.startswith('progress_') or op.startswith('weight_'):
            from core.projects.physical_progress import progress_command
            result=progress_command(p,op,data,actor,reason)
        else:raise ValueError('عملیات کنترل پروژه ناشناخته است')
    history.append({'sequence':len(history)+1,'op':op,'actor':actor,'reason':reason,'at':command['at'],'data':data,'result_digest':digest(result)})
    return p,deepcopy(result)


def guard(before,after,command):
    official=('project_control_config','project_control_history','project_wbs','schedule_baselines','progress_documents','progress_weight_sets','progress_reports')
    if not before.get('project_control_config') and not after.get('project_control_config') and all(before.get(k)==after.get(k) for k in official):return
    if command is None:
        if any(before.get(k)!=after.get(k) for k in KEYS):raise ValueError('تغییر کنترل پروژه فقط از گردش ثبت‌شده مجاز است')
        return
    expected,_=apply(before,command)
    if any(expected.get(k)!=after.get(k) for k in KEYS):raise ValueError('ثبت کنترل پروژه با فرمان معتبر تطبیق ندارد')


def snapshot(project):
    p=deepcopy(project)
    return {'project_id':p['id'],'version':p['_meta']['version'],
            'buildings':p.get('buildings',[]),'floors':p.get('floors',[]),'zones':p.get('zones',[]),
            'disciplines':p.get('disciplines',[]),'wbs':p.get('project_wbs',[]),
            'activities':[{**a,'basis_stale':basis_stale(p,a)} for a in p.get('project_schedule_tasks',[])],
            'history':p.get('project_control_history',[])}
