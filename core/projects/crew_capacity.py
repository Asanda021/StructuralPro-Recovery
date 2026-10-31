"""Resource feasibility gate and optional deterministic capacity leveling.

Only explicitly named crew pools are constrained. Suggestions that simply
say "2 crews suggested" do not imply identical available people. Existing
PDM dependency semantics are preserved; the resource leveler is a *draft*
scenario and never overwrites a saved contractual baseline.
"""
from __future__ import annotations
from copy import deepcopy
from collections import defaultdict
from core.projects.precedence_model import calculate_precedence


def _request(task,limits):
    name=task.get("crew_pool")
    if not name:
        return None
    if name not in limits:
        raise ValueError(f"ظرفیت اکیپ «{name}» مشخص نشده است")
    demand=task.get("crew_demand",1)
    if type(demand) is not int or demand<1:
        raise ValueError("درخواست اکیپ باید عدد صحیح مثبت باشد")
    cap=limits[name]
    if type(cap) is not int or cap<1 or cap>100:
        raise ValueError("ظرفیت اکیپ باید عدد صحیح ۱ تا ۱۰۰ باشد")
    if demand>cap:
        raise ValueError("تقاضای یک فعالیت از کل اکیپ‌های موجود بیشتر است")
    return name,demand,cap


def _relations(task):
    mapped={x["predecessor"]:(x["type"],x["lag_days"]) for x in task.get("links",[])}
    return [(pid,*mapped.get(pid,("FS",0))) for pid in task["predecessors"]]


def _earliest(task,scheduled):
    start=0
    duration=task["duration_days"]
    for name,kind,lag in _relations(task):
        previous=scheduled[name]
        ps=previous["start_workday_offset"]
        pf=previous["end_workday_offset"]
        bound={
            "FS":pf+lag,
            "SS":ps+lag,
            "FF":pf+lag-duration,
            "SF":ps+lag-duration,
        }[kind]
        start=max(start,bound)
    return start


def resource_conflicts(plan,limits):
    """Report every overloaded crew workday, with no false 'safe' status."""
    copy=deepcopy(plan)
    calculate_precedence(copy)
    usage=defaultdict(lambda:defaultdict(list))
    for task in copy["tasks"]:
        request=_request(task,limits)
        if not request or not task["duration_days"]:
            continue
        name,demand,_=request
        for d in range(task["start_workday_offset"],task["end_workday_offset"]):
            usage[name][d].append((task["id"],demand))
    errors=[]
    for name,days in usage.items():
        for day,items in days.items():
            total=sum(x[1] for x in items)
            if total>limits[name]:
                errors.append({"crew_pool":name,"workday":day,
                               "demand":total,"available":limits[name],
                               "tasks":sorted(x[0] for x in items)})
    return sorted(errors,key=lambda x:(x["workday"],x["crew_pool"]))


def level_shared_crew_resources(plan,limits,max_offset=3650):
    """Topological serial scheduling against explicit capacities only.

    Structural precedence is respected for FS, SS, FF and SF, including
    lead/lag. The method is an auditable deterministic *one* draft scenario.
    """
    draft=deepcopy(plan)
    if not isinstance(limits,dict):raise ValueError("ظرفیت منابع باید جدول باشد")
    calculate_precedence(draft)  # fail-fast for cycles and invalid links
    by_id={task["id"]:task for task in draft["tasks"]}
    visited=set()
    order=[]
    def visit(name):
        if name in visited:return
        visited.add(name)
        for pred in by_id[name]["predecessors"]:visit(pred)
        order.append(name)
    for key in by_id:visit(key)
    scheduled={}
    usage=defaultdict(lambda:defaultdict(int))
    for key in order:
        task=by_id[key]
        req=_request(task,limits)
        duration=task["duration_days"]
        earliest=_earliest(task,scheduled)
        start=earliest
        if req is not None and duration:
            name,demand,cap=req
            # Check only the current task's pool; other pools were committed
            # independently. This avoids exponential scheduling search.
            while any(usage[name][day]+demand>cap
                      for day in range(start,start+duration)):
                start+=1
                if start>max_offset:raise ValueError("امکان تخصیص اکیپ در افق ایمن وجود ندارد")
            for day in range(start,start+duration):
                usage[name][day]+=demand
        task["start_workday_offset"]=start
        task["end_workday_offset"]=start+duration
        scheduled[key]=task
    draft["indicative_total_workdays"]=max(
        (x["end_workday_offset"] for x in draft["tasks"]),default=0
    )
    draft["resource_limits"]=deepcopy(limits)
    draft["resource_leveling_status"]="PROPOSED_UNAPPROVED"
    draft["resource_conflict_count"]=len(resource_conflicts(draft,limits))
    # Do not rerun bare PDM calculation on the leveled result; it would reset
    # the intentional resource offsets.
    if draft["resource_conflict_count"]:
        raise AssertionError("resource leveler produced overloaded draft")
    return draft
