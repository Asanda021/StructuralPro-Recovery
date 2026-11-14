"""Deterministic editable PDM network (FS, SS, FF, SF + lag).

Workday offsets only; calendar dates and resource leveling are NOT implied.
References: PMI Scheduling 101, CMU PMBook ch10, Oracle P6 Relationships.
"""
from __future__ import annotations


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
            weight = lag
            if kind in ("FS", "FF"):
                weight += durations[pred]
            if kind in ("FF", "SF"):
                weight -= durations[key]
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
    else:
        plan.pop("cpm_scope", None)
    plan["network_review_status"]="DRAFT_UNAPPROVED_NOT_RESOURCE_LEVELED"
    return plan
