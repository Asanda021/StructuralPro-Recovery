"""Versioned observations and a retained-logic, whole-day forecast."""
from copy import deepcopy
from datetime import timedelta

from core.projects.controls import basis_stale, digest, evidence, num
from core.commercial.exact_values import exact
from core.projects.precedence_model import driving_graph
from core.projects.schedule_calendars import EffectiveCalendar, Slot, latest_predecessor, shift_event
from core.projects.scheduling import WorkCalendar, _duration, current

DAY = timedelta(days=1)
STATES = {'NOT_STARTED', 'IN_PROGRESS', 'COMPLETED'}
POLICY = 'RETAINED_LOGIC'
FIELDS = {'id', 'state', 'actual_start', 'actual_finish', 'actual_percent',
          'actual_quantity', 'remaining_work', 'remaining_duration', 'source'}


@exact
def _observations(project, schedule, data_date, items):
    if not isinstance(items, list):
        raise ValueError('فهرست مشاهدات باید صریح باشد')
    rows = {task['id']: task for task in project['project_schedule_tasks']}
    result = {}
    planned_start = schedule['calendar_start']
    records=project.get('schedule_status_records',[])
    earliest=WorkCalendar.valid_date(min([planned_start, *(row['schedule_origin'] for row in records)]))
    for item in items:
        if not isinstance(item, dict) or set(item) - FIELDS:
            raise ValueError('فیلد مشاهده زمان‌بندی نامعتبر یا پشتیبانی‌نشده است')
        key, state = item.get('id'), item.get('state')
        if not isinstance(key, str) or key not in rows or key in result or not isinstance(state,str) or state not in STATES:
            raise ValueError('فعالیت یا وضعیت مشاهده نامعتبر است')
        start = WorkCalendar.valid_date(item['actual_start']) if item.get('actual_start') is not None else None
        finish = WorkCalendar.valid_date(item['actual_finish']) if item.get('actual_finish') is not None else None
        duration = schedule['activities'][key]['duration']
        remaining = _duration(item.get('remaining_duration'))
        if any(day is not None and not earliest <= day < data_date for day in (start, finish)):
            raise ValueError('تاریخ مشاهده باید در محدوده سابقه پروژه و پیش از تاریخ وضعیت باشد')
        if state == 'COMPLETED':
            if not start or not finish or finish < start or remaining or (duration == 0 and start != finish):
                raise ValueError('شروع، پایان یا باقیمانده فعالیت تکمیل‌شده ناسازگار است')
        elif state == 'IN_PROGRESS':
            if not start or finish is not None or remaining == 0 or not duration:
                raise ValueError('فعالیت در حال اجرا به شروع و مدت باقی‌مانده مثبت نیاز دارد')
        elif start or finish or remaining != duration:
            raise ValueError('فعالیت شروع‌نشده تاریخ واقعی ندارد و مدت کامل باقی می‌ماند')
        percent = None
        if item.get('actual_percent') is not None:
            percent = num(item['actual_percent'], 'درصد مشاهده‌شده')
            if (percent > 100 or state == 'NOT_STARTED' and percent != 0
                    or state == 'IN_PROGRESS' and percent == 100
                    or state == 'COMPLETED' and percent != 100):
                raise ValueError('درصد مشاهده‌شده با وضعیت فعالیت ناسازگار است')
        quantities = {}
        measurement = rows[key].get('measurement') or {}
        if item.get('actual_quantity') is not None or item.get('remaining_work') is not None:
            if not measurement.get('total') or basis_stale(project, rows[key]):
                raise ValueError('مقدار یا کار باقیمانده به مبنای سنجش معتبر نیاز دارد')
            if measurement['kind']=='explicit':
                evidence(measurement['source'])
            total = num(measurement['total'], 'مقدار مبنا')
            quantity = num(item['actual_quantity'], 'مقدار مشاهده‌شده') if item.get('actual_quantity') is not None else None
            work = num(item['remaining_work'], 'کار باقی‌مانده') if item.get('remaining_work') is not None else None
            if quantity is not None and (quantity > total or (state == 'NOT_STARTED' and quantity != 0)
                                         or (state == 'COMPLETED' and quantity != total)):
                raise ValueError('مقدار مشاهده‌شده با وضعیت یا مقدار مبنا ناسازگار است')
            if work is not None and (work > total or (state == 'COMPLETED' and work != 0)
                                     or (state == 'NOT_STARTED' and work != total)
                                     or (quantity is not None and quantity + work != total)):
                raise ValueError('کار باقی‌مانده با مقدار مبنا ناسازگار است')
            quantities = {'actual_quantity':str(quantity) if quantity is not None else None,
                          'remaining_work':str(work) if work is not None else None,
                          'unit':measurement.get('unit'), 'measurement_digest':digest(measurement)}
        result[key] = {'id': key, 'state': state, 'actual_start': item.get('actual_start'),
                       'actual_finish': item.get('actual_finish'),
                       'remaining_duration': remaining, 'actual_percent': str(percent) if percent is not None else None,
                       'source': evidence(item.get('source')), **quantities}
    return [result[key] for key in sorted(result)]


