"""Reviewed physical quantities and documented weights in project management.

Approved cumulative measurements are observations, not payments. Corrections
supersede an observation explicitly; original observations/reports are retained.
Planned percentages are at the start boundary of the selected report date.
"""
from copy import deepcopy
from decimal import Decimal,localcontext,ROUND_HALF_EVEN,ROUND_HALF_UP
from core.projects.controls import num,integer,text,evidence,find,digest,basis_stale
from core.projects.scheduling import WorkCalendar,current
from core.commercial.exact_values import exact


def _active(p,as_of,extra=None):
    docs=[d for d in p.get('progress_documents',[]) if d['status']=='approved']
    if extra is not None:docs.append(extra)
    superseded={d['supersedes'] for d in docs if d.get('supersedes')}
    return [d for d in docs if d['id'] not in superseded and d['date']<=as_of]


@exact
def _validate_observations(p,extra):
    docs=_active(p,'9999-12-31',extra)
    for a in p.get('project_schedule_tasks',[]):
        ordered=sorted((d for d in docs if d['activity_id']==a['id']),key=lambda d:d['date'])
        seen=set();previous=Decimal(0)
        for d in ordered:
            q=num(d['quantity'],'کارکرد')
            if d['date'] in seen:raise ValueError('برای این فعالیت و تاریخ مشاهده مؤثر تکراری وجود دارد')
            if q<previous:raise ValueError('کاهش کارکرد فقط با اصلاحیه سازگار با سوابق بعدی مجاز است')
            if q>num(a['measurement']['total'],'مقدار مصوب'):raise ValueError('کارکرد بیش از مقدار مصوب است')
            seen.add(d['date']);previous=q


def _transition(p,op,data,actor,key):
    d=find(p.get(key,[]),data.get('id'),'سند')
    review=op.endswith('_review');needed='draft' if review else 'reviewed'
    if d['status']!=needed:raise ValueError('وضعیت سند برای این عملیات معتبر نیست')
    if actor in {d['created_by'],d.get('reviewed_by')}:raise ValueError('بازبین و تأییدکننده باید مستقل باشند')
    evidence(d['source'])
    if key=='progress_documents':
        a=find(p['project_schedule_tasks'],d['activity_id'],'فعالیت')
        if basis_stale(p,a) or d['basis_digest']!=digest(a['measurement']):raise ValueError('مبنای مقدار تغییر کرده است')
        _validate_observations(p,d if not review else None)
    else:_validate_weights(p,d)
    d['status']='reviewed' if review else 'approved';d['reviewed_by' if review else 'approved_by']=actor
    return d


def activity_basis(activities):
    scope=('id','parent_activity_id','wbs_id','floor_ids','zone_ids','member_ids','discipline_id','unit','measurement')
    return digest([{k:a.get(k) for k in scope} for a in activities])


@exact
def _validate_weights(p,d):
    activities=p.get('project_schedule_tasks',[]);ids={a['id'] for a in activities}
    if set(d['weights'])!=ids or set(d['distributions'])!=ids:raise ValueError('وزن و توزیع همه فعالیت‌ها باید پوشش کامل داشته باشد')
    if d['method'] not in {'manual_approved','contractual','approved_amount'}:raise ValueError('روش وزن‌دهی نامعتبر است')
    weights=[num(x,'وزن فعالیت') for x in d['weights'].values()]
    if sum(weights,Decimal(0))<=0:raise ValueError('مجموع وزن باید مثبت باشد')
    integer(d['decimal_places'],'دقت درصد')
    if not 0<=d['decimal_places']<=12 or d['rounding'] not in {'ROUND_HALF_EVEN','ROUND_HALF_UP'}:raise ValueError('سیاست نمایش درصد نامعتبر است')
    if set(d.get('floor_shares',{})) - ids:raise ValueError('سهم طبقات برای فعالیت ناشناخته ثبت شده است')
    for a in activities:
        distribution=d['distributions'][a['id']]
        if distribution not in {'linear_workdays','milestone_finish'}:raise ValueError('توزیع پیشرفت باید صریح انتخاب شود')
        floors=a.get('floor_ids',[]);allocation=d.get('floor_shares',{}).get(a['id'])
        if len(floors)>1 or allocation is not None:
            if not isinstance(allocation,dict) or set(allocation)!=set(floors) or sum((num(x,'سهم طبقه') for x in allocation.values()),Decimal(0))!=1:
                raise ValueError('فعالیت چندطبقه نیازمند سهم صریح طبقات با جمع یک است')
    if d['activity_basis']!=activity_basis(activities):raise ValueError('فعالیت‌ها پس از تنظیم وزن تغییر کرده‌اند؛ نسخه جدید وزن لازم است')


