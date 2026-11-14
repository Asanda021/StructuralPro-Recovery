"""Long-lived Jalali construction calendar with source-verified 1405–1410 holidays.

Fixed solar holidays are arithmetic. Lunar holidays in 1408–1410 are
explicitly source-based *forecasts* (subject to moon sighting), not silently
passed as final legal holidays. The calendar works beyond 1410 and supports
reviewed project holiday imports for any supported future year.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date,timedelta
from core.projects.jalali_dates import (
    parse_jalali,jalali_to_gregorian,gregorian_to_jalali,month_lengths,
)
from core.projects.iran_holiday_seeds import (
    YEAR_SOURCE,SOLAR_FIXED,listed_holidays,
)
from core.projects.precedence_model import calculate_precedence

MIN_YEAR=1405
MAX_YEAR=1410 # last INCLUDED preset holiday year, not expiration
_YEAR=1405
_SOURCE="https://makanet.ir/time/holidays/"
_YEAR_STARTS={
    year:jalali_to_gregorian(f"{year:04d}/01/01")
    for year in range(MIN_YEAR,MAX_YEAR+2)
}
_MONTH_LENGTHS=month_lengths(1405)
_BASE_HOLIDAYS={
    (int(entry["date"][5:7]),int(entry["date"][8:]))
    for entry in listed_holidays(1405)
}
_FIXED_SOLAR_HOLIDAYS={
    (int(key[:2]),int(key[3:]))
    for key in SOLAR_FIXED
}


def _parse_solar(value):
    return parse_jalali(value)


def _solar(y,m,d):
    return f"{y:04d}/{m:02d}/{d:02d}"


def gregorian_1405(solar):
    """Historical alias: conversion has no hard end in 1410."""
    return jalali_to_gregorian(solar)


def solar_1405(gregorian):
    """Historical alias: conversion has no hard end in 1410."""
    return gregorian_to_jalali(gregorian)


def _validate_dates(values):
    return sorted({_solar(*parse_jalali(v)) for v in values})


def _reviewed_holidays_input(value):
    if value is None:return {}
    if not isinstance(value,dict):
        raise ValueError("تعطیلات بازبینی‌شده باید سال‌به‌سال و در جدول باشند")
    result={}
    for key,rows in value.items():
        try: year=int(key)
        except (ValueError,TypeError):raise ValueError("سال تعطیلات بازبینی‌شده نامعتبر است")
        if year<1 or year>=3178 or not isinstance(rows,list):
            raise ValueError("سال یا لیست تعطیلات نامعتبر است")
        values=_validate_dates(rows)
        if any(parse_jalali(day)[0]!=year for day in values):
            raise ValueError("تاریخ تعطیلی با سال اعلام‌شده مطابقت ندارد")
        result[year]=values
    return result


def make_calendar(*,start_date=None,holidays=None,extra_holidays=None,
                  working_weekdays=(0,1,2,3,5,6),official_holidays=True,
                  reviewed_future_holidays=None,forecast_lunar=True):
    """Build documented holiday sets: 1405–1410 preset, future-year extensible.

    Reviewed future lists override forecast *lunar* events only for that year;
    fixed solar nationwide holidays remain mandatory unless overridden by
    project workday exceptions. Friday is already represented in weekdays.
    """
    weekdays=list(working_weekdays)
    if (not weekdays or len(set(weekdays))!=len(weekdays) or
            any(type(x) is not int or not 0<=x<=6 for x in weekdays)):
        raise ValueError("روزهای کاری باید از هفته و بدون تکرار انتخاب شوند")
    start=_solar(*parse_jalali(start_date)) if start_date is not None else None
    reviewed=_reviewed_holidays_input(reviewed_future_holidays)
    seeded=[]
    sources={}
    review_years=[]
    holiday_events=[]
    if official_holidays:
        for year in range(MIN_YEAR,MAX_YEAR+1):
            records=listed_holidays(year)
            if year in reviewed:
                records=[x for x in records if x["kind"]=="solar_fixed"]
                records.extend(
                    {"date":day,"name":"تعطیلی مصوب واردشده توسط مدیر پروژه",
                     "kind":"lunar_or_special_reviewed","status":"USER_REVIEWED",
                     "source":"USER_YEAR_SPECIFIC"} for day in reviewed[year]
                )
                sources[str(year)]="USER_YEAR_SPECIFIC"
            else:
                if not forecast_lunar and year>=1406:
                    records=[x for x in records if x["kind"]=="solar_fixed"]
                if year>=1406:
                    review_years.append(year)
                sources[str(year)]=YEAR_SOURCE[year]
            seeded.extend(x["date"] for x in records)
            holiday_events.extend(records)
    ignored=_validate_dates(holidays or [])
    extra=_validate_dates(extra_holidays or [])
    fixed=_validate_dates(seeded)
    if not set(ignored).issubset(set(fixed)|set(extra)):
        raise ValueError("روز کاری استثنایی باید یکی از تعطیلات معرفی‌شده باشد")
    return {
        "start_date":start,"working_weekdays":weekdays,
        "reference_year":MIN_YEAR,"supported_years":[MIN_YEAR,MAX_YEAR],
        "calendar_expiration":None,
        "holiday_source":_SOURCE if official_holidays else None,
        "nationwide_holidays":fixed,
        "holiday_events":holiday_events,
        "additional_site_holidays":extra,
        "working_day_exceptions":ignored,
        "future_holidays_review_required":review_years,
        "year_sources":sources,
        "reviewed_year_holidays":{str(y):x for y,x in reviewed.items()},
        "official_holidays_enabled":bool(official_holidays),
        "include_lunar_forecasts":bool(forecast_lunar),
        "approved":False,
        "warning":"تقویم فاقد انقضای ۱۴۱۰ است؛ تعطیلی قمری پیش‌بینی‌شده و تعطیلات پس از ۱۴۱۰ نیازمند تأیید سالانه‌اند",
    }


def _calendar_holiday_sets(calendar,year):
    off=set(calendar.get("nationwide_holidays",[]))
    off.update(calendar.get("additional_site_holidays",[]))
    if not calendar.get("official_holidays_enabled",True):
        return off,False
    if year>MAX_YEAR or year<MIN_YEAR:
        off.update(f"{year:04d}/{key}" for key in SOLAR_FIXED)
        # User-reviewed year-specific overrides are still valid beyond 1410.
        reviewed=calendar.get("reviewed_year_holidays",{})
        if str(year) in reviewed:
            off.update(reviewed[str(year)])
            return off,False
        return off,True
    return off,(year in calendar.get("future_holidays_review_required",[]))


def apply_calendar(plan):
    calendar=plan.get("calendar")
    if not isinstance(calendar,dict):raise ValueError("تقویم پروژه معتبر نیست")
    start=calendar.get("start_date")
    if not start:return plan
    first=jalali_to_gregorian(start)
    work=calendar.get("working_weekdays",[])
    if (not isinstance(work,list) or not work or
            any(type(x) is not int or not 0<=x<=6 for x in work)):
        raise ValueError("روزهای کاری معتبر نیستند")
    exception=set(_validate_dates(calendar.get("working_day_exceptions",[])))
    site=set(_validate_dates(calendar.get("additional_site_holidays",[])))
    count=max((t.get("end_workday_offset",0) for t in plan.get("tasks",[])),default=0)
    if type(count) is not int or not 0<=count<=3650:
        raise ValueError("بازه فعالیت‌ها معتبر نیست")
    day_map=[]
    cursor=first
    unreviewed=set()
    while len(day_map)<=count:
        jalali=gregorian_to_jalali(cursor)
        year=int(jalali[:4])
        days_off,needs_review=_calendar_holiday_sets(calendar,year)
        # Some holiday corrections for future years cannot be magically
        # predicted: expose them in plan metadata, never invent a final date.
        if needs_review:
            unreviewed.add(year)
        if cursor.weekday() in work and (jalali not in days_off or jalali in exception):
            day_map.append(jalali)
        cursor+=timedelta(days=1)
    for task in plan.get("tasks",[]):
        start_index=task["start_workday_offset"]
        end_index=task["end_workday_offset"]
        task["start_jalali"]=day_map[start_index]
        task["finish_jalali"]=(
            day_map[end_index-1] if end_index>start_index else day_map[start_index]
        )
    plan["scheduled_end_jalali"] = max(
        (task["finish_jalali"] for task in plan.get("tasks", [])), default=day_map[0]
    )
    plan["unreviewed_holiday_years"]=sorted(unreviewed)
    plan["calendar_approved"]=bool(calendar.get("approved")) and not unreviewed
    plan["calendar_holiday_revision_required"]=bool(unreviewed)
    return plan


def calendarize(plan,calendar):
    out=deepcopy(plan)
    out["calendar"]=deepcopy(calendar)
    if out.get("resource_leveling_status")!="PROPOSED_UNAPPROVED":
        calculate_precedence(out)
    apply_calendar(out)
    return out
