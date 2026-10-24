"""Evidence-backed office records. Actor labels are local attribution only."""
from copy import deepcopy
from core.projects.controls import text, num, integer, evidence, find, digest, basis_stale
from core.projects.scheduling import WorkCalendar
from core.commercial.exact_values import exact

KEYS = ('project_daily_reports', 'project_meetings', 'site_obstacles',
        'site_correspondence', 'site_document_packages', 'site_action_events')
_COLLECTIONS = {'daily':'project_daily_reports', 'meeting':'project_meetings',
                'correspondence':'site_correspondence', 'package':'site_document_packages'}
OPS = {f'{kind}_{action}' for kind in _COLLECTIONS for action in ('create','review','approve','issue','amend')} | {'daily_transfer','obstacle_create','obstacle_resolve','action_resolve'}
_PACKAGE_SOURCES = set(_COLLECTIONS.values()) - {'site_document_packages'} | {'progress_documents','progress_reports','statement_periods','manual_formula_amendments','beam_amendments'}


def _date(value):
    return WorkCalendar.valid_date(value).isoformat()


def _seal(record):
    record['content_digest'] = digest({k:v for k,v in record.items() if k not in {'content_digest','status','reviewed_by','approved_by','issued_by'}})


def _verify(record):
    if record.get('content_digest') != digest({k:v for k,v in record.items() if k not in {'content_digest','status','reviewed_by','approved_by','issued_by'}}):
        raise ValueError('محتوای سند تغییر کرده است')
    evidence(record['source']) if 'source' in record else None
    for proof in record.get('attachments',[]):evidence(proof)
    for action in record.get('action_items',[]):evidence(action['source'])


def _activity(p,id):
    return find(p.get('project_schedule_tasks',[]),id,'فعالیت')['id']


def _refs(p,key,values):
    if not isinstance(values,list) or len(set(values)) != len(values):raise ValueError('فهرست منابع صریح لازم است')
    return [find(p.get(key,[]),id,'منبع')['id'] for id in values]


def _event(p,kind,target,data,actor,reason):
    events=p.setdefault('site_action_events',[])
    row={'id':f'OFFICE-EVENT-{len(events)+1}','project_id':p['id'],'kind':kind,'target_id':target,
         'date':_date(data.get('date')),'resolution':text(data.get('resolution'),'شرح اقدام'),
         'source':evidence(data.get('source')),'actor':actor,'reason':reason}
    events.append(row);return row


