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
