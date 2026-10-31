"""Iranian 1405 worksite calendar: visible, editable, source-attributed.

This is a period-specific calendar fixture, not an eternal lunar holiday
oracle.  Provincial/emergency closures are an optional site overlay.  After
1405 the user must import a reviewed calendar instead of silently assuming
holidays for years not in this dataset.
"""
from __future__ import annotations
from datetime import date,timedelta
from copy import deepcopy
from core.projects.precedence_model import calculate_precedence

_SOURCE="https://timestamp.ir/holidays-list"
_YEAR=1405
_ANCHOR=date(2026,3,21)
_MONTH_LENGTHS=(31,31,31,31,31,31,30,30,30,30,30,29)
# 27 public nationwide dates in the cited national 1405 list; extraordinary
# Tehran-only / emergency closures (Tir 13-16) intentionally NOT silently
# adopted as permanent nationwide holidays.
_BASE_HOLIDAYS={
    (1,1),(1,2),(1,3),(1,4),(1,12),(1,13),(1,24),
    (3,3),(3,6),(3,14),(3,15),
    (4,3),(4,4),
    (5,13),(5,21),(5,22),(5,30),
    (6,8),(8,22),
    (10,2),(10,16),
    (11,4),(11,22),
    (12,9),(12,19),(12,20),(12,29),
}


def _parse_solar(value):
    if not isinstance(value,str):raise ValueError("تاریخ شمسی باید رشته YYYY/MM/DD باشد")
    parts=value.replace("-","/").split("/")
    if len(parts)!=3 or any(not x.isascii() or not x.isdigit() for x in parts):
        raise ValueError("تاریخ شمسی باید YYYY/MM/DD باشد")
    y,m,d=map(int,parts)
    if y!=_YEAR or not 1<=m<=12 or not 1<=d<=_MONTH_LENGTHS[m-1]:
        raise ValueError("تاریخ خارج از تقویم بازبینی‌شده ۱۴۰۵ است")
    return m,d


def gregorian_1405(solar):
    month,day=_parse_solar(solar)
    return _ANCHOR+timedelta(days=sum(_MONTH_LENGTHS[:month-1])+day-1)


def solar_1405(gregorian):
    delta=(gregorian-_ANCHOR).days
    if not 0<=delta<sum(_MONTH_LENGTHS):
        raise ValueError("برای سال بعد باید تقویم رسمی آن سال بازبینی و بارگذاری شود")
    remaining=delta
    for m,length in enumerate(_MONTH_LENGTHS,1):
        if remaining<length:return f"{_YEAR:04d}/{m:02d}/{remaining+1:02d}"
        remaining-=length
    raise AssertionError("unexpected solar date")


def make_calendar(*,start_date=None,holidays=None,extra_holidays=None,
                  working_weekdays=(0,1,2,3,5,6),official_holidays=True):
    """Python Mon=0 .. Sun=6; Iran conventional six-day week excludes Fri=4.

    Calendar specific overrides require user confirmation before baseline.
    """
    weekdays=list(working_weekdays)
    if len(set(weekdays))!=len(weekdays) or any(type(x) is not int or x not in range(7) for x in weekdays):
        raise ValueError("روزهای کاری نامعتبر است")
    if not weekdays:raise ValueError("حداقل یک روز کاری در هفته لازم است")
    when=gregorian_1405(start_date) if start_date is not None else None
    def checked(values):
        return sorted({f"{_YEAR:04d}/{m:02d}/{d:02d}" for m,d in (_parse_solar(v) for v in values)})
    fixed=checked(f"{_YEAR}/{m:02d}/{d:02d}" for m,d in _BASE_HOLIDAYS) if official_holidays else []
    ignored=checked(holidays or [])
    extra=checked(extra_holidays or [])
    return {
        "start_date":start_date,
        "working_weekdays":weekdays,
        "holiday_source":_SOURCE if official_holidays else None,
        "reference_year":_YEAR,
        "nationwide_holidays":fixed,
        "additional_site_holidays":extra,
        "working_day_exceptions":ignored,
        "approved":False,
        "warning":"تقویم پیش‌نویس است؛ تعطیلی اضطراری/استانی و تعطیلات قمری باید توسط مدیر پروژه کنترل شوند",
    }


def apply_calendar(plan):
    """Place exclusive working-day offsets on a Jalali YYYY/MM/DD axis.

    A zero-day milestone has a date but consumes no working days. A task end
    date is the last working day actually executed; its exclusive finish
    offset is retained in the source WBS. No date beyond reviewed 1405.
    """
    calendar=plan.get("calendar")
    if not isinstance(calendar,dict):raise ValueError("تقویم برنامه نامعتبر است")
    start=calendar.get("start_date")
    if not start:
        return plan
    _parse_solar(start)
    work=set(calendar.get("working_weekdays",[]))
    if not work:raise ValueError("روزهای کاری تعیین نشده‌اند")
    off=set(calendar.get("nationwide_holidays",[]))|set(calendar.get("additional_site_holidays",[]))
    excepts=set(calendar.get("working_day_exceptions",[]))
    if not excepts.issubset(off):
        raise ValueError("روزهای استثنایی باید از فهرست تعطیلی‌های واقعی انتخاب شوند")
    # Convert all declared holiday dates first so corrupted calendar inputs
    # never silently disappear during a long project schedule.
    for x in off|excepts:_parse_solar(x)
    start_date=gregorian_1405(start)
    day_map=[]
    current=start_date
    count=max((task.get("end_workday_offset",0) for task in plan.get("tasks",[])),default=0)
    while len(day_map)<=count:
        if current>=_ANCHOR+timedelta(days=sum(_MONTH_LENGTHS)):
            raise ValueError("پروژه از سال ۱۴۰۵ عبور کرد؛ تقویم سال جدید باید بارگذاری شود")
        day=solar_1405(current)
        if current.weekday() in work and (day not in off or day in excepts):
            day_map.append(day)
        current+=timedelta(days=1)
    for task in plan.get("tasks",[]):
        start_i=task["start_workday_offset"]
        end_i=task["end_workday_offset"]
        task["start_jalali"]=day_map[start_i]
        task["finish_jalali"]=day_map[end_i-1] if end_i>start_i else day_map[start_i]
    plan["scheduled_end_jalali"]=day_map[count-1] if count else day_map[0]
    plan["calendar_approved"]=False
    return plan


def calendarize(plan,calendar):
    out=deepcopy(plan)
    out["calendar"]=deepcopy(calendar)
    if out.get("resource_leveling_status")!="PROPOSED_UNAPPROVED":
        calculate_precedence(out)
    # Calendar placement must preserve resource-feasible offsets when the
    # user only changes the calendar/holiday overlay.
    apply_calendar(out)
    return out
