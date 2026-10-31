"""Multi-year Jalali worksite calendar 1405–1410, with reviewed holiday provenance.

Gregorian correspondence and leap-year length are deterministic. Lunar and
one-off future holidays are NOT official until separately validated/imported.
Partial public-holiday data is explicitly disclosed, not silently complete.
"""
from __future__ import annotations
from datetime import date,timedelta
from copy import deepcopy
from bisect import bisect_right
from core.projects.precedence_model import calculate_precedence

MIN_YEAR=1405
MAX_YEAR=1410
_YEAR=MIN_YEAR  # compatibility with earlier 1405-only importers
_SOURCE_1405="https://timestamp.ir/holidays-list"
_FUTURE_NOTICE="https://makanet.ir/time/month/"
_YEAR_STARTS={
    1405:date(2026,3,21),
    1406:date(2027,3,21),
    1407:date(2028,3,20),
    1408:date(2029,3,20),
    1409:date(2030,3,21),
    1410:date(2031,3,21),
    1411:date(2032,3,20),  # upper endpoint only; not a supported year
}
# Retain the original reviewed 1405 dataset for compatibility. Dates of
# lunar festivals must NOT be mechanically carried into future years.
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
# Dates that are solar-fixed, rather than year-dependent lunar celebrations.
# Future official lunar dates, provincial closures and legal changes require
# their OWN reviewed year files before a baseline is approved.
_FIXED_SOLAR_HOLIDAYS={
    (1,1),(1,2),(1,3),(1,4),(1,12),(1,13),
    (3,14),(3,15),(11,22),(12,29),
}


def _month_lengths(year):
    if year not in range(MIN_YEAR,MAX_YEAR+1):
        raise ValueError("سال باید بین ۱۴۰۵ تا ۱۴۱۰ باشد")
    leap=(_YEAR_STARTS[year+1]-_YEAR_STARTS[year]).days==366
    return (31,)*6+(30,)*5+(30 if leap else 29,)


def _parse_solar(value):
    if not isinstance(value,str):
        raise ValueError("تاریخ شمسی باید YYYY/MM/DD باشد")
    digits=str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")
    parts=value.translate(digits).replace("-","/").split("/")
    if len(parts)!=3 or any(not x.isascii() or not x.isdigit() for x in parts):
        raise ValueError("تاریخ شمسی باید YYYY/MM/DD باشد")
    year,month,day=map(int,parts)
    if not MIN_YEAR<=year<=MAX_YEAR:
        raise ValueError("تاریخ خارج از محدوده ۱۴۰۵ تا ۱۴۱۰ است")
    if not 1<=month<=12 or not 1<=day<=_month_lengths(year)[month-1]:
        raise ValueError("روز یا ماه شمسی نامعتبر است")
    return year,month,day


def _solar(year,month,day):
    return f"{year:04d}/{month:02d}/{day:02d}"


def gregorian_1405(solar):
    """Historical public function now accepts all 1405..1410 years."""
    y,m,d=_parse_solar(solar)
    return _YEAR_STARTS[y]+timedelta(days=sum(_month_lengths(y)[:m-1])+d-1)


def solar_1405(gregorian):
    """Historical public function now supports dates through Esfand 1410."""
    if not isinstance(gregorian,date) or not _YEAR_STARTS[MIN_YEAR]<=gregorian<_YEAR_STARTS[MAX_YEAR+1]:
        raise ValueError("میلادی خارج از تقویم ۱۴۰۵ تا ۱۴۱۰ است")
    ys=list(_YEAR_STARTS)
    start_dates=[_YEAR_STARTS[y] for y in ys]
    year=ys[bisect_right(start_dates,gregorian)-1]
    offset=(gregorian-_YEAR_STARTS[year]).days
    for month,length in enumerate(_month_lengths(year),1):
        if offset<length:return _solar(year,month,offset+1)
        offset-=length
    raise ValueError("روز خورشیدی در محدوده سال نیست")


def _validate_dates(values):
    normalized=set()
    for value in values:
        normalized.add(_solar(*_parse_solar(value)))
    return sorted(normalized)


