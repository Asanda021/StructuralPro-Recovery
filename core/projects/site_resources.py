"""Explicit resource capacity and read-only look-ahead over the existing CPM."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from core.commercial.exact_values import exact
from core.projects.controls import text,num,evidence,find,references,digest
from core.projects.scheduling import WorkCalendar,current

KEYS=('project_resources','resource_assignments','resource_availability','resource_events','activity_resource_requirements')
OPS={'resource_create','resource_review','resource_approve','availability','resource_event','assign','assignment_review','assignment_approve','assignment_cancel','requirements'}

def interval(data):
    start=WorkCalendar.valid_date(data.get('start'));end=WorkCalendar.valid_date(data.get('end'))
    if end<start or (end-start).days>366:raise ValueError('بازه باید مرتب و حداکثر یک سال باشد')
    return start,end

def dates(start,end):
    return [(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]

def valid_source(row):
    try:evidence(row['source']);return True
    except (ValueError,KeyError):return False

def capacity(p,r,day):
    events=[x for x in p.get('resource_events',[]) if x['resource_id']==r['id'] and x['start']<=day<=x['end']]
    if not valid_source(r) or any(not valid_source(x) for x in events):return None
    released={x.get('reference_id') for x in events if x['state']=='released'}
    if any(x['state'] in {'absent','stopped'} and x['id'] not in released for x in events):return Decimal(0)
    superseded={x.get('supersedes') for x in p.get('resource_availability',[])}
    rows=[x for x in p.get('resource_availability',[]) if x['id'] not in superseded and x['resource_id']==r['id'] and x['start']<=day<=x['end']]
    if not rows:return None
    row=rows[-1]
    if not valid_source(row):return None
    if row['state']!='present':return Decimal(0) if row['state']=='absent' else None
    return min(num(r['capacity'],'ظرفیت'),num(row['capacity'],'حضور'))

def work_dates(p,start,end):
    config=p.get('project_control_config',{}).get('schedule')
    if not config:raise ValueError('تقویم معتبر پروژه لازم است')
    cal=WorkCalendar(config['calendar'],config['start'])
    return [x for x in dates(start,end) if WorkCalendar.valid_date(x).weekday() in cal.days and WorkCalendar.valid_date(x) not in cal.holidays]

@exact
def conflicts(p,row):
    r=find(p.get('project_resources',[]),row['resource_id'],'منبع')
    if r.get('status')!='approved':raise ValueError('منبع تأییدشده لازم است')
    days=work_dates(p,*interval(row))
    if not days:raise ValueError('تخصیص باید روز کاری داشته باشد')
    reasons=[]
    for day in days:
        available=capacity(p,r,day)
        if available is None:reasons.append('حضور یا دسترسی تأییدشده نامشخص: '+day);continue
        used=sum((num(x['allocation'],'تخصیص') for x in p.get('resource_assignments',[]) if x['id']!=row['id'] and x.get('status')=='approved' and x['resource_id']==r['id'] and x['start']<=day<=x['end']),Decimal(0))
        if used+num(row['allocation'],'تخصیص')>available:reasons.append('تداخل ظرفیت یا توقف: '+day)
    return reasons

def _new(p,key,id):
    rows=p.setdefault(key,[])
    if any(str(x['id']).strip().casefold()==id.casefold() for x in rows):raise ValueError('شناسه تکراری است')
    return rows

def dispatch(p,op,data,actor,reason):
    id=text(data.get('id'),'شناسه')
    if op=='resource_create':
        rows=_new(p,'project_resources',id);cap=num(data.get('capacity'),'ظرفیت')
        if cap<=0 or data.get('kind') not in {'crew','equipment'}:raise ValueError('نوع یا ظرفیت منبع نامعتبر است')
        discipline=find(p.get('disciplines',[]),data.get('discipline_id'),'رشته')['id']
        r={'id':id,'name':text(data.get('name'),'نام'),'kind':data['kind'],'capacity':str(cap),'quantity':str(cap),'unit':text(data.get('unit'),'واحد'),'discipline_id':discipline,'subcontractor':text(data.get('subcontractor'),'مسئول یا پیمانکار'),'source':evidence(data.get('source')),'created_by':actor,'status':'draft','reason':reason}
        rows.append(r);return r
    if op in {'resource_review','resource_approve','assignment_review','assignment_approve'}:
        key='project_resources' if op.startswith('resource') else 'resource_assignments'
        r=find(p.get(key,[]),id,'سند');review=op.endswith('review')
        if r['status']!=('draft' if review else 'reviewed') or actor in {r['created_by'],r.get('reviewed_by')}:raise ValueError('وضعیت یا استقلال مسئول تأیید معتبر نیست')
        evidence(r['source'])
        if key=='resource_assignments':
            if r['activity_basis']!=digest(find(p['project_schedule_tasks'],r['activity_id'],'فعالیت')):raise ValueError('فعالیت تغییر کرده است؛ تخصیص جدید لازم است')
            problems=conflicts(p,r)
            if problems:raise ValueError('؛ '.join(problems))
        r['status']='reviewed' if review else 'approved';r['reviewed_by' if review else 'approved_by']=actor;return r
    if op in {'availability','resource_event'}:
        key='resource_availability' if op=='availability' else 'resource_events';rows=_new(p,key,id)
        resource=find(p.get('project_resources',[]),data.get('resource_id'),'منبع')
        if resource.get('status')!='approved':raise ValueError('منبع تأیید نشده است')
        start,end=interval(data);state=data.get('state')
        if state not in ({'present','absent','unknown'} if op=='availability' else {'absent','stopped','released'}):raise ValueError('وضعیت دسترسی نامعتبر است')
        r={'id':id,'resource_id':resource['id'],'start':start.isoformat(),'end':end.isoformat(),'state':state,'source':evidence(data.get('source')),'created_by':actor,'reason':reason}
        if op=='resource_event' and state=='released':
            previous=find(rows,data.get('reference_id'),'توقف قبلی')
            if previous['resource_id']!=resource['id'] or previous['state'] not in {'absent','stopped'} or start.isoformat()<previous['start'] or end.isoformat()>previous['end']:raise ValueError('رفع توقف باید به بازه همان توقف متصل باشد')
            r['reference_id']=previous['id']
        if op=='availability':
            if data.get('confirmed') is not True:raise ValueError('تأیید صریح حضور لازم است')
            r['capacity']=str(num(data.get('capacity'),'ظرفیت حضور'))
            if num(r['capacity'],'ظرفیت حضور')>num(resource['capacity'],'ظرفیت'):raise ValueError('حضور بیش از ظرفیت مصوب است')
            replaced=data.get('supersedes');superseded={x.get('supersedes') for x in rows}
            if replaced:
                old=find(rows,replaced,'حضور اصلاح‌شونده')
                if replaced in superseded or old['resource_id']!=r['resource_id'] or (old['start'],old['end'])!=(r['start'],r['end']):raise ValueError('اصلاح حضور باید همان منبع و بازه مؤثر را حفظ کند')
                r['supersedes']=old['id']
            if any(x['id']!=replaced and x['id'] not in superseded and x['resource_id']==resource['id'] and x['start']<=r['end'] and x['end']>=r['start'] for x in rows):raise ValueError('بازه حضور هم‌پوشان است؛ توقف را جدا ثبت کنید')
        rows.append(r);return r
    if op=='assign':
        rows=_new(p,'resource_assignments',id);a=find(p.get('project_schedule_tasks',[]),data.get('activity_id'),'فعالیت');r=find(p.get('project_resources',[]),data.get('resource_id'),'منبع');start,end=interval(data)
        q=num(data.get('allocation'),'تخصیص')
        if q<=0:raise ValueError('تخصیص باید مثبت باشد')
        row={'id':id,'activity_id':a['id'],'resource_id':r['id'],'start':start.isoformat(),'end':end.isoformat(),'allocation':str(q),'source':evidence(data.get('source')),'created_by':actor,'reason':reason,'status':'draft','activity_basis':digest(a),'floor_ids':deepcopy(a.get('floor_ids',[])),'zone_ids':deepcopy(a.get('zone_ids',[]))}
        rows.append(row);return row
    if op=='assignment_cancel':
        r=find(p.get('resource_assignments',[]),id,'تخصیص')
        if r['status']=='cancelled':raise ValueError('تخصیص قبلاً لغو شده است')
        r.update(status='cancelled',cancelled_by=actor,cancel_reason=reason);return r
    if op=='requirements':
        rows=_new(p,'activity_resource_requirements',id);a=find(p.get('project_schedule_tasks',[]),data.get('activity_id'),'فعالیت')
        resources=data.get('resources');materials=data.get('materials')
        if not isinstance(resources,list) or not isinstance(materials,list):raise ValueError('نیاز منابع و مصالح باید صریح باشد')
        seen=set()
        for r in resources:
            rid=find(p.get('project_resources',[]),r.get('resource_id'),'منبع')['id']
            if rid in seen or num(r.get('quantity'),'نیاز')<=0:raise ValueError('نیاز تکراری یا نامعتبر است')
            seen.add(rid)
        for mid in materials:find(p.get('material_requirements',[]),mid,'نیاز مصالح')
        row={'id':id,'activity_id':a['id'],'resources':[{'resource_id':r['resource_id'],'quantity':str(num(r['quantity'],'نیاز'))} for r in resources],'materials':deepcopy(materials),'source':evidence(data.get('source')),'created_by':actor,'activity_basis':digest(a),'reason':reason}
        rows.append(row);return row
    raise ValueError('عملیات منبع نامعتبر است')

@exact
def lookahead(p,*,start,days=None,end=None):
    first=WorkCalendar.valid_date(start)
    if end is None:
        if isinstance(days,bool) or days not in {7,14}:raise ValueError('افق باید ۷ یا ۱۴ روز یا بازه صریح باشد')
        last=first+timedelta(days=days-1)
    else:
        if days is not None:raise ValueError('فقط افق یا پایان را تعیین کنید')
        last=WorkCalendar.valid_date(end)
    interval({'start':first.isoformat(),'end':last.isoformat()})
    try:plan=current(p);error=None
    except ValueError as e:plan=None;error=str(e)
    result=[]
    for a in p.get('project_schedule_tasks',[]):
        schedule=plan['activities'][a['id']] if plan else None
        if schedule and (schedule['finish']<start or schedule['start']>last.isoformat()):continue
        reasons=[];status='ready'
        if not schedule:reasons.append(error);status='insufficient_information'
        req=next((x for x in reversed(p.get('activity_resource_requirements',[])) if x['activity_id']==a['id']),None)
        if req is None or req.get('activity_basis')!=digest(a) or not valid_source(req):reasons.append('نیاز منابع فعالیت ثبت نشده، قدیمی یا دارای مدرک نامعتبر است');status='insufficient_information'
        occupied=work_dates(p,max(first,WorkCalendar.valid_date(schedule['start'])),min(last,WorkCalendar.valid_date(schedule['finish']))) if schedule else []
        if req and schedule:
            for need in req['resources']:
                resource=find(p.get('project_resources',[]),need['resource_id'],'منبع')
                assignments=[x for x in p.get('resource_assignments',[]) if x.get('status')=='approved' and x['activity_id']==a['id'] and x['resource_id']==resource['id'] and x.get('activity_basis')==digest(a) and valid_source(x)]
                for day in occupied:
                    allocated=sum((num(x['allocation'],'تخصیص') for x in assignments if x['start']<=day<=x['end']),Decimal(0))
                    if allocated<num(need['quantity'],'نیاز'):reasons.append('تخصیص کافی نیست: '+resource['id']+' '+day);status='insufficient_information'
                    available=capacity(p,resource,day)
                    total=sum((num(x['allocation'],'تخصیص') for x in p.get('resource_assignments',[]) if x.get('status')=='approved' and x['resource_id']==resource['id'] and x['start']<=day<=x['end']),Decimal(0))
                    if available is None:reasons.append('دسترسی نامشخص: '+day);status='insufficient_information'
                    elif total>available:reasons.append('تداخل یا توقف منبع: '+resource['id']+' '+day);status='resource_conflict'
            if req['materials']:
                from core.projects.site_materials import snapshot
                materials=snapshot(p,as_of=start,activity_id=a['id'])
                by={x['id']:x for x in materials['requirements']}
                for mid in req['materials']:
                    material=by.get(mid)
                    if not material or not material['current'] or material['shortage'] is None:
                        reasons.append('موجودی یا مبنای مصالح نامشخص: '+mid);status='insufficient_information'
                    elif num(material['shortage'],'کسری')>0:
                        reasons.append('کسری مستند مصالح: '+mid);status='human_decision'
        if a.get('schedule',{}).get('relationships'):
            from core.projects.physical_progress import _active
            observations=_active(p,start)
            for rel in a['schedule']['relationships']:
                pred=find(p['project_schedule_tasks'],rel['pred'],'پیش‌نیاز')
                q=max((num(x['quantity'],'کارکرد') for x in observations if x['activity_id']==pred['id']),default=None)
                if rel['type']=='FS' and rel['lag']>=0:
                    if q is None or pred.get('measurement',{}).get('total') is None or q<num(pred['measurement']['total'],'مبنا'):
                        reasons.append('تکمیل پیش‌نیاز تأیید نشده: '+pred['id']);status='dependent'
                else:reasons.append('کنترل انسانی رابطه اجرایی: '+pred['id']);status='human_decision'
        resolved={x['target_id'] for x in p.get('site_action_events',[]) if x['kind']=='obstacle_resolve' and x['date']<=start}
        for blocker in p.get('site_obstacles',[]):
            if blocker.get('date','9999-12-31')<=start and blocker.get('activity_id')==a['id'] and blocker['id'] not in resolved:reasons.append('مانع باز: '+blocker['id']);status='human_decision'
        result.append({'id':a['id'],'title':a['title'],'responsible':a.get('responsible'),'floor_ids':a.get('floor_ids',[]),'zone_ids':a.get('zone_ids',[]),'start':schedule['start'] if schedule else None,'finish':schedule['finish'] if schedule else None,'work_dates':occupied,'resources':req['resources'] if req else None,'status':status,'reasons':reasons,'requirement_id':req['id'] if req else None})
    return {'project_id':p['id'],'start':start,'end':last.isoformat(),'activities':result,'schedule_digest':digest(plan) if plan else None,'baseline_unchanged':True}
