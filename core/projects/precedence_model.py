"""Deterministic editable PDM network (FS, SS, FF, SF + lag).

Workday offsets only; calendar dates and resource leveling are NOT implied.
References: PMI Scheduling 101, CMU PMBook ch10, Oracle P6 Relationships.
"""
from __future__ import annotations
def calculate_precedence(plan):
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
    visited,stack=set(),set()
    def start_of(key):
        if key in stack:raise ValueError("چرخه در شبکه تقدم و تأخر")
        if key in visited:return by_id[key]["start_workday_offset"]
        stack.add(key)
        task=by_id[key]
        duration=task.get("duration_days")
        if type(duration) is not int or not 0<=duration<=3650:
            raise ValueError("مدت فعالیت باید عدد صحیح معتبر باشد")
        lower=0
        for pred,kind,lag in relationships(task):
            before=start_of(pred)
            p=by_id[pred]
            predecessor_finish=before+p["duration_days"]
            if kind=="FS": candidate=predecessor_finish+lag
            elif kind=="SS":candidate=before+lag
            elif kind=="FF":candidate=predecessor_finish+lag-duration
            else:candidate=before+lag-duration
            lower=max(lower,candidate)
        task["start_workday_offset"]=lower
        task["end_workday_offset"]=lower+duration
        stack.remove(key);visited.add(key)
        return lower
    for key in by_id:start_of(key)
    plan["indicative_total_workdays"]=max((t["end_workday_offset"] for t in tasks),default=0)
    plan["network_review_status"]="DRAFT_UNAPPROVED_NOT_RESOURCE_LEVELED"
    return plan