def progress_command(p,op,data,actor,reason):
    if op=='progress_create':
        a=find(p.get('project_schedule_tasks',[]),data.get('activity_id'),'فعالیت');m=a.get('measurement',{})
        if m.get('kind')=='none' or not m.get('total') or basis_stale(p,a):raise ValueError('مقدار مصوب معتبر برای فعالیت موجود نیست')
        q=num(data.get('cumulative_quantity'),'مقدار تجمعی');total=num(m['total'],'مقدار مصوب')
        if q>total:raise ValueError('کارکرد بیش از مقدار مصوب است')
        day=WorkCalendar.valid_date(data.get('date')).isoformat();ref=text(data.get('reference'),'شماره سند')
        docs=p.setdefault('progress_documents',[])
        if any(d['reference']==ref for d in docs):raise ValueError('شماره سند پیشرفت تکراری است')
        target=data.get('supersedes')
        if target:
            old=find(docs,target,'سند اصلاح‌شونده')
            if old['status']!='approved' or old['activity_id']!=a['id'] or old['date']!=day:raise ValueError('اصلاحیه باید همان فعالیت و تاریخ سند تأییدشده را اصلاح کند')
            if any(d.get('supersedes')==target and d['status']=='approved' for d in docs):raise ValueError('این سند قبلاً اصلاح شده است')
        result={'id':f'WORK-{len(docs)+1}','activity_id':a['id'],'date':day,'reference':ref,'quantity':str(q),
                'source':evidence(data.get('source')),'status':'draft','created_by':actor,'reason':reason,
                'supersedes':target,'basis_digest':digest(m),'unit':a.get('unit','')}
        docs.append(result);return result
    if op in {'progress_review','progress_approve'}:return _transition(p,op,data,actor,'progress_documents')
    if op=='weight_create':
        versions=p.setdefault('progress_weight_sets',[]);ref=text(data.get('reference'),'مرجع وزن')
        if any(d['reference']==ref for d in versions):raise ValueError('مرجع وزن تکراری است')
        raw=data.get('weights');dist=data.get('distributions')
        if not isinstance(raw,dict) or not isinstance(dist,dict):raise ValueError('وزن‌ها و توزیع زمانی لازم هستند')
        d={'id':f'WEIGHT-{len(versions)+1}','version':len(versions)+1,'reference':ref,'method':data.get('method'),
           'source':evidence(data.get('source')),'created_by':actor,'reason':reason,'status':'draft',
           'weights':{k:str(num(v,'وزن')) for k,v in raw.items()},'distributions':dist,
           'floor_shares':data.get('floor_shares',{}),'decimal_places':integer(data.get('decimal_places'),'دقت درصد'),
           'rounding':data.get('rounding'),'activity_basis':activity_basis(p.get('project_schedule_tasks',[]))}
        _validate_weights(p,d);versions.append(d);return d
    if op in {'weight_review','weight_approve'}:return _transition(p,op,data,actor,'progress_weight_sets')
    if op=='progress_report':
        reports=p.setdefault('progress_reports',[]);ref=text(data.get('reference'),'مرجع گزارش')
        if any(r['reference']==ref for r in reports):raise ValueError('مرجع گزارش تکراری است')
        r=calculate(p,as_of=data.get('date'))
        if r['actual'] is None or r['planned'] is None:raise ValueError('گزارش قطعی نیازمند داده کامل و تأییدشده است')
        result={'id':f'PROGRESS-{len(reports)+1}','version':len(reports)+1,'reference':ref,'created_by':actor,'reason':reason,**r}
        result['sha256']=digest(result);reports.append(result);return result
    raise ValueError('عملیات پیشرفت ناشناخته است')


