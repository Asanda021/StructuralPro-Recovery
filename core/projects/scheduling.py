"""CPM in explicit integer workday boundaries; display finish is last workday.

A task occupies [ES, EF). A zero-duration milestone is at ES. FS/SS/FF/SF
are lower bounds on successor starts. Lag/lead is signed workdays in the
single explicitly chosen project calendar; no implicit statutory holidays.
"""
from copy import deepcopy
from bisect import bisect_left
from datetime import date,timedelta
import heapq
from core.projects.controls import integer,text,find,digest
from core.projects.precedence_model import driving_graph, precedence_order, relation_weight
from core.projects.schedule_calendars import calendar_registry, dated_cpm, selected_calendars


_UNSUPPORTED_SCHEDULE_FIELDS = {
    'constraint', 'constraints', 'deadline', 'actual_start',
    'actual_finish', 'actual_end', 'remaining_duration', 'data_date',
}


def _check_schedule_fields(data, *, allow_calendar=False):
    if _UNSUPPORTED_SCHEDULE_FIELDS.intersection(data) or ('calendar' in data and not allow_calendar):
        raise ValueError('مهلت و کارکرد واقعی در ورودی مستقیم CPM پشتیبانی نمی‌شوند')


def _duration(value):
    duration = integer(value, 'مدت کاری')
    if duration > 100000:
        raise ValueError('مدت بیش از افق پشتیبانی‌شده است')
    return duration


class WorkCalendar:
    def __init__(self,config,start):
        self.start=self.valid_date(start)
        if not isinstance(config,dict):raise ValueError('تقویم کاری صریح لازم است')
        days=config.get('weekdays')
        if not isinstance(days,list) or not days:raise ValueError('روزهای کاری تقویم نامعتبر است')
        self.days={integer(x,'روز هفته') for x in days}
        if len(self.days)!=len(days) or not self.days<=set(range(7)):raise ValueError('روز هفته باید یکتا و بین صفر و شش باشد')
        holidays=config.get('holidays')
        if not isinstance(holidays,list):raise ValueError('تعطیلات تقویم باید صریح باشند')
        self.holidays={self.valid_date(x) for x in holidays}
        exceptions=config.get('working_exceptions',[])
        if not isinstance(exceptions,list):raise ValueError('استثناهای روز کاری باید صریح باشند')
        self.exceptions={self.valid_date(x) for x in exceptions}
        if self.holidays & self.exceptions:raise ValueError('یک تاریخ نمی‌تواند هم تعطیل و هم روز کاری استثنایی باشد')
        if any(key in config for key in ('shift_hours','shifts','working_hours','half_days','timezone','official_holidays')):
            raise ValueError('تقویم فقط روز مدنی کامل و تعطیلی صریح ثبت‌شده را پشتیبانی می‌کند')
        self.dates=[];self.cursor=self.start
        self.closed=sorted(day for day in self.holidays if day>=self.start and day.weekday() in self.days)
        self.extra=sorted(day for day in self.exceptions if day>=self.start and day.weekday() not in self.days)
    @staticmethod
    def valid_date(value):
        if not isinstance(value,str):raise ValueError('تاریخ ISO معتبر لازم است')
        try:d=date.fromisoformat(value)
        except (ValueError,TypeError) as e:raise ValueError('تاریخ نامعتبر است') from e
        if d.isoformat()!=value:raise ValueError('قرارداد تاریخ باید YYYY-MM-DD باشد')
        return d
    def at(self,index):
        if index<0 or index>100000:raise ValueError('افق برنامه خارج از محدوده است')
        while len(self.dates)<=index:
            if (self.cursor-self.start).days>365000:raise ValueError('تقویم قابل محاسبه نیست')
            if self.is_open(self.cursor):self.dates.append(self.cursor)
            if len(self.dates)>index and self.cursor==date.max:return self.dates[index]
            try:self.cursor+=timedelta(days=1)
            except OverflowError as e:raise ValueError('سرریز تاریخ برنامه') from e
        return self.dates[index]
    def is_open(self,day):
        return day not in self.holidays and (day.weekday() in self.days or day in self.exceptions)

    def index_day(self,day):
        if day <= self.start:return 0
        weeks, remainder = divmod((day-self.start).days,7)
        ordinary = weeks*len(self.days)+sum((self.start.weekday()+i)%7 in self.days for i in range(remainder))
        return ordinary-bisect_left(self.closed,day)+bisect_left(self.extra,day)

    def index(self,value):
        return self.index_day(self.valid_date(value))