def make_calendar(*,start_date=None,holidays=None,extra_holidays=None,
                  working_weekdays=(0,1,2,3,5,6),official_holidays=True,
                  reviewed_future_holidays=None):
    """Mon=0...Sun=6. Iranian workweek usually excludes Friday=4.

    reviewed_future_holidays: explicit year-tagged approved date lists imported
    by the responsible engineer. The caller must not invent a future dataset.
    """
    days=list(working_weekdays)
    if not days or len(set(days))!=len(days) or any(type(d) is not int or d not in range(7) for d in days):
        raise ValueError("روزهای کاری معتبر بین شنبه و پنجشنبه انتخاب شوند")
    start=(_solar(*_parse_solar(start_date)) if start_date is not None else None)
    reviewed=reviewed_future_holidays or {}
    if not isinstance(reviewed,dict):
        raise ValueError("تعطیلات بازبینی‌شده باید برای هر سال مجزا باشد")
    for key,values in reviewed.items():
        try: year=int(key)
        except (TypeError,ValueError):raise ValueError("سال تعطیلات بازبینی‌شده نامعتبر است")
        if year not in range(MIN_YEAR,MAX_YEAR+1) or not isinstance(values,list):
            raise ValueError("فهرست تعطیلات بازبینی‌شده نامعتبر است")
        if any(_parse_solar(x)[0]!=year for x in values):
            raise ValueError("سال تاریخ تعطیلات با سال فهرست یکسان نیست")
    base=[]
    review_required=[]
    sources={}
    if official_holidays:
        for year in range(MIN_YEAR,MAX_YEAR+1):
            if year==MIN_YEAR:
                entries=_BASE_HOLIDAYS
                sources[str(year)]=_SOURCE_1405
            elif str(year) in reviewed or year in reviewed:
                entries={(m,d) for _,m,d in (_parse_solar(v) for v in reviewed.get(str(year),reviewed.get(year,[])))}
                entries|=_FIXED_SOLAR_HOLIDAYS
                sources[str(year)]="USER_REVIEWED_YEAR_SPECIFIC"
            else:
                entries=_FIXED_SOLAR_HOLIDAYS
                review_required.append(year)
                sources[str(year)]="SOLAR_FIXED_ONLY_LUNAR_AND_SPECIAL_MISSING"
            base.extend(_solar(year,m,d) for m,d in entries if d<=_month_lengths(year)[m-1])
    ignored=_validate_dates(holidays or [])
    extra=_validate_dates(extra_holidays or [])
    all_base=_validate_dates(base)
    if not set(ignored).issubset(set(all_base)|set(extra)):
        raise ValueError("استثنای روز کاری باید یکی از تعطیلی‌ها باشد")
    return {
        "start_date":start,"working_weekdays":days,
        "holiday_source":_SOURCE_1405 if official_holidays else None,
        "reference_year":MIN_YEAR,"supported_years":[MIN_YEAR,MAX_YEAR],
        "nationwide_holidays":all_base,
        "additional_site_holidays":extra,
        "working_day_exceptions":ignored,
        "future_holidays_review_required":review_required,
        "year_sources":sources,
        "approved":False,
        "warning":"تقویم پیش‌نویس است؛ تعطیلی‌های قمری/موردی سال‌های آتی و بخشنامه‌های استانی باید جداگانه بازبینی شوند",
    }


def apply_calendar(plan):
    calendar=plan.get("calendar")
    if not isinstance(calendar,dict):raise ValueError("تقویم برنامه نامعتبر است")
    start=calendar.get("start_date")
    if not start:return plan
    start_dt=gregorian_1405(start)
    week=calendar.get("working_weekdays",[])
    if not isinstance(week,list) or not week or any(type(x) is not int or x not in range(7) for x in week):
        raise ValueError("روزهای کاری پروژه معتبر نیست")
    off=set(_validate_dates(calendar.get("nationwide_holidays",[])))|set(
        _validate_dates(calendar.get("additional_site_holidays",[])))
    exceptions=set(_validate_dates(calendar.get("working_day_exceptions",[])))
    if not exceptions.issubset(off):
        raise ValueError("روزهای استثنا باید در تعطیلات تعریف شده باشند")
    count=max((t.get("end_workday_offset",0) for t in plan.get("tasks",[])),default=0)
    days=[]
    cursor=start_dt
    while len(days)<=count:
        if cursor>=_YEAR_STARTS[MAX_YEAR+1]:
            raise ValueError("پروژه از انتهای ۱۴۱۰ عبور کرده؛ تقویم سال جدید لازم است")
        day=solar_1405(cursor)
        if cursor.weekday() in week and (day not in off or day in exceptions):
            days.append(day)
        cursor+=timedelta(days=1)
    for task in plan.get("tasks",[]):
        i=task["start_workday_offset"];end=task["end_workday_offset"]
        task["start_jalali"]=days[i]
        task["finish_jalali"]=days[end-1] if end>i else days[i]
    plan["scheduled_end_jalali"]=days[count-1] if count else days[0]
    covered={int(value[:4]) for value in days}
    pending=set(calendar.get("future_holidays_review_required",[]))&covered
    plan["calendar_approved"]=bool(calendar.get("approved")) and not pending
    plan["unreviewed_holiday_years"]=sorted(pending)
    return plan


def calendarize(plan,calendar):
    out=deepcopy(plan)
    out["calendar"]=deepcopy(calendar)
    if out.get("resource_leveling_status")!="PROPOSED_UNAPPROVED":
        calculate_precedence(out)
    apply_calendar(out)
    return out
