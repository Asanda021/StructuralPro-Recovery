"""Deterministic editable PDM network (FS, SS, FF, SF + lag).

Workday offsets only; calendar dates and resource leveling are NOT implied.
References: PMI Scheduling 101, CMU PMBook ch10, Oracle P6 Relationships.
"""
from __future__ import annotations


def relation_weight(predecessor_duration, successor_duration, kind, lag):
    """Convert the two endpoints of a shared-axis relationship to a start bound."""
    return (lag + (predecessor_duration if kind[0] == 'F' else 0)
            - (successor_duration if kind[1] == 'F' else 0))


def driving_graph(order, tight, finish_ids, binding_dates):
    """Explain the current finish via binding edges, not via zero float alone."""
    path_limit = 64
    count_limit = 1_000_000_000_000
    incoming = {key: [] for key in order}
    for link in sorted(tight, key=lambda row: (row['pred'], row['succ'])):
        incoming[link['succ']].append(link)
    finish_ids = sorted(finish_ids)
    retained = set(finish_ids)
    for key in reversed(order):
        if key in retained:
            retained.update(link['pred'] for link in incoming[key])
    roots = {}
    choices = {}
    counts = {}
    for key in order:
        if key not in retained:
            continue
        predecessors = [link['pred'] for link in incoming[key]]
        if key in binding_dates or not predecessors:
            roots[key] = binding_dates.get(key, 'PROJECT_START')
            predecessors.insert(0, None)
        choices[key] = predecessors
        counts[key] = min(count_limit + 1, sum(1 if pred is None else counts[pred] for pred in predecessors))
    count = min(count_limit + 1, sum(counts[key] for key in finish_ids))
    paths = []
    for end in finish_ids:
        chain = [end]
        stack = [iter(choices[end])]
        while stack and len(paths) < path_limit:
            try:
                pred = next(stack[-1])
            except StopIteration:
                stack.pop()
                chain.pop()
                continue
            if pred is None:
                paths.append(list(reversed(chain)))
            else:
                chain.append(pred)
                stack.append(iter(choices[pred]))
        if len(paths) == path_limit:
            break
    return {'finish_ids': finish_ids,
            'roots': [{'id': key, 'reason': roots[key]} for key in sorted(roots)],
            'edges': [link for key in sorted(retained) for link in incoming[key]],
            'paths': paths, 'path_count': min(count, count_limit),
            'path_count_capped': count > count_limit, 'paths_truncated': count > len(paths)}


def precedence_order(predecessors):
    """Visit dependencies first in input order, without using the call stack."""
    done = set()
    visiting = set()
    order = []
    for key in predecessors:
        if key in done:
            continue
        visiting.add(key)
        stack = [(key, iter(predecessors[key]))]
        while stack:
            task, refs = stack[-1]
            predecessor = next(refs, None)
            if predecessor is None:
                stack.pop()
                visiting.remove(task)
                done.add(task)
                order.append(task)
            elif predecessor in visiting:
                raise ValueError("چرخه در شبکه تقدم و تأخر")
            elif predecessor not in done:
                visiting.add(predecessor)
                stack.append((predecessor, iter(predecessors[predecessor])))
    return order


_CPM_TASK_FIELDS = (
    "latest_start_workday_offset", "latest_end_workday_offset",
    "total_float_workdays", "free_float_workdays",
)