def cpm(tasks,relationships,*,start,calendar,calendars=None,resource_calendars=None):
    try:
        tasks=list(tasks)
        relationships=list(relationships)
    except TypeError as exc:
        raise ValueError('فهرست فعالیت و روابط برنامه باید معتبر باشد') from exc
    if not tasks:
        raise ValueError('فهرست فعالیت و روابط برنامه باید معتبر باشد')
    cal=WorkCalendar(calendar,start);by={};duration={}
    calendars = {} if calendars is None else calendars
    resource_calendars = {} if resource_calendars is None else resource_calendars
    parsed = calendar_registry(start, calendars, resource_calendars, WorkCalendar)
    separate = False
    for t in tasks:
        if not isinstance(t,dict):raise ValueError('فعالیت برنامه نامعتبر است')
        _check_schedule_fields(t)
        ids = selected_calendars(t, parsed, resource_calendars)
        separate = separate or ids != ('PROJECT',)
        id=text(t.get('id'),'شناسه فعالیت')
        if id in by:raise ValueError('شناسه فعالیت تکراری است')
        by[id]=t;duration[id]=_duration(t.get('duration'))
    adj={k:[] for k in by};incoming={k:[] for k in by};degree={k:0 for k in by};seen=set();links=[]
    for r in relationships:
        if not isinstance(r,dict):raise ValueError('رابطه پیش‌نیازی نامعتبر است')
        a,b,kind=r.get('pred'),r.get('succ'),r.get('type')
        if not isinstance(a,str) or not isinstance(b,str) or a not in by or b not in by or a==b or kind not in ('FS','SS','FF','SF'):raise ValueError('رابطه پیش‌نیازی نامعتبر است')
        if (a,b) in seen:raise ValueError('رابطه تکراری یا متعارض است')
        seen.add((a,b));lag=integer(r.get('lag'),'وقفه کاری',signed=True)
        offset=relation_weight(duration[a],duration[b],kind,lag)
        adj[a].append((b,offset));incoming[b].append((a,offset));degree[b]+=1
        links.append(({'pred':a,'succ':b,'type':kind,'lag':lag}, offset))
    ready=[k for k in by if not degree[k]];heapq.heapify(ready);order=[]
    while ready:
        a=heapq.heappop(ready);order.append(a)
        for b,_ in adj[a]:
            degree[b]-=1
            if not degree[b]:heapq.heappush(ready,b)
    if len(order)!=len(by):raise ValueError('حلقه در شبکه فعالیت‌ها مجاز نیست')
    if separate:
        return dated_cpm(by, duration, order, links, relationships, cal, calendar, calendars, resource_calendars, parsed)
    bounds={k:cal.index(t['not_before']) if t.get('not_before') is not None else 0 for k,t in by.items()}
    es=bounds.copy()
    for a in order:
        for b,offset in adj[a]:es[b]=max(es[b],es[a]+offset)
    end=max(es[k]+duration[k] for k in by);cal.at(end)
    ls={k:end-duration[k] for k in by}
    for a in reversed(order):
        for b,offset in adj[a]:ls[a]=min(ls[a],ls[b]-offset)
    rows={}
    for k in order:
        ef=es[k]+duration[k];tf=ls[k]-es[k]
        ff=min([end-ef]+[es[b]-es[k]-offset for b,offset in adj[k]])
        rows[k]={'id':k,'duration':duration[k],'es':es[k],'ef':ef,'ls':ls[k],'lf':ls[k]+duration[k],
             'total_float':tf,'free_float':ff,'critical':tf==0,'milestone':duration[k]==0,
             'start':cal.at(es[k]).isoformat(),'finish':cal.at(ef-1 if duration[k] else ef).isoformat(),
             'finish_boundary':cal.at(ef).isoformat(),'late_start':cal.at(ls[k]).isoformat(),
             'late_finish_boundary':cal.at(ls[k]+duration[k]).isoformat()}
    tight=[link for link,offset in links if es[link['succ']]==es[link['pred']]+offset]
    driving=driving_graph(order,tight,[key for key in order if rows[key]['ef']==end],
                          {key:'NOT_BEFORE' for key in order if bounds[key] and es[key]==bounds[key]})
    return {'activities':rows,'order':order,'duration':end,'start':cal.at(0).isoformat(),
            'finish_boundary':cal.at(end).isoformat(),'critical_ids':[k for k in order if rows[k]['critical']],
            'relationships':deepcopy(relationships),'calendar':deepcopy(calendar),'calendar_start':start,
            'driving':driving,'cpm_scope':'SHARED_PROJECT_WORKDAYS','offset_unit':'PROJECT_WORKDAY',
            'warnings':[{'id':k,'message':'فعالیت ریشه؛ بدون پیش‌نیاز'} for k in order if not incoming[k]]}


