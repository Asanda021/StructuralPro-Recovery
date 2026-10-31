"""Separate auditable day-by-day weekly work plans for every engineer.

No shared mutable engineer schedule. Work items are suggested/planned only;
checks are human attestations, not automatic physical-progress certification.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
from core.projects.iran_worksite_calendar import gregorian_1405,solar_1405

WEEKDAY_FA=("دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه")
_ITEM_STATES=frozenset(("planned","in_progress","blocked","done"))


def _identity(value,label):
    if not isinstance(value,str) or not value.strip() or len(value)>128:
        raise ValueError(label+" معتبر نیست")
    return value.strip()


def week_start_of(day):
    greg=gregorian_1405(day)
    saturday=greg-timedelta(days=(greg.weekday()-5)%7)
    return solar_1405(saturday)


def _week_dates(start):
    first=gregorian_1405(start)
    if first.weekday()!=5:
        raise ValueError("روز آغاز هفته باید شنبه باشد")
    return [(solar_1405(first+timedelta(days=i)),
             WEEKDAY_FA[(first+timedelta(days=i)).weekday()])
            for i in range(7)]


def create_engineer_week(plans,engineer_id,engineer_name,week_of,*,role="",source_sha256=""):
    ident=_identity(engineer_id,"شناسه مهندس")
    name=_identity(engineer_name,"نام مهندس")
    if not isinstance(plans,list):raise ValueError("فهرست برنامه مهندسان نامعتبر است")
    first=week_start_of(week_of)
    if any(p["engineer_id"]==ident and p["week_start"]==first for p in plans):
        raise ValueError("برنامه این مهندس برای این هفته قبلاً ایجاد شده")
    days=[
        {"jalali":jalali,"day_name":weekday,
         "work_items":[],"daily_note":""}
        for jalali,weekday in _week_dates(first)
    ]
    out=deepcopy(plans)
    out.append({
        "schema":"structuralpro.engineer-week-v1",
        "engineer_id":ident,"engineer_name":name,
        "role":str(role).strip()[:128],"week_start":first,
        "source_sha256":str(source_sha256 or ""),
        "status":"DRAFT_UNAPPROVED",
        "days":days,
    })
    return out


def _week(plans,engineer_id,week_start):
    for week in plans:
        if week.get("engineer_id")==engineer_id and week.get("week_start")==week_start:
            return week
    raise ValueError("برنامه هفتگی این مهندس وجود ندارد")


def add_week_item(plans,engineer_id,week_start,day,title,*,activity_id=None,
                  checklist=(),priority="normal",notes="",source_ref=""):
    if priority not in ("low","normal","high","critical"):
        raise ValueError("اولویت فعالیت معتبر نیست")
    title=_identity(title,"شرح کار قابل انجام")
    if not isinstance(checklist,(list,tuple)) or len(checklist)>40:
        raise ValueError("حداکثر ۴۰ مورد چک‌لیست مجاز است")
    labels=[_identity(value,"شرح چک‌لیست") for value in checklist]
    if len(set(labels))!=len(labels):
        raise ValueError("چک‌لیست نباید موارد تکراری داشته باشد")
    draft=deepcopy(plans)
    week=_week(draft,engineer_id,week_start)
    day_record=next((d for d in week["days"] if d["jalali"]==day),None)
    if day_record is None:
        raise ValueError("تاریخ فعالیت خارج از هفته انتخابی است")
    day_record["work_items"].append({
        "id":"EW-"+uuid4().hex[:16],
        "title":title,"activity_id":str(activity_id or ""),
        "source_ref":str(source_ref or ""),
        "priority":priority,"status":"planned",
        "notes":str(notes)[:2000],
        "checklist":[{"id":f"check-{i+1}","text":x,"done":False,
                      "checked_by":None} for i,x in enumerate(labels)],
        "completed_by":None,
    })
    return draft


def check_week_item(plans,engineer_id,week_start,day,item_id,check_id,*,done,operator):
    if type(done) is not bool:raise ValueError("چک‌لیست باید انجام‌شده یا انجام‌نشده باشد")
    checked_by=_identity(operator,"نام ثبت‌کننده چک‌لیست")
    draft=deepcopy(plans)
    week=_week(draft,engineer_id,week_start)
    section=next((x for x in week["days"] if x["jalali"]==day),None)
    if section is None:raise ValueError("روز موردنظر در این هفته نیست")
    item=next((x for x in section["work_items"] if x["id"]==item_id),None)
    if item is None:raise ValueError("فعالیت انتخاب‌شده وجود ندارد")
    check=next((x for x in item["checklist"] if x["id"]==check_id),None)
    if check is None:raise ValueError("ردیف چک‌لیست وجود ندارد")
    check["done"]=done
    check["checked_by"]=checked_by if done else None
    if not done and item["status"]=="done":
        item["status"]="in_progress"
        item["completed_by"]=None
    return draft


def set_week_item_status(plans,engineer_id,week_start,day,item_id,status,*,operator,notes=None):
    if status not in _ITEM_STATES:raise ValueError("وضعیت فعالیت نامعتبر است")
    signed=_identity(operator,"نام بازبین")
    draft=deepcopy(plans)
    week=_week(draft,engineer_id,week_start)
    section=next((x for x in week["days"] if x["jalali"]==day),None)
    if section is None:raise ValueError("روز خارج از برنامه است")
    task=next((x for x in section["work_items"] if x["id"]==item_id),None)
    if task is None:raise ValueError("فعالیت روزانه وجود ندارد")
    if status=="done" and (not task["checklist"] or any(not x["done"] for x in task["checklist"])):
        raise ValueError("تا تکمیل چک‌لیست، بستن فعالیت مجاز نیست")
    task["status"]=status
    task["completed_by"]=signed if status=="done" else None
    if notes is not None:task["notes"]=str(notes)[:2000]
    return draft


def weekly_summary(plans,engineer_id,week_start):
    week=_week(plans,engineer_id,week_start)
    count=sum(len(day["work_items"]) for day in week["days"])
    done=sum(item["status"]=="done" for day in week["days"] for item in day["work_items"])
    checks=sum(len(item["checklist"]) for day in week["days"] for item in day["work_items"])
    checked=sum(bool(x["done"]) for day in week["days"] for item in day["work_items"] for x in item["checklist"])
    return {
        "engineer_id":week["engineer_id"],
        "engineer_name":week["engineer_name"],
        "week_start":week_start,
        "item_count":count,"completed_items":done,
        "checklist_count":checks,"checked_count":checked,
        "review_status":week["status"],
    }
