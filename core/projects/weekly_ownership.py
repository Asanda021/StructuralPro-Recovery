"""Four discipline owners and WBS-linked weekly assignments."""
from __future__ import annotations

from copy import deepcopy
from core.projects.engineer_weekly_plan import create_engineer_week, week_start_of, _week_dates
from core.projects.jalali_dates import jalali_to_gregorian
from core.projects.iran_worksite_calendar import _calendar_holiday_sets

TRADES=("structure","architecture","mechanical","electrical")
TRADE_NAMES=("سازه","معماری","مکانیک","برق")
CHECKLIST={
 "structure":("کنترل نقشه سازه","کنترل جزئیات اجرایی","ثبت گزارش عدم انطباق"),
 "architecture":("کنترل نقشه معماری","کنترل کیفیت و تراز","ثبت گزارش روز"),
 "mechanical":("کنترل نقشه مکانیک","کنترل تداخل‌ها","ثبت تست‌ها"),
 "electrical":("کنترل نقشه برق","کنترل ایمنی و مدار","ثبت تست‌ها"),
}

# Activity-family checks are applied to the exact scheduled work item, not
# only the engineer's discipline. They are review prompts, not approvals.
ACTIVITY_CHECKS={
    "foundation":("کنترل آکس و تراز فونداسیون","کنترل بتن مگر و بستر",
                  "کنترل آرماتورها/کاور طبق نقشه","کنترل صورتجلسه مجوز بتن‌ریزی"),
    "rebar":("کنترل قطر، تعداد و طول مهاری میلگرد","کنترل وصله و خاموت",
             "کنترل کاور و فواصل","تأیید آمادگی قبل بتن‌ریزی"),
    "concrete":("کنترل قالب و شمع‌بندی","کنترل اسلامپ و نمونه‌گیری مطابق طرح",
                "کنترل تراکم و ویبره","ثبت عمل‌آوری و محدودیت بارگذاری"),
    "form":("کنترل ابعاد و تراز قالب","کنترل مهاربندی و ایمنی",
             "کنترل بازشوها و تأسیسات مدفون"),
    "steel":("کنترل قطعات و ابعاد ساخت","کنترل اتصالات، پیچ یا جوش",
              "کنترل شاقولی و پایداری موقت"),
    "wall":("کنترل محل دیوار و بازشو","کنترل شاقولی و رج‌بندی",
             "کنترل اتصال‌ها و وال‌پست در صورت الزام نقشه"),
    "tile":("کنترل آماده‌سازی زیرکار و عایق","کنترل شیب و تراز",
             "کنترل بندها و کیفیت نصب"),
    "plaster":("کنترل رطوبت و زیرکار","کنترل ضخامت و تراز اندود",
                "کنترل کیفیت و ترک‌خوردگی"),
    "paint":("کنترل رطوبت و آماده‌سازی","کنترل اجرای آستر",
              "کنترل پوشش نهایی"),
    "facade":("کنترل جزئیات اتصال و مهار نما","کنترل داربست و ایمنی ارتفاع",
               "کنترل اجرا و آب‌بندی"),
    "water":("کنترل لوله، قطر و مسیر","کنترل شیب یا عایق در صورت نیاز",
              "کنترل تست فشار و ثبت نتیجه"),
    "sewage":("کنترل مسیر و شیب فاضلاب","کنترل اتصال‌ها و ونت",
               "کنترل آزمایش آب‌بندی"),
    "gas":("کنترل مجوز و روش اجرا","کنترل اتصالات مطابق نقشه",
            "کنترل تست نشتی توسط مجاز"),
    "hvac":("کنترل کانال و عایق","کنترل تداخل سازه و معماری",
             "کنترل تست و راه‌اندازی"),
    "conduit":("کنترل مسیر لوله و قوطی برق","کنترل فاصله و تداخل",
                "کنترل مسیر کشش سیم قبل پوشش"),
    "wiring":("کنترل سطح مقطع و نوع سیم","کنترل تست پیوستگی و عایق",
               "کنترل شناسایی مدارها"),
    "panel":("کنترل تابلو و شماره مدارها","کنترل ارت و حفاظت",
              "کنترل تست الکتریکی"),
    "elevator":("کنترل شاقولی و ریل‌ها","کنترل ایمنی چاه و تجهیزات",
                 "کنترل تست‌ها توسط مجاز"),
    "fire":("کنترل نقشه آتش‌نشانی","کنترل تجهیزات و مسیرها",
             "کنترل تست و تأییدهای لازم"),
}
def daily_checklist(activity,trade):
    """Generate actionable daily inspection points from WBS task identity."""
    description=" ".join((str(activity.get("id","")),
                          str(activity.get("title","")),
                          str(activity.get("family","")))).lower()
    aliases={
        "آرماتور":"rebar","میلگرد":"rebar","بتن":"concrete",
        "قالب":"form","بلوک":"wall","آجر":"wall",
        "سرامیک":"tile","کاشی":"tile","گچ":"plaster",
        "رنگ":"paint","نما":"facade","فاضلاب":"sewage",
        "سیم":"wiring","تابلو":"panel","لوله برق":"conduit",
        "آسانسور":"elevator","اعلام حریق":"fire",
        "اطفا":"fire","فونداسیون":"foundation","شناژ":"foundation",
        "اسکلت فولادی":"steel","تهویه":"hvac",
    }
    for label,key in aliases.items():
        if label in description:
            return ACTIVITY_CHECKS[key]
    for key,checks in ACTIVITY_CHECKS.items():
        if key in description:return checks
    return CHECKLIST[trade]