def current(project):
    config=project.get('project_control_config',{}).get('schedule')
    if not config:raise ValueError('تاریخ شروع و تقویم پروژه ثبت نشده است')
    tasks=[];rels=[]
    for a in project.get('project_schedule_tasks',[]):
        if not a.get('schedule'):raise ValueError('مدت و روابط همه فعالیت‌ها باید صریح ثبت شوند')
        tasks.append({'id':a['id'],**a['schedule']});rels.extend(a['schedule']['relationships'])
    result=cpm(tasks,rels,start=config['start'],calendar=config['calendar'],
               calendars=config.get('calendars'),resource_calendars=config.get('resource_calendars'))
    for a in project.get('project_schedule_tasks',[]):
        result['activities'][a['id']].update(title=a['title'],wbs_id=a.get('wbs_id'))
    result['input_digest']=digest({'config':config,'tasks':tasks})
    if 'calendar_version' in config:
        result['calendar_version']=config['calendar_version']
        result.setdefault('calendars',deepcopy(config.get('calendars',{})))
        result.setdefault('resource_calendars',deepcopy(config.get('resource_calendars',{})))
    return result


def activity_work_dates(schedule, activity_id, first, last):
    """Occupied dates within an inclusive window, using the saved CPM calendar."""
    row = schedule['activities'][activity_id]
    if row['milestone']:
        return []
    lo = max(first, WorkCalendar.valid_date(row['start']))
    hi = min(last, WorkCalendar.valid_date(row['finish']))
    start = schedule['calendar_start']
    definitions = [schedule['calendar'] if key == 'PROJECT' else schedule['calendars'][key]
                   for key in row.get('calendar_ids', ['PROJECT'])]
    calendars = [WorkCalendar(definition, start) for definition in definitions]
    days = (lo + timedelta(days=i) for i in range(max(0, (hi - lo).days + 1)))
    return [day.isoformat() for day in days if all(calendar.is_open(day) for calendar in calendars)]


def _refresh_schedule_projection(p):
    result = current(p)
    for task in p['project_schedule_tasks']:
        row = result['activities'][task['id']]
        task.update(planned_start=row['start'],planned_end=row['finish'],
                    predecessor_ids=[link['pred'] for link in task['schedule']['relationships']])
    return result