def _package_documents(p,sources):
    if not isinstance(sources,list) or not sources:raise ValueError('منابع بسته الزامی است')
    documents=[];seen=set()
    for item in sources:
        key=item.get('collection');id=item.get('id')
        if key not in _PACKAGE_SOURCES or (key,id) in seen:raise ValueError('مجموعه منبع نامعتبر یا تکراری است')
        candidates=p.get(key,[])
        if key in {'manual_formula_amendments','beam_amendments'}:candidates=list(candidates.values())
        if key=='statement_periods':
            candidates=[{**r,'id':str(r['number'])} for r in candidates]
        row=find(candidates,id,'سند منبع');seen.add((key,id))
        if key=='statement_periods':row={k:v for k,v in row.items() if k!='id'}
        if row.get('project_id',p['id'])!=p['id']:raise ValueError('سند متعلق به پروژه دیگری است')
        # Reports/statements without an explicit official status are intentionally blocked.
        if key=='statement_periods':
            envelopes=[d for d in p.get('statement_workflow',[]) if d.get('status')=='ISSUED' and d.get('period')==row]
            if len(envelopes)!=1:raise ValueError('صورت‌وضعیت فاقد گردش صدور معتبر است')
        elif key=='beam_amendments':
            from core.takeoff.manual_formula_amendments import beam_current, beam_effective_takeoffs
            if row.get('status')!='applied' or p.get('beam_amendment_applied',{}).get(row.get('beam_key'))!=id:raise ValueError('اصلاحیه تخصصی اعمال‌شده معتبر نیست')
            beam_current(p,row['beam_key']);beam_effective_takeoffs(p,p.get('takeoffs',[]))
        elif key=='manual_formula_amendments':
            from core.takeoff.manual_formula_register import verified
            from core.takeoff.manual_formula_amendments import effective
            if row.get('status')!='applied' or p.get('manual_formula_applied',{}).get(row.get('row_id'))!=id:raise ValueError('اصلاحیه اعمال‌شده معتبر نیست')
            verified(p);effective(p,p.get('manual_formula_register',{}))
            canonical=[r for r in p.get('takeoffs',[]) if r.get('source_id')==row.get('source_id')]
            if not canonical:raise ValueError('منبع اصلی اصلاحیه موجود نیست')
        elif key=='progress_reports':
            if row.get('sha256')!=digest({k:v for k,v in row.items() if k!='sha256'}):raise ValueError('هش گزارش پیشرفت نامعتبر است')
            for activity in row.get('activities',[]):
                doc=find(p.get('progress_documents',[]),activity.get('source_document'),'مشاهده منبع')
                if doc.get('status')!='approved' or doc.get('activity_id')!=activity.get('id'):raise ValueError('مشاهده منبع تأیید نشده است')
                evidence(doc.get('source'))
                basis=find(p.get('project_schedule_tasks',[]),doc['activity_id'],'فعالیت')
                if basis_stale(p,basis) or doc.get('basis_digest')!=digest(basis.get('measurement',{})):raise ValueError('مبنای مشاهده گزارش تغییر کرده است')
            if not row.get('activities'):raise ValueError('گزارش پیشرفت فاقد منابع است')
        elif row.get('status') not in {'approved','issued'}:raise ValueError('منبع باید تأیید یا صادر شده باشد')
        if 'content_digest' in row:_verify(row)
        if item.get('sha256')!=digest(row) or item.get('version')!=row.get('version',1):raise ValueError('نسخه یا هش منبع ناسازگار است')
        if row.get('source'):evidence(row['source'])
        if key=='progress_documents':
            activity=find(p.get('project_schedule_tasks',[]),row.get('activity_id'),'فعالیت')
            if basis_stale(p,activity) or row.get('basis_digest')!=digest(activity.get('measurement',{})):raise ValueError('مبنای مقدار منبع تغییر کرده است')
        documents.append({'collection':key,'id':id,'version':row.get('version',1),'sha256':digest(row),'record':deepcopy(row)})
    return documents