def define_team(names, owners):
    if not isinstance(names,list) or not 1<=len(names)<=4:
        raise ValueError("تعداد سرپرستان باید بین ۱ و ۴ نفر باشد")
    if not isinstance(owners,dict) or set(owners)!=set(TRADES):
        raise ValueError("مسئول چهار رشته باید مشخص باشد")
    if any(not isinstance(n,str) or not n.strip() for n in names):
        raise ValueError("نام سرپرست لازم است")
    if any(type(i) is not int or i<0 or i>=len(names) for i in owners.values()):
        raise ValueError("مسئول رشته نامعتبر است")
    if set(owners.values())!=set(range(len(names))):
        raise ValueError("سرپرست بدون رشته نباید ثبت شود")
    people=[{"id":f"supervisor-{i+1}","name":name.strip(),
             "trades":[t for t,j in owners.items() if j==i]}
            for i,name in enumerate(names)]
    return {"schema":"structuralpro.supervision-team-v1",
            "people":people,"count":len(people),
            "mode":"single" if len(people)==1 else "specialized",
            "owners":{t:f"supervisor-{i+1}" for t,i in owners.items()}}

def recommended_team(names):
    splits={1:(0,0,0,0),2:(0,0,1,1),3:(0,1,2,2),4:(0,1,2,3)}
    if len(names) not in splits:raise ValueError("بین ۱ تا ۴ سرپرست")
    return define_team(names,dict(zip(TRADES,splits[len(names)])))

def owner_discipline(task):
    scope=task.get("discipline")
    if scope in TRADES:return scope
    if scope=="fire":
        return "electrical" if "alarm" in str(task.get("id","")) else "mechanical"
    return {"elevator":"mechanical","site":"architecture","wood":"structure",
            "renovation":"architecture","restoration":"architecture"}.get(scope)

def _working(date,calendar):
    off,_=_calendar_holiday_sets(calendar,int(date[:4]))
    return (jalali_to_gregorian(date).weekday() in
            calendar.get("working_weekdays",(0,1,2,3,5,6))
            and (date not in off or date in calendar.get("working_day_exceptions",[])))


