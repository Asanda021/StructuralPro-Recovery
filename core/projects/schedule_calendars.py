"""Calendar-day CPM for explicit, whole-day activity and resource calendars."""
from copy import deepcopy
from bisect import bisect_left
from datetime import date, timedelta

from core.projects.controls import digest
from core.projects.precedence_model import driving_graph

DAY = timedelta(days=1)


class EffectiveCalendar:
    def __init__(self, components, *, boundary_on_workday=False):
        self.components = tuple(components)
        self.boundary_on_workday = boundary_on_workday
        self.start = components[0].start
        self.dates = []
        self.cursor = self.start
        weekdays = set.intersection(*(cal.days for cal in components))
        exceptions = set.union(*(cal.exceptions for cal in components))
        self.finite = not weekdays
        if self.finite:
            self.dates = sorted(day for day in exceptions if day >= self.start and self.is_open(day))
            if not self.dates:
                raise ValueError('تقویم‌های فعالیت و منابع روز کاری مشترک ندارند')

    def is_open(self, day):
        return all(cal.is_open(day) for cal in self.components)

    def at(self, index):
        if not 0 <= index <= 100000:
            raise ValueError('افق تقویم مؤثر خارج از محدوده است')
        if self.finite and index >= len(self.dates):
            raise ValueError('تقویم مؤثر روز کاری کافی ندارد')
        while len(self.dates) <= index:
            if (self.cursor - self.start).days > 365000:
                raise ValueError('تقویم مؤثر روز کاری کافی ندارد')
            if self.is_open(self.cursor):
                self.dates.append(self.cursor)
                if len(self.dates)>index and self.cursor==date.max:
                    return self.dates[index]
            try:
                self.cursor += DAY
            except OverflowError as exc:
                raise ValueError('سرریز تاریخ تقویم مؤثر') from exc
        return self.dates[index]

    def index_day(self, day):
        if day <= self.start:
            return 0
        while not self.finite and (not self.dates or self.dates[-1] < day):
            self.at(len(self.dates))
        return bisect_left(self.dates, day)


def calendar_registry(start, calendars, resource_calendars, make_calendar):
    if not isinstance(calendars, dict) or not isinstance(resource_calendars, dict):
        raise ValueError('فهرست تقویم‌ها و تقویم منابع باید صریح باشد')
    if any(not isinstance(key, str) or not key.strip() or key == 'PROJECT' for key in calendars):
        raise ValueError('شناسه تقویم نامعتبر یا رزروشده است')
    parsed = {key: make_calendar(config, start) for key, config in calendars.items()}
    if any(not isinstance(rid, str) or not rid.strip()
           or not isinstance(cid, str) or cid not in parsed for rid, cid in resource_calendars.items()):
        raise ValueError('تقویم منبع ثبت نشده است')
    return parsed


def selected_calendars(task, parsed, resource_calendars):
    calendar_id = task.get('calendar_id')
    if calendar_id is not None and (not isinstance(calendar_id, str) or calendar_id not in parsed):
        raise ValueError('تقویم فعالیت ثبت نشده است')
    resource_ids = task.get('resource_ids', [])
    if (not isinstance(resource_ids, list)
            or any(not isinstance(rid, str) or rid not in resource_calendars for rid in resource_ids)
            or len(set(resource_ids)) != len(resource_ids)):
        raise ValueError('هر منبع زمان‌بندی به تقویم ثبت‌شده و شناسه یکتا نیاز دارد')
    return (calendar_id or 'PROJECT', *(resource_calendars[rid] for rid in sorted(resource_ids)))


def shift_event(event, lag, project, *, allow_before_start=False):
    if not lag:
        return event
    if allow_before_start and event < project.start:
        return shift_event(event,lag,project.with_start(event))
    index = project.index_day(event) + lag
    if index < 0:
        return project.start
    return project.at(index)


def clipped_lead(event, lag, project):
    return lag < 0 and project.index_day(event) + lag < 0


class Slot:
    def __init__(self, duration, calendar):
        self.duration = duration
        self.calendar = calendar

    def start(self, index):
        return self.calendar.at(index)

    def finish(self, index):
        if not self.duration:
            return self.start(index)
        if self.calendar.boundary_on_workday:
            return self.calendar.at(index + self.duration)
        try:
            return self.calendar.at(index + self.duration - 1) + DAY
        except OverflowError as exc:
            raise ValueError('سرریز تاریخ پایان فعالیت') from exc

    def event(self, endpoint, index):
        return self.finish(index) if endpoint == 'F' else self.start(index)

    def lower(self, endpoint, day):
        # A requirement earlier than the first possible endpoint does not
        # govern the project/calendar start even if both round to index zero.
        if day < self.event(endpoint, 0):
            return -1
        if endpoint == 'S' or not self.duration:
            return self.calendar.index_day(day)
        if self.calendar.boundary_on_workday:
            return max(0, self.calendar.index_day(day) - self.duration)
        if day <= self.calendar.start:
            return 0
        return max(0, self.calendar.index_day(day - DAY) - self.duration + 1)

    def upper_finish(self, day):
        if not self.duration:
            index = self.calendar.index_day(day)
            return index if self.calendar.is_open(day) else index - 1
        index = self.calendar.index_day(day)
        if self.calendar.boundary_on_workday and not self.calendar.is_open(day):
            index -= 1
        return index - self.duration