def calculate(p,*,as_of):
    day=WorkCalendar.valid_date(as_of).isoformat();activities=p.get('project_schedule_tasks',[])
    weights=next((d for d in reversed(p.get('progress_weight_sets',[])) if d['status']=='approved'),None)
    baseline=(p.get('schedule_baselines') or [None])[-1]
    try:current_schedule=current(p)
    except ValueError:current_schedule=None
    weight_valid=True;issues=[]
    if weights:
        try:_validate_weights(p,weights)
        except ValueError as e:weight_valid=False;issues.append(str(e))
    else:weight_valid=False;issues.append('وزن تأییدشده موجود نیست')
    places=weights['decimal_places'] if weights else 6;rounding=weights['rounding'] if weights else ROUND_HALF_EVEN
    def percent(n):
        if n is None:return None
        with localcontext() as ctx:
            ctx.prec=160
            return format(n.quantize(Decimal(1).scaleb(-places),rounding=rounding),'f')
    documents=_active(p,day);rows=[]
    with localcontext() as ctx:
        ctx.prec=160
        for a in activities:
            m=a.get('measurement',{});total=num(m['total'],'مقدار مبنا') if m.get('total') else None
            obs=sorted((d for d in documents if d['activity_id']==a['id']),key=lambda d:d['date'])
            actual=None;quantity=None
            if obs and total and not basis_stale(p,a) and obs[-1]['basis_digest']==digest(m):quantity=num(obs[-1]['quantity'],'کارکرد');actual=quantity/total*100
            def planned_for(schedule):
                if not schedule or not weights or not weight_valid or a['id'] not in schedule['activities']:return None
                t=schedule['activities'][a['id']];cal=WorkCalendar(schedule['calendar'],schedule['calendar_start'])
                elapsed=0 if day<cal.at(t['es']).isoformat() else max(0,min(t['duration'],cal.index(day)-t['es']))
                if weights['distributions'][a['id']]=='linear_workdays' and t['duration']:return Decimal(elapsed)/Decimal(t['duration'])*100
                return Decimal(100) if day>=t['finish_boundary'] else Decimal(0)
            planned=planned_for(baseline['result'] if baseline else None)
            planned_current=planned_for(current_schedule)
            rows.append({'id':a['id'],'title':a['title'],'unit':a.get('unit',''),'total':str(total) if total is not None else None,
                         'executed':str(quantity) if quantity is not None else None,'remaining':str(total-quantity) if quantity is not None else None,
                         'actual':actual,'planned':planned,'planned_current':planned_current,'weight':num(weights['weights'][a['id']],'وزن') if weights and a['id'] in weights['weights'] else None,
                         'source_document':obs[-1]['id'] if obs else None,'basis_stale':basis_stale(p,a)})
        def aggregate(selected,shares=None):
            if not selected or not weight_valid or any(r['weight'] is None for r in selected):return {'actual':None,'planned':None,'planned_current':None,'variance':None,'variance_current':None,'coverage':False}
            ws={r['id']:r['weight']*(shares or {}).get(r['id'],Decimal(1)) for r in selected};total=sum(ws.values(),Decimal(0))
            positive=[r for r in selected if ws[r['id']]>0]
            actual=sum((ws[r['id']]*r['actual'] for r in positive),Decimal(0))/total if total and all(r['actual'] is not None for r in positive) else None
            planned=sum((ws[r['id']]*r['planned'] for r in positive),Decimal(0))/total if total and all(r['planned'] is not None for r in positive) else None
            planned_current=sum((ws[r['id']]*r['planned_current'] for r in positive),Decimal(0))/total if total and all(r['planned_current'] is not None for r in positive) else None
            return {'actual':percent(actual),'planned':percent(planned),'planned_current':percent(planned_current),'variance_current':percent(actual-planned_current) if actual is not None and planned_current is not None else None,'variance':percent(actual-planned) if actual is not None and planned is not None else None,
                    'coverage':actual is not None and planned is not None,'weight_sum':str(total),'activity_ids':[r['id'] for r in selected]}
        groups={}
        for key,collection in [('floors','floors'),('zones','zones'),('disciplines','disciplines'),('wbs','project_wbs')]:
            groups[key]={}
            for item in p.get(collection,[]):
                id=item['id'];ids=set();shares={}
                descendants={id}
                if key=='wbs':
                    changed=True
                    while changed:
                        add={x['id'] for x in p.get('project_wbs',[]) if x.get('parent_id') in descendants};changed=not add<=descendants;descendants|=add
                for a in activities:
                    match=(id in a.get('floor_ids',[]) if key=='floors' else id in a.get('zone_ids',[]) if key=='zones' else a.get('discipline_id')==id if key=='disciplines' else a.get('wbs_id') in descendants)
                    if match:
                        ids.add(a['id'])
                        if key=='floors' and weights:shares[a['id']]=num(weights.get('floor_shares',{}).get(a['id'],{}).get(id,'1'),'سهم طبقه')
                groups[key][id]=aggregate([r for r in rows if r['id'] in ids],shares)
        result=aggregate(rows)
        raw_weight_total=sum((x['weight'] for x in rows if x['weight'] is not None),Decimal(0))
        for r in rows:
            r['variance']=percent(r['actual']-r['planned']) if r['actual'] is not None and r['planned'] is not None else None
            r['normalized_weight']=percent(r['weight']/raw_weight_total*100) if weight_valid else None
            for key in ['actual','planned','planned_current']:r[key]=percent(r[key])
            if r['weight'] is not None:r['weight']=str(r['weight'])
    return {'project_id':p['id'],'date':day,**result,'activities':rows,'groups':groups,'issues':issues,
            'weight_id':weights['id'] if weights else None,'baseline_id':baseline['id'] if baseline else None,
            'baseline_sha256':baseline['sha256'] if baseline else None,'percentage_policy':{'decimal_places':places,'rounding':rounding}}


def curve(p,frequency):
    if frequency not in {'daily','weekly','monthly'}:raise ValueError('دوره نمودار نامعتبر است')
    buckets={}
    for r in p.get('progress_reports',[]):
        d=WorkCalendar.valid_date(r['date']);key=d.isoformat() if frequency=='daily' else f'{d.isocalendar().year}-{d.isocalendar().week:02d}' if frequency=='weekly' else f'{d.year}-{d.month:02d}'
        old=buckets.get(key)
        if old is None or (r['date'],r['version'])>(old['date'],old['version']):buckets[key]=r
    return [{'date':r['date'],'actual':r['actual'],'planned':r['planned'],'variance':r['variance'],'planned_current':calculate(p,as_of=r['date'])['planned_current'],'report_id':r['id'],'sha256':r['sha256'],'baseline_id':r['baseline_id'],'weight_id':r['weight_id']} for _,r in sorted(buckets.items())]