def derive_weeks(team, plan, reference_date, previous_weeks, source_sha256):
    """Project an existing dated WBS into each supervisor's seven-day plan.

    No activity is independently invented. Preserves signed checks when the
    source task's date/duration has not changed; otherwise resets approval.
    """
    from hashlib import sha256
    if not isinstance(team,dict) or team.get("schema")!="structuralpro.supervision-team-v1":
        raise ValueError("ساختار سرپرستی پروژه انتخاب نشده است")
    if not isinstance(plan,dict) or not plan.get("calendar",{}).get("start_date"):
        raise ValueError("اول باید تاریخ شروع برنامه زمان‌بندی اصلی مشخص شود")
    if plan.get("source_sha256")!=source_sha256:
        raise ValueError("نسخه برنامه با نقشه تطبیق ندارد")
    if not isinstance(previous_weeks,list):
        raise ValueError("سوابق هفتگی سرپرستان معتبر نیست")
    first=week_start_of(reference_date)
    dates=[day for day,_ in _week_dates(first)]
    result=deepcopy(previous_weeks)
    for person in team["people"]:
        if not any(w.get("engineer_id")==person["id"] and
                   w.get("week_start")==first for w in result):
            result=create_engineer_week(
                result,person["id"],person["name"],first,
                role="، ".join(TRADE_NAMES[TRADES.index(t)] for t in person["trades"]),
                source_sha256=source_sha256,
            )
    active=set()
    uncovered=[]
    changed=[]
    for activity in plan.get("tasks",[]):
        if activity.get("duration_days",0)<=0 or not activity.get("start_jalali"):
            continue
        trade=owner_discipline(activity)
        if trade not in team["owners"]:
            uncovered.append(str(activity.get("id","")))
            continue
        person_id=team["owners"][trade]
        week=next(w for w in result if w["engineer_id"]==person_id
                  and w["week_start"]==first)
        begin=jalali_to_gregorian(activity["start_jalali"])
        finish=jalali_to_gregorian(activity["finish_jalali"])
        # A changed measured quantity, source reference or task title can
        # invalidate a signed site inspection even when the duration and
        # schedule dates remain identical.
        stamp={
            "activity_id":str(activity["id"]),
            "title":activity.get("title",""),
            "start":activity["start_jalali"],
            "finish":activity["finish_jalali"],
            "duration":activity["duration_days"],
            "scheduled_quantity":activity.get("scheduled_quantity"),
            "linked_item_ids":sorted(map(str,activity.get("linked_item_ids",[]))),
            "quantity_multiplier_evidence":activity.get("quantity_multiplier_evidence"),
            "discipline":trade,
            "assigned_supervisor":person_id,
            "supervisor_name":next(p["name"] for p in team["people"]
                                   if p["id"]==person_id),
            "checklist":list(daily_checklist(activity,trade)),
        }
        for day in dates:
            dt=jalali_to_gregorian(day)
            if not begin<=dt<=finish or not _working(day,plan["calendar"]):
                continue
            uid="EW-SCH-"+sha256(
                f"{source_sha256}|{person_id}|{activity['id']}|{day}".encode()
            ).hexdigest()[:20]
            active.add(uid)
            day_row=next(d for d in week["days"] if d["jalali"]==day)
            old=next((v for v in day_row["work_items"] if v["id"]==uid),None)
            same=old is not None and old.get("schedule_snapshot")==stamp
            checks=[]
            for i,title in enumerate(daily_checklist(activity,trade),1):
                old_check=(next((v for v in old["checklist"]
                     if v["id"]==f"check-{i}" and v["text"]==title),None)
                     if same else None)
                checks.append({"id":f"check-{i}","text":title,
                               "done":bool(old_check and old_check["done"]),
                               "checked_by":(old_check.get("checked_by")
                                             if old_check and old_check["done"] else None)})
            row={"id":uid,"title":activity["title"],"activity_id":activity["id"],
                 "source_ref":", ".join(map(str,activity.get("linked_item_ids",[]))),
                 "priority":"normal","status":old.get("status","planned") if same else "planned",
                 "notes":old.get("notes","") if old else "",
                 "checklist":checks,"completed_by":old.get("completed_by") if same else None,
                 "origin":"schedule_generated","schedule_snapshot":stamp,
                 "review_required":not bool(plan.get("calendar_approved"))}
            if old:
                if not same and (
                    old.get("status")=="done" or
                    any(x.get("done") for x in old.get("checklist",[]))
                ):
                    changed.append(uid)
                day_row["work_items"].remove(old)
            day_row["work_items"].append(row)
    for week in result:
        if week["week_start"]!=first:continue
        person=next((p for p in team["people"] if p["id"]==week["engineer_id"]),None)
        if person is None:continue
        week["engineer_name"]=person["name"]
        week["role"]="، ".join(TRADE_NAMES[TRADES.index(t)] for t in person["trades"])
        week["derived_from_wbs"]=True
        week["schedule_review_status"]="DRAFT_FROM_MAIN_WBS"
        for day in week["days"]:
            for item in day["work_items"]:
                if (item.get("origin")=="schedule_generated"
                        and item["id"] not in active
                        and (item.get("status")=="done" or
                             any(check.get("done") for check in item.get("checklist",[])))):
                    changed.append(item["id"])
            day["work_items"]=[item for item in day["work_items"]
                if item.get("origin")!="schedule_generated" or item["id"] in active]
    return {"plans":result,"week_start":first,"unassigned_wbs":sorted(set(uncovered)),
            "invalidated_signed_checks":sorted(set(changed)),
            "status":"SOURCE_DERIVED_DRAFT"}