def calculate_precedence(plan, *, include_cpm=False):
    tasks=plan.get("tasks",[])
    if not isinstance(tasks,list):raise ValueError("فهرست فعالیت‌ها معتبر نیست")
    if plan.get('calendars') or plan.get('resource_calendars') or any(
            isinstance(task,dict) and (task.get('calendar_id') is not None or task.get('resource_ids'))
            for task in tasks):
        raise ValueError('محور نسبی پیش‌نویس از تقویم فعالیت یا منبع پشتیبانی نمی‌کند')
    by_id={}
    for t in tasks:
        ident=t.get("id")
        if not isinstance(ident,str) or not ident or ident in by_id:
            raise ValueError("شناسه فعالیت تکراری یا نامعتبر")
        by_id[ident]=t
    def relationships(task):
        refs=task.get("predecessors",[])
        if not isinstance(refs,list) or any(not isinstance(x,str) for x in refs) or len(refs)!=len(set(refs)):
            raise ValueError("پیش‌نیازها باید یکتا و معتبر باشند")
        # The explicit relationship map augments legacy FS-only predecessors
        # instead of forcing old stored schedules to migrate.
        special=task.get("links") or []
        if not isinstance(special,list):raise ValueError("روابط تقدم و تأخر معتبر نیست")
        mapping={}
        for link in special:
            if not isinstance(link,dict):raise ValueError("ساختار رابطه معتبر نیست")
            predecessor=link.get("predecessor")
            kind=link.get("type")
            lag=link.get("lag_days",0)
            if kind not in ("FS","SS","FF","SF") or type(lag) is not int or not -30<=lag<=365:
                raise ValueError("نوع رابطه یا تأخیر نامعتبر است")
            if predecessor in mapping:raise ValueError("رابطه تکراری ثبت شده")
            mapping[predecessor]=(kind,lag)
        if set(mapping)-set(refs):raise ValueError("رابطه به فعالیت غیرپیش‌نیاز اشاره می‌کند")
        for predecessor in refs:
            if predecessor not in by_id or predecessor==task["id"]:
                raise ValueError("شناسه پیش‌نیاز ناشناخته یا حلقه خودارجاع")
        return [(name,*mapping.get(name,("FS",0))) for name in refs]
    if include_cpm:
        unsupported = {"constraint", "constraints", "deadline", "calendar", "calendar_id",
                       "not_before", "actual_start", "actual_finish", "actual_end", "remaining_duration", "data_date"}
        if any(unsupported.intersection(t) for t in tasks) or any(k in plan for k in ("data_date", "deadline", "calendar")):
            raise ValueError("CPM offsets do not support constraints, calendars or actuals")

    durations = {}
    incoming = {}
    for key, task in by_id.items():
        duration=task.get("duration_days")
        if type(duration) is not int or not 0<=duration<=3650:
            raise ValueError("مدت فعالیت باید عدد صحیح معتبر باشد")
        durations[key] = duration
        incoming[key] = relationships(task)

    order = precedence_order({key: [pred for pred, _, _ in links]
                              for key, links in incoming.items()})
    starts = {}
    outgoing = {key: [] for key in by_id} if include_cpm else None
    for key in order:
        lower = 0
        for pred, kind, lag in incoming[key]:
            weight = relation_weight(durations[pred], durations[key], kind, lag)
            lower = max(lower, starts[pred] + weight)
            if outgoing is not None:
                outgoing[pred].append((key, weight))
        starts[key] = lower

    finish = max((starts[key] + durations[key] for key in by_id), default=0)
    for key, task in by_id.items():
        task["start_workday_offset"] = starts[key]
        task["end_workday_offset"] = starts[key] + durations[key]
        for field in _CPM_TASK_FIELDS:
            task.pop(field, None)
    plan["indicative_total_workdays"] = finish
    if include_cpm:
        # Relative offset analysis only: shared workday axis, no calendar or constraints.
        for key in reversed(order):
            task=by_id[key]; duration=durations[key]
            latest=min([finish-duration]+[by_id[s]["latest_start_workday_offset"]-w for s,w in outgoing[key]])
            early=task["start_workday_offset"]
            free=min([finish-duration-early]+[by_id[s]["start_workday_offset"]-w-early for s,w in outgoing[key]])
            task["latest_start_workday_offset"]=latest
            task["latest_end_workday_offset"]=latest+duration
            task["total_float_workdays"]=latest-early
            task["free_float_workdays"]=free
        plan["cpm_scope"]="DRAFT_SHARED_WORKDAY_OFFSETS_NO_CONSTRAINTS_OR_ACTUALS"
        tight = [{'pred': pred, 'succ': succ, 'type': kind, 'lag': lag}
                 for succ, links in incoming.items() for pred, kind, lag in links
                 if starts[succ] == starts[pred] + relation_weight(durations[pred], durations[succ], kind, lag)]
        plan['driving'] = driving_graph(order, tight,
                                        [key for key in order if starts[key] + durations[key] == finish], {})
    else:
        plan.pop("cpm_scope", None)
        plan.pop('driving', None)
    plan["network_review_status"]="DRAFT_UNAPPROVED_NOT_RESOURCE_LEVELED"
    return plan
