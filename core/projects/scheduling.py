"""CPM in explicit integer workday boundaries; display finish is last workday.

A task occupies [ES, EF). A zero-duration milestone is at ES. FS/SS/FF/SF
are lower bounds on successor starts. Lag/lead is signed workdays in the
single explicitly chosen project calendar; no implicit statutory holidays.
"""
from copy import deepcopy
from datetime import date,timedelta
import heapq
from core.projects.controls import integer,text,find,digest


class WorkCalendar:
    def __init__(self,config,start):
        self.start=self.valid_date(start)
        if not isinstance(config,dict):raise ValueError('تقویم کاری صریح لازم است')
        days=config.get('weekdays')
        if not isinstance(days,list) or not days or len(set(days))!=len(days):raise ValueError('روزهای کاری تقویم نامعتبر است')
        self.days={integer(x,'روز هفته') for x in days}
        if not self.days<=set(range(7)):raise ValueError('روز هفته باید بین صفر و شش باشد')
        holidays=config.get('holidays')
        if not isinstance(holidays,list):raise ValueError('تعطیلات تقویم باید صریح باشند')
        self.holidays={self.valid_date(x) for x in holidays}
        self.dates=[];self.cursor=self.start
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
            if self.cursor.weekday() in self.days and self.cursor not in self.holidays:self.dates.append(self.cursor)
            try:self.cursor+=timedelta(days=1)
            except OverflowError as e:raise ValueError('سرریز تاریخ برنامه') from e
        return self.dates[index]
    def index(self,value):
        d=self.valid_date(value)
        if d<self.start:return 0
        i=0
        while self.at(i)<d:i+=1
        return i


def cpm(tasks,relationships,*,start,calendar):
    if not tasks:raise ValueError('برای محاسبه برنامه فعالیت لازم است')
    cal=WorkCalendar(calendar,start);by={};duration={}
    for t in tasks:
        id=text(t.get('id'),'شناسه فعالیت')
        if id in by:raise ValueError('شناسه فعالیت تکراری است')
        d=integer(t.get('duration'),'مدت کاری')
        if d>100000:raise ValueError('مدت بیش از افق پشتیبانی‌شده است')
        by[id]=t;duration[id]=d
    adj={k:[] for k in by};incoming={k:[] for k in by};degree={k:0 for k in by};seen=set()
    for r in relationships:
        a,b,kind=r.get('pred'),r.get('succ'),r.get('type')
        if a not in by or b not in by or a==b or kind not in {'FS','SS','FF','SF'}:raise ValueError('رابطه پیش‌نیازی نامعتبر است')
        if (a,b) in seen:raise ValueError('رابطه تکراری یا متعارض است')
        seen.add((a,b));lag=integer(r.get('lag'),'وقفه کاری',signed=True)
        offset=(duration[a] if kind in {'FS','FF'} else 0)-(duration[b] if kind in {'FF','SF'} else 0)+lag
        adj[a].append((b,offset));incoming[b].append((a,offset));degree[b]+=1
    ready=[k for k in by if not degree[k]];heapq.heapify(ready);order=[]
    while ready:
        a=heapq.heappop(ready);order.append(a)
        for b,_ in adj[a]:
            degree[b]-=1
            if not degree[b]:heapq.heappush(ready,b)
    if len(order)!=len(by):raise ValueError('حلقه در شبکه فعالیت‌ها مجاز نیست')
    es={k:cal.index(t['not_before']) if t.get('not_before') else 0 for k,t in by.items()}
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
    return {'activities':rows,'order':order,'duration':end,'start':cal.at(0).isoformat(),
            'finish_boundary':cal.at(end).isoformat(),'critical_ids':[k for k in order if rows[k]['critical']],
            'relationships':deepcopy(relationships),'calendar':deepcopy(calendar),'calendar_start':start,
            'warnings':[{'id':k,'message':'فعالیت ریشه؛ بدون پیش‌نیاز'} for k in order if not incoming[k]]}


def current(project):
    config=project.get('project_control_config',{}).get('schedule')
    if not config:raise ValueError('تاریخ شروع و تقویم پروژه ثبت نشده است')
    tasks=[];rels=[]
    for a in project.get('project_schedule_tasks',[]):
        if not a.get('schedule'):raise ValueError('مدت و روابط همه فعالیت‌ها باید صریح ثبت شوند')
        tasks.append({'id':a['id'],**a['schedule']});rels.extend(a['schedule']['relationships'])
    result=cpm(tasks,rels,start=config['start'],calendar=config['calendar'])
    for a in project.get('project_schedule_tasks',[]):
        result['activities'][a['id']].update(title=a['title'],wbs_id=a.get('wbs_id'))
    return result


def schedule_command(p,op,data,actor,reason):
    config=p['project_control_config']
    if op=='schedule_calendar':
        WorkCalendar(data.get('calendar'),data.get('start')).at(0)
        config['schedule']={'start':data['start'],'calendar':deepcopy(data['calendar'])}
        if p.get('project_schedule_tasks') and all(a.get('schedule') for a in p['project_schedule_tasks']):
            result=current(p)
            for a in p['project_schedule_tasks']:
                a.update(planned_start=result['activities'][a['id']]['start'],planned_end=result['activities'][a['id']]['finish'])
        return config['schedule']
    if op=='schedule_activity':
        a=find(p.get('project_schedule_tasks',[]),data.get('id'),'فعالیت')
        d=integer(data.get('duration'),'مدت');nb=data.get('not_before')
        if nb is not None:WorkCalendar.valid_date(nb)
        rels=data.get('relationships')
        if not isinstance(rels,list):raise ValueError('روابط فعالیت باید صریح ثبت شوند')
        ids={x['id'] for x in p['project_schedule_tasks']};seen=set()
        for r in rels:
            if r.get('succ')!=a['id'] or r.get('pred') not in ids or r['pred']==a['id'] or r.get('type') not in {'FS','SS','FF','SF'}:raise ValueError('رابطه فعالیت نامعتبر است')
            integer(r.get('lag'),'وقفه',signed=True)
            if r['pred'] in seen:raise ValueError('پیش‌نیاز تکراری')
            seen.add(r['pred'])
        a['schedule']={'duration':d,'not_before':nb,'relationships':rels}
        if all(x.get('schedule') for x in p['project_schedule_tasks']):
            r=current(p)
            for t in p['project_schedule_tasks']:
                t.update(planned_start=r['activities'][t['id']]['start'],planned_end=r['activities'][t['id']]['finish'],
                         predecessor_ids=[x['pred'] for x in t['schedule']['relationships']])
        return a
    if op=='schedule_baseline':
        ref=text(data.get('reference'),'مرجع مبنا');approved=text(data.get('approved_by'),'تأییدکننده مبنا')
        baselines=p.setdefault('schedule_baselines',[])
        if any(x['reference']==ref for x in baselines):raise ValueError('مرجع مبنا تکراری است')
        result=current(p)
        b={'id':f'BASE-{len(baselines)+1}','version':len(baselines)+1,'reference':ref,'approved_by':approved,'created_by':actor,
           'reason':reason,'result':result,'activities':deepcopy(p['project_schedule_tasks'])}
        b['sha256']=digest(b);baselines.append(b);return b
    raise ValueError('عملیات زمان‌بندی ناشناخته است')