def _event(row, endpoint, slots, offsets, actual_finishes):
    if endpoint == 'F' and row['id'] in actual_finishes:
        return actual_finishes[row['id']]
    field = 'actual_start' if endpoint == 'S' else 'actual_finish'
    raw = row.get(field)
    if raw is not None:
        return WorkCalendar.valid_date(raw)
    return slots[row['id']].event(endpoint, offsets[row['id']])


def _forecast(schedule, data_date, observations, not_before):
    durations = {key:row['duration'] for key,row in schedule['activities'].items()}
    known = {row['id']:row for row in observations}
    for key in schedule['order']:
        known.setdefault(key, {'id':key,'state':'NOT_STARTED','remaining_duration':durations[key],
                               'actual_start':None,'actual_finish':None})
    start = schedule['calendar_start']
    project_calendar = WorkCalendar(schedule['calendar'], start)
    shared = schedule['offset_unit']=='PROJECT_WORKDAY'
    actual_finishes = {}
    for key,row in known.items():
        if row.get('actual_finish') is None:
            continue
        day=WorkCalendar.valid_date(row['actual_finish'])
        if durations[key]:
            day += DAY
            if shared:
                day=project_calendar.at(project_calendar.index_day(day))
        actual_finishes[key]=day
    definitions = {'PROJECT':project_calendar, **{key:WorkCalendar(value,start)
                   for key,value in schedule.get('calendars',{}).items()}}
    cal_cache = {}
    slots = {}
    for key, row in known.items():
        if row['state'] == 'COMPLETED':
            continue
        ids = tuple(schedule['activities'][key].get('calendar_ids',['PROJECT']))
        if ids not in cal_cache:
            cal_cache[ids] = EffectiveCalendar([definitions[cid] for cid in ids],
                boundary_on_workday=shared)
        slots[key] = Slot(row['remaining_duration'],cal_cache[ids])
    incoming = {key:[] for key in known}
    for rel in schedule['relationships']:
        normalized = {key:rel[key] for key in ('pred','succ','type')}
        normalized['lag'] = int(num(rel['lag'],'وقفه کاری',signed=True))
        incoming[rel['succ']].append(normalized)
    early = {}
    roots = {}
    tight = []
    future_edges = {key:[] for key in slots}
    out_of_sequence = []
    for key in schedule['order']:
        observed = known[key]
        slot = slots.get(key)
        lower = None
        if slot:
            planned = not_before[key]
            day = max(data_date, WorkCalendar.valid_date(planned)) if planned else data_date
            lower = max(0, slot.lower('S',day))
        requirements = []
        for link in incoming[key]:
            pred, kind = link['pred'], link['type']
            upstream = known[pred]
            limit = shift_event(_event(upstream,kind[0],slots,early,actual_finishes),link['lag'],project_calendar)
            actual = observed.get('actual_start' if kind[1]=='S' else 'actual_finish')
            if actual is not None:
                reported = _event(observed,kind[1],slots,early,actual_finishes)
                if reported < limit:
                    out_of_sequence.append({**link,'reported_event':reported.isoformat(),'required_event':limit.isoformat()})
            if slot is None:
                continue
            # An already observed start stays fixed. Retained logic bounds the
            # future resumption of its remaining work at the same requirement.
            offset = slot.lower(kind[1],limit)
            requirements.append((offset,link))
            if pred in slots and not upstream.get('actual_start' if kind[0]=='S' else 'actual_finish'):
                future_edges[pred].append(link)
        if slot is not None:
            early[key] = max([lower, *(offset for offset,_ in requirements)])
            if early[key] == lower:
                roots[key] = 'DATA_DATE' if not planned or WorkCalendar.valid_date(planned) <= data_date else 'NOT_BEFORE'
            for offset,link in requirements:
                if offset != early[key]:
                    continue
                upstream = known[link['pred']]
                if link['pred'] in slots and not upstream.get('actual_start' if link['type'][0]=='S' else 'actual_finish'):
                    tight.append(link)
                else:
                    roots.setdefault(key,'OBSERVED_PREDECESSOR')

    finishes = {key:_event(row,'F',slots,early,actual_finishes) for key,row in known.items()}
    end = max(finishes.values())
    latest, free = {}, {}
    for key in reversed(schedule['order']):
        if key not in slots:
            continue
        slot = slots[key]
        late = loose = slot.upper_finish(end)
        for link in future_edges[key]:
            succ = link['succ']
            target = slots[succ]
            late = latest_predecessor(target.event(link['type'][1],latest[succ]),early[key],late,slot,link,project_calendar)
            loose = latest_predecessor(target.event(link['type'][1],early[succ]),early[key],loose,slot,link,project_calendar)
        latest[key],free[key] = late,loose

    activities = {}
    for key in schedule['order']:
        observed = known[key]
        slot = slots.get(key)
        resume = slot.start(early[key]).isoformat() if slot else None
        last_work = (slot.calendar.at(early[key]+slot.duration-1) if slot and slot.duration
                     else WorkCalendar.valid_date(observed['actual_finish']) if not slot
                     else finishes[key])
        activities[key] = {
            **deepcopy(observed), 'start': observed.get('actual_start') or resume, 'resume':resume,
            'finish':last_work.isoformat(),'milestone':durations[key]==0,
            'finish_boundary':finishes[key].isoformat(),
            'forecast_finish':finishes[key].isoformat() if slot else None,
            'late_resume':slot.start(latest[key]).isoformat() if slot else None,
            'total_float':latest[key]-early[key] if slot else None,
            'free_float':free[key]-early[key] if slot else None,
            'float_unit':'ACTIVITY_WORKDAY' if slot else None,
        }
    return {'data_date':data_date.isoformat(),'finish_boundary':end.isoformat(),'activities':activities,
            'out_of_sequence':out_of_sequence,'policy':POLICY,'status':'PROPOSED_UNAPPROVED',
            'offset_unit':schedule['offset_unit'],
            'driving':driving_graph([key for key in schedule['order'] if key in slots],tight,
                                     [key for key in slots if finishes[key]==end],roots)}