def latest_predecessor(limit, early, ceiling, pred, link, project):
    lag = link['lag']
    limit_index = None
    if lag:
        limit_index = project.index_day(limit)
        if not project.is_open(limit):
            limit_index -= 1
    lo, hi = early, ceiling
    while lo < hi:
        middle = (lo + hi + 1) // 2
        event = pred.event(link['type'][0], middle)
        if not lag:
            allowed = event <= limit
        else:
            index = project.index_day(event) + lag
            allowed = project.start <= limit if index < 0 else index <= limit_index
        if allowed:
            lo = middle
        else:
            hi = middle - 1
    return lo


def dated_cpm(by, duration, order, links, relationships, project, base, calendars, resource_calendars, parsed):
    slots = {}
    fingerprints = {}
    selected = {}
    effective = {}
    for key in order:
        task = by[key]
        ids = selected_calendars(task, parsed, resource_calendars)
        definitions = [base if cid == 'PROJECT' else calendars[cid] for cid in ids]
        if ids not in effective:
            effective[ids] = EffectiveCalendar([project if cid == 'PROJECT' else parsed[cid] for cid in ids])
        slots[key] = Slot(duration[key], effective[ids])
        fingerprints[key] = digest({'calendars': list(zip(ids, definitions)), 'resources': sorted(task.get('resource_ids', []))})
        selected[key] = list(ids)

    incoming = {key: [] for key in order}
    outgoing = {key: [] for key in order}
    for link, _ in links:
        incoming[link['succ']].append(link)
        outgoing[link['pred']].append(link)
    lower = {}
    early = {}
    tight = []
    roots = {}
    for key in order:
        earliest = by[key].get('not_before')
        slot = slots[key]
        lower[key] = max(0, slot.lower('S', project.valid_date(earliest))) if earliest is not None else 0
        bounds = []
        for link in incoming[key]:
            pred = link['pred']
            event=slots[pred].event(link['type'][0],early[pred])
            target=shift_event(event,link['lag'],project)
            bounds.append((slot.lower(link['type'][1],target),link,clipped_lead(event,link['lag'],project)))
        early[key] = max([lower[key], *(index for index, _, _ in bounds)])
        tight.extend(link for index, link, clipped in bounds if index == early[key] and not clipped)
        if early[key] == lower[key]:
            if earliest is not None and project.valid_date(earliest) >= slot.start(0):
                roots[key] = 'NOT_BEFORE'
            elif slot.start(0) > project.start:
                roots[key] = 'EFFECTIVE_CALENDAR_START'

    finishes = {key: slots[key].finish(early[key]) for key in order}
    end = max(finishes.values())
    latest = {}
    free = {}
    for key in reversed(order):
        slot = slots[key]
        project_limit = slot.upper_finish(end)
        latest[key] = project_limit
        free[key] = project_limit
        for link in outgoing[key]:
            succ = link['succ']
            target = slots[succ]
            latest[key] = latest_predecessor(target.event(link['type'][1], latest[succ]), early[key],
                                               latest[key], slot, link, project)
            free[key] = latest_predecessor(target.event(link['type'][1], early[succ]), early[key],
                                             free[key], slot, link, project)

    rows = {}
    for key in order:
        slot = slots[key]
        es = slot.start(early[key])
        ef = finishes[key]
        ls = slot.start(latest[key])
        lf = slot.finish(latest[key])
        tf = latest[key] - early[key]
        rows[key] = {
            'id': key, 'duration': slot.duration,
            **{field: (day - project.start).days for field, day in [('es', es), ('ef', ef), ('ls', ls), ('lf', lf)]},
            'total_float': tf, 'free_float': free[key] - early[key], 'critical': tf == 0,
            'milestone': slot.duration == 0, 'start': es.isoformat(),
            'finish': (ef - DAY if slot.duration else ef).isoformat(), 'finish_boundary': ef.isoformat(),
            'late_start': ls.isoformat(), 'late_finish_boundary': lf.isoformat(),
            'float_unit': 'ACTIVITY_WORKDAY', 'calendar_ids': selected[key], 'calendar_digest': fingerprints[key],
            'resource_ids': deepcopy(by[key].get('resource_ids', [])),
        }

    return {
        'activities': rows, 'order': order, 'duration': (end - project.start).days,
        'start': project.start.isoformat(), 'finish_boundary': end.isoformat(),
        'critical_ids': [key for key in order if rows[key]['critical']],
        'relationships': deepcopy(relationships), 'calendar': deepcopy(base), 'calendar_start': project.start.isoformat(),
        'calendars': deepcopy(calendars), 'resource_calendars': deepcopy(resource_calendars),
        'driving': driving_graph(order, tight, [key for key in order if finishes[key] == end], roots),
        'cpm_scope': 'EFFECTIVE_ACTIVITY_CALENDARS', 'offset_unit': 'CALENDAR_DAY',
        'warnings': [{'id': key, 'message': 'فعالیت ریشه؛ بدون پیش‌نیاز'} for key in order if not incoming[key]],
    }