def schedule_command(p,op,data,actor,reason):
    config=p['project_control_config']
    if op=='schedule_calendar':
        _check_schedule_fields(data, allow_calendar=True)
        previous=config.get('schedule',{})
        base=deepcopy(data.get('calendar'))
        if isinstance(base,dict) and 'working_exceptions' not in base and 'working_exceptions' in previous.get('calendar',{}):
            base['working_exceptions']=deepcopy(previous['calendar']['working_exceptions'])
        WorkCalendar(base,data.get('start')).at(0)
        calendars=data.get('calendars',previous.get('calendars',{}))
        mappings=data.get('resource_calendars',previous.get('resource_calendars',{}))
        parsed=calendar_registry(data['start'],calendars,mappings,WorkCalendar)
        eligible={row['id'] for row in p.get('project_resources',[])
                  if row.get('kind') in {'crew','equipment'} and row.get('status')=='approved'}
        if set(mappings)-eligible:
            raise ValueError('تقویم منبع به اکیپ یا تجهیز تأییدشده نیاز دارد')
        tasks=p.get('project_schedule_tasks',[])
        for task in tasks:
            selected_calendars(task.get('schedule') or {},parsed,mappings)
        updated={'start':data['start'],'calendar':base}
        if calendars or mappings or 'calendar_version' in previous or 'calendars' in data or 'resource_calendars' in data:
            updated.update(calendars=deepcopy(calendars),resource_calendars=deepcopy(mappings))
            before={key:previous.get(key,{} if key in {'calendars','resource_calendars'} else None) for key in updated}
            updated['calendar_version']=previous.get('calendar_version',1 if previous else 0)+int(updated!=before)
        config['schedule']=updated
        if tasks and all(a.get('schedule') for a in tasks):
            _refresh_schedule_projection(p)
        return config['schedule']
    if op=='schedule_activity':
        _check_schedule_fields(data)
        a=find(p.get('project_schedule_tasks',[]),data.get('id'),'فعالیت')
        d=_duration(data.get('duration'));nb=data.get('not_before')
        if nb is not None:WorkCalendar.valid_date(nb)
        schedule_config=config.get('schedule',{})
        calendar_data={key:data.get(key,(a.get('schedule') or {}).get(key))
                       for key in ('calendar_id','resource_ids') if key in data or key in (a.get('schedule') or {})}
        selected_calendars(calendar_data,schedule_config.get('calendars',{}),schedule_config.get('resource_calendars',{}))
        rels=data.get('relationships')
        if not isinstance(rels,list):raise ValueError('روابط فعالیت باید صریح ثبت شوند')
        ids={x['id'] for x in p['project_schedule_tasks']};seen=set()
        for r in rels:
            if not isinstance(r,dict) or not isinstance(r.get('pred'),str) or r.get('succ')!=a['id'] or r['pred'] not in ids or r['pred']==a['id'] or r.get('type') not in ('FS','SS','FF','SF'):raise ValueError('رابطه فعالیت نامعتبر است')
            integer(r.get('lag'),'وقفه',signed=True)
            if r['pred'] in seen:raise ValueError('پیش‌نیاز تکراری')
            seen.add(r['pred'])
        a['schedule']={'duration':d,'not_before':nb,'relationships':rels,**calendar_data}
        if all(x.get('schedule') for x in p['project_schedule_tasks']):
            _refresh_schedule_projection(p)
        else:
            # A cycle between entered activities is invalid even while other
            # activities are still waiting for a duration or links.
            precedence_order({
                task['id']: [rel['pred'] for rel in (task.get('schedule') or {}).get('relationships', [])]
                for task in p['project_schedule_tasks']
            })
        return a
    if op=='schedule_baseline':
        ref=text(data.get('reference'),'مرجع مبنا');approved=text(data.get('approved_by'),'تأییدکننده مبنا')
        baselines=p.setdefault('schedule_baselines',[])
        if any(x['reference']==ref for x in baselines):raise ValueError('مرجع مبنا تکراری است')
        result=current(p)
        b={'id':f'BASE-{len(baselines)+1}','version':len(baselines)+1,'reference':ref,'approved_by':approved,'created_by':actor,
           'reason':reason,'result':result,'activities':deepcopy(p['project_schedule_tasks'])}
        b['sha256']=digest(b);baselines.append(b);return b
    if op=='schedule_status':
        from core.projects.schedule_status import record_status
        return record_status(p,data,actor,reason)
    raise ValueError('عملیات زمان‌بندی ناشناخته است')