def _check_basis(project, record):
    _verify_record(record)
    schedule = current(project)
    if digest(schedule) != record['schedule_digest']:
        raise ValueError('برنامه تغییر کرده است. رکورد تاریخ وضعیت باید دوباره بازبینی شود')
    checked = _observations(project,schedule,WorkCalendar.valid_date(record['data_date']),[
        {key:value for key,value in row.items() if key in FIELDS} for row in record['observations']])
    if checked != record['observations']:
        raise ValueError('مبنای مشاهده پس از ثبت تغییر کرده است')
    return schedule


def _verify_record(record):
    if record.get('schema') != 1:
        raise ValueError('نسخه رکورد تاریخ وضعیت پشتیبانی نمی‌شود')
    payload = {key:value for key,value in record.items() if key!='sha256'}
    if digest(payload) != record.get('sha256'):
        raise ValueError('تمامیت رکورد تاریخ وضعیت معتبر نیست')


def forecast(project, *, version=None):
    records = project.get('schedule_status_records') or []
    record = records[-1] if records and version is None else next(
        (row for row in records if row['version']==version),None)
    if not record:
        raise ValueError('رکورد معتبر تاریخ وضعیت ثبت نشده است')
    schedule = _check_basis(project,record)
    bounds = {task['id']:task['schedule'].get('not_before') for task in project['project_schedule_tasks']}
    result = _forecast(schedule,WorkCalendar.valid_date(record['data_date']),record['observations'],bounds)
    if digest(result) != record['forecast_digest']:
        raise ValueError('بازمحاسبه پیش‌بینی با سابقه ثبت‌شده تطبیق ندارد')
    return {**result,'version':record['version'],'status_sha256':record['sha256'],
            'baseline_finish':record['baseline_finish'],'baseline_sha256':record['baseline_sha256'],
            'baseline_delta_days':record['baseline_delta_days']}