@exact
def dispatch(p,op,data,actor,reason):
    actor=text(actor,'عامل');reason=text(reason,'دلیل')
    if op not in OPS:raise ValueError('عملیات دفتر فنی ناشناخته است')
    if data.get('project_id',p['id']) != p['id']:raise ValueError('پروژه ناسازگار است')
    if op=='daily_transfer':
        row=find(p.get('project_daily_reports',[]),data.get('id'),'گزارش روزانه');_verify(row)
        if row['status'] not in {'approved','issued'}:raise ValueError('گزارش تأیید نشده است')
        if data.get('quantity_semantics')!='cumulative':raise ValueError('مقدار تجمعی باید صریح باشد')
        if any(e['kind']=='daily_transfer' and e['target_id']==row['id'] for e in p.get('site_action_events',[])):raise ValueError('این گزارش قبلاً منتقل شده است')
        activity=find(p.get('project_schedule_tasks',[]),row['activity_id'],'فعالیت')
        if basis_stale(p,activity) or row.get('basis_digest')!=digest(activity.get('measurement',{})):raise ValueError('مبنای گزارش روزانه تغییر کرده است')
        if any(r.get('supersedes')==row['id'] for r in p.get('project_daily_reports',[])):raise ValueError('گزارش دارای نسخه اصلاحی است')
        events=[e for e in p.get('site_action_events',[]) if e['kind']=='daily_transfer']
        supersedes=None
        ancestor=row
        visited=set()
        prior_event=[]
        while ancestor.get('supersedes'):
            if ancestor['id'] in visited:raise ValueError('زنجیره اصلاحیه نامعتبر است')
            visited.add(ancestor['id'])
            ancestor=find(p.get('project_daily_reports',[]),ancestor['supersedes'],'گزارش اصلی')
            if ancestor['date']!=row['date'] or ancestor['activity_id']!=row['activity_id']:raise ValueError('اصلاحیه باید همان فعالیت و تاریخ را حفظ کند')
            prior_event=[e for e in events if e['target_id']==ancestor['id']]
            if prior_event:break
        if prior_event:
            if len(prior_event)!=1:raise ValueError('انتقال اصلی تکراری است')
            supersedes=prior_event[0]['progress_document_id']
            old=find(p.get('progress_documents',[]),supersedes,'مشاهده اصلی')
            if old['status']!='approved':raise ValueError('مشاهده انتقال اصلی پیش‌نویس است؛ ابتدا بازبینی و تأیید شود')
            if data.get('supersedes')!=supersedes:raise ValueError('شناسه مشاهده اصلاح‌شونده تأییدشده لازم است')
        elif data.get('supersedes'):raise ValueError('هیچ مشاهده انتقال اصلی برای اصلاح وجود ندارد')
        from core.projects.physical_progress import progress_command, _active
        previous=sorted((d for d in _active(p,'9999-12-31') if d['activity_id']==row['activity_id'] and d['date']<row['date']),key=lambda d:d['date'])
        before=num(data.get('previous_cumulative_quantity'),'مقدار تجمعی پیشین')
        if previous:
            prior=previous[-1]
            if data.get('initial_observation') or data.get('previous_progress_id')!=prior['id'] or before!=num(prior['quantity'],'مقدار پیشین'):raise ValueError('مشاهده پیشین ناسازگار است')
            evidence(prior['source'])
            if prior.get('basis_digest')!=row['basis_digest']:raise ValueError('مبنای مشاهده پیشین تغییر کرده است')
        elif data.get('initial_observation') is not True or before!=0 or data.get('previous_progress_id'):
            raise ValueError('نخستین مشاهده نیازمند اعلام صریح مبنای صفر است')
        cumulative=num(data.get('cumulative_quantity'),'مقدار تجمعی')
        if cumulative!=before+num(row['quantity'],'مقدار گزارش'):raise ValueError('مقدار تجمعی با گزارش امضاشده تطبیق ندارد')
        result=progress_command(p,'progress_create',{'activity_id':row['activity_id'],'date':row['date'],
            'reference':data.get('reference'),'cumulative_quantity':str(cumulative),'source':data.get('source'),'supersedes':supersedes},actor,reason)
        result['daily_report_id']=row['id']
        p.setdefault('site_action_events',[]).append({'id':f"OFFICE-EVENT-{len(p.get('site_action_events',[]))+1}",'project_id':p['id'],'kind':'daily_transfer','target_id':row['id'],'activity_id':row['activity_id'],'progress_document_id':result['id'],'actor':actor,'reason':reason,'source':deepcopy(result['source']),'quantity_semantics':'cumulative','previous_cumulative_quantity':str(before),'previous_progress_id':data.get('previous_progress_id'),'initial_observation':data.get('initial_observation') is True,'supersedes':supersedes})
        return result
    if op in {'obstacle_resolve','action_resolve'}:
        key='site_obstacles' if op=='obstacle_resolve' else 'project_meetings'
        rows=p.get(key,[]) if key=='site_obstacles' else [a for m in p.get(key,[]) for a in m.get('action_items',[])]
        row=find(rows,data.get('id'),'پیگیری')
        if any(e['kind']==op and e['target_id']==row['id'] for e in p.get('site_action_events',[])):raise ValueError('پیگیری قبلاً بسته شده است')
        if _date(data.get('date'))<row.get('date','0001-01-01'):raise ValueError('تاریخ اقدام پیش از ثبت است')
        return _event(p,op,row['id'],data,actor,reason)
    if op=='obstacle_create':
        rows=p.setdefault('site_obstacles',[])
        row={'id':f'OBSTACLE-{len(rows)+1}','project_id':p['id'],'title':text(data.get('title'),'عنوان'),'owner':text(data.get('owner'),'مسئول'),
             'date':_date(data.get('date')),'due_date':_date(data.get('due_date')),'location':text(data.get('location'),'محل'),
             'activity_id':_activity(p,data.get('activity_id')),'source':evidence(data.get('source')),'status':'open','created_by':actor,'reason':reason}
        if row['due_date']<row['date']:raise ValueError('سررسید پیش از ثبت است')
        rows.append(row);return row
    kind,action=op.rsplit('_',1);key=_COLLECTIONS[kind];rows=p.setdefault(key,[])
    if action in {'review','approve','issue'}:
        row=find(rows,data.get('id'),'سند');_verify(row)
        expected={'review':'draft','approve':'reviewed','issue':'approved'}[action]
        if row['status']!=expected:raise ValueError('وضعیت سند نامعتبر است')
        if action in {'review','approve'} and actor in {row['created_by'],row.get('reviewed_by')}:raise ValueError('بازبینی و تأیید مستقل لازم است')
        if kind=='package':_package_documents(p,row['sources'])
        row['status']={'review':'reviewed','approve':'approved','issue':'issued'}[action]
        row[{'review':'reviewed_by','approve':'approved_by','issue':'issued_by'}[action]]=actor
        return row
    parent=None
    if action=='amend':
        parent=find(rows,data.get('id'),'سند اصلی');_verify(parent)
        if parent['status']!='issued':raise ValueError('اصلاحیه تنها برای سند صادرشده مجاز است')
        if any(r.get('supersedes')==parent['id'] for r in rows):raise ValueError('نسخه اصلاحی موجود است')
    ref=text(data.get('reference'),'شماره سند')
    if any(r.get('reference')==ref for r in rows):raise ValueError('شماره سند تکراری است')
    row={'id':f'{kind.upper()}-{len(rows)+1}','project_id':p['id'],'reference':ref,'date':_date(data.get('date')),
         'version':parent['version']+1 if parent else 1,'supersedes':parent['id'] if parent else None,
         'status':'draft','created_by':actor,'reason':reason}
    if kind=='package':
        row.update(title=text(data.get('title'),'عنوان'),template=text(data.get('template'),'قالب'),template_version=text(data.get('template_version'),'نسخه قالب'),sources=deepcopy(data.get('sources')),documents=_package_documents(p,data.get('sources')),drawing_status='waiting_phase7')
    else:
        attachments=data.get('attachments')
        if not isinstance(attachments,list):raise ValueError('فهرست پیوست صریح لازم است')
        row.update(source=evidence(data.get('source')),attachments=[evidence(x) for x in attachments])
    if kind=='daily':
        activity=find(p.get('project_schedule_tasks',[]),data.get('activity_id'),'فعالیت');unit=text(data.get('unit'),'واحد')
        if unit!=activity.get('unit'):raise ValueError('واحد فعالیت ناسازگار است')
        row.update(basis_digest=digest(activity.get('measurement',{})),activity_id=activity['id'],unit=unit,quantity=str(num(data.get('quantity'),'مقدار')),
                   human_count=integer(data.get('human_count'),'تعداد نیروی انسانی'),location=text(data.get('location'),'محل'),
                   crew_ids=_refs(p,'project_resources',data.get('crew_ids')),equipment_ids=_refs(p,'project_resources',data.get('equipment_ids')),
                   material_ids=_refs(p,'project_materials',data.get('material_ids')),technical_notes=text(data.get('technical_notes'),'یادداشت فنی'),summary=text(data.get('summary'),'خلاصه'))
        row.update(workforce=row['human_count'],weather=data.get('weather',''),notes=row['technical_notes'])
    if kind=='meeting':
        participants=data.get('participants');actions=data.get('actions')
        if not isinstance(participants,list) or not participants or not isinstance(actions,list):raise ValueError('حاضران و اقدامات صریح لازم است')
        items=[]
        for index,a in enumerate(actions):
            items.append({'id':f"{row['id']}-ACTION-{index+1}",'date':row['date'],'title':text(a.get('title'),'اقدام'),'owner':text(a.get('owner'),'مسئول'),'due_date':_date(a.get('due_date')),'activity_id':_activity(p,a.get('activity_id')),'source':evidence(a.get('source')),'status':'open'})
            if items[-1]['due_date']<row['date']:raise ValueError('سررسید اقدام پیش از جلسه است')
        row.update(title=text(data.get('title'),'عنوان'),participants=', '.join(text(x,'حاضر') for x in participants),participant_names=participants[:],decisions=text(data.get('decisions'),'تصمیم‌ها'),actions='; '.join(a['title'] for a in items),action_items=items,follow_up_date=min((a['due_date'] for a in items),default=''))
    if kind=='correspondence':
        if data.get('kind') not in {'rfi','material_approval','drawing_review','instruction','letter'}:raise ValueError('نوع مکاتبه نامعتبر است')
        row.update(kind=data['kind'],title=text(data.get('title'),'عنوان'),recipient=text(data.get('recipient'),'مخاطب'),technical_notes=text(data.get('technical_notes'),'شرح'),delivery_status='not_sent')
    _seal(row);rows.append(row);return row