def _civil_finish(result):
    return max(WorkCalendar.valid_date(row['finish']) + (timedelta(0) if row['milestone'] else DAY)
               for row in result['activities'].values())


def record_status(project, data, actor, reason):
    allowed = {'data_date','policy','unreported','observations','corrects_version'}
    if set(data)-allowed or data.get('policy') != POLICY or data.get('unreported') != 'NOT_STARTED':
        raise ValueError('سیاست RETAINED_LOGIC و فرض صریح NOT_STARTED برای موارد گزارش‌نشده لازم است')
    schedule = current(project)
    day = WorkCalendar.valid_date(data.get('data_date'))
    if day < WorkCalendar.valid_date(schedule['calendar_start']):
        raise ValueError('تاریخ وضعیت پیش از شروع پروژه است')
    records = project.setdefault('schedule_status_records',[])
    observations = _observations(project,schedule,day,data.get('observations'))
    correction=data.get('corrects_version')
    if records:
        last=records[-1]
        _verify_record(last)
        if correction is not None:
            if type(correction) is not int or correction!=last['version'] or day.isoformat()!=last['data_date']:
                raise ValueError('اصلاحیه باید به آخرین نسخه همین تاریخ وضعیت ارجاع دهد')
        elif day.isoformat() <= last['data_date']:
            raise ValueError('تاریخ وضعیت باید جلو برود یا با مرجع صریح اصلاح شود')
        else:
            new={row['id']:row for row in observations}
            measurements={task['id']:task.get('measurement',{}) for task in project['project_schedule_tasks']}
            for old in last['observations']:
                if old['actual_start'] is None:
                    continue
                row=new.get(old['id'])
                if (row is None or row['actual_start']!=old['actual_start']
                        or old['actual_finish'] is not None and row['actual_finish']!=old['actual_finish']):
                    raise ValueError('مشاهده پیشین نباید حذف یا به‌صورت ضمنی اصلاح شود')
                if not old.get('measurement_digest') or old['measurement_digest']==digest(measurements[old['id']]):
                    for field in ('actual_quantity','actual_percent'):
                        previous=old.get(field)
                        observed=row.get(field)
                        if previous is not None and (observed is None or num(observed,field)<num(previous,field)):
                            raise ValueError('کارکرد تجمعی در مبنای یکسان بدون اصلاحیه نباید کم یا حذف شود')
    elif correction is not None:
        raise ValueError('رکوردی برای اصلاح وجود ندارد')
    bounds = {task['id']:task['schedule'].get('not_before') for task in project['project_schedule_tasks']}
    result = _forecast(schedule,day,observations,bounds)
    baseline = (project.get('schedule_baselines') or [None])[-1]
    if baseline and digest({key:value for key,value in baseline.items() if key!='sha256'}) != baseline.get('sha256'):
        raise ValueError('تمامیت Baseline معتبر نیست')
    base_finish = baseline['result']['finish_boundary'] if baseline else None
    delta = None
    if baseline:
        delta = (_civil_finish(result)-_civil_finish(baseline['result'])).days
    record = {'schema':1,'version':len(records)+1,'data_date':day.isoformat(),'policy':POLICY,
              'schedule_origin':schedule['calendar_start'],
              'unreported':'NOT_STARTED','actor':actor,'reason':reason,'schedule_digest':digest(schedule),
              'observations':observations,'forecast_finish':result['finish_boundary'],'forecast_digest':digest(result),
              'baseline_sha256':baseline['sha256'] if baseline else None,'baseline_finish':base_finish,'baseline_delta_days':delta}
    if correction is not None:
        record['corrects_version']=correction
    record['sha256'] = digest(record)
    records.append(record)
    return record