def package_candidates(p):
    """Only validated current source records, with copyable package references."""
    candidates=[]
    for key in sorted(_PACKAGE_SOURCES):
        rows=p.get(key,[])
        if isinstance(rows,dict):rows=list(rows.values())
        for row in rows:
            id=str(row['number']) if key=='statement_periods' else row.get('id')
            if id is None:continue
            item={'collection':key,'id':id,'version':row.get('version',1),'sha256':digest(row)}
            try:_package_documents(p,[item])
            except (ValueError,KeyError,TypeError):continue
            candidates.append(item)
    return candidates

def snapshot(p,*,as_of):
    day=_date(as_of);events=p.get('site_action_events',[])
    resolved={e['target_id'] for e in events if e['kind'] in {'obstacle_resolve','action_resolve'} and e['date']<=day}
    def rows(key):return deepcopy([r for r in p.get(key,[]) if r.get('date','9999-12-31')<=day])
    obstacles=rows('site_obstacles')
    for r in obstacles:r['status']='resolved' if r['id'] in resolved else 'open'
    meetings=rows('project_meetings');actions=[a for m in meetings for a in m.get('action_items',[])]
    for a in actions:a['status']='resolved' if a['id'] in resolved else 'open'
    packages=rows('site_document_packages')
    for package in packages:
        try:
            _verify(package);_package_documents(p,package['sources'])
            package.update(current=True,source_error=None)
        except (ValueError,KeyError,TypeError) as error:
            package.update(current=False,source_error=str(error))
    return {'project_id':p['id'],'date':day,'daily_reports':rows('project_daily_reports'),'meetings':meetings,'obstacles':obstacles,
            'correspondence':rows('site_correspondence'),'packages':packages,'overdue_actions':[a for a in actions if a['status']=='open' and a['due_date']<day],
            'overdue_obstacles':[a for a in obstacles if a['status']=='open' and a['due_date']<day],
            'packaged_documents':[{**deepcopy(d),'package_id':pkg['id'],'current':pkg['current'],'source_error':pkg['source_error']} for pkg in packages for d in pkg['documents']]}
