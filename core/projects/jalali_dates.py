"""Dependency-free modern Iranian Jalali date conversion.

Borkowski break-year method, ported from the MIT-licensed jalaali-js
implementation (https://github.com/jalaali/jalaali-js).  This arithmetic
is valid through Jalali year 3177; it does not expire at 1410. Official
future equinox announcements may require a review at exceptional edges.
"""
from __future__ import annotations
from datetime import date,timedelta
from functools import lru_cache

_BREAKS=(-61,9,38,199,426,686,756,818,1111,1181,1210,1635,
         2060,2097,2192,2262,2324,2394,2456,3178)

def _trunc(n,d):
    return int(n/d)

def _mod(n,d):
    return n-_trunc(n,d)*d

@lru_cache(maxsize=512)
def _jal_cal(jy):
    if type(jy) is not int or not 1<=jy<3178:
        raise ValueError("سال خارج از محدوده قابل تبدیل تقویم شمسی است")
    gy=jy+621
    leap_j=-14
    jp=_BREAKS[0]
    jump=0
    for jm in _BREAKS[1:]:
        jump=jm-jp
        if jy<jm:
            break
        leap_j+=_trunc(jump,33)*8+_trunc(_mod(jump,33),4)
        jp=jm
    n=jy-jp
    leap_j+=_trunc(n,33)*8+_trunc(_mod(n,33)+3,4)
    if _mod(jump,33)==4 and jump-n==4:
        leap_j+=1
    leap_g=_trunc(gy,4)-_trunc((_trunc(gy,100)+1)*3,4)-150
    march=20+leap_j-leap_g
    if jump-n<6:
        n=n-jump+_trunc(jump+4,33)*33
    leap=_mod(_mod(n+1,33)-1,4)
    if leap==-1:
        leap=4
    return date(gy,3,march),leap

def is_leap_jalali(year):
    return _jal_cal(year)[1]==0

def month_lengths(year):
    return (31,)*6+(30,)*5+(30 if is_leap_jalali(year) else 29,)

def parse_jalali(value):
    if not isinstance(value,str):
        raise ValueError("تاریخ شمسی باید YYYY/MM/DD باشد")
    digits=str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
                         "01234567890123456789")
    parts=value.translate(digits).replace("-","/").split("/")
    if len(parts)!=3 or any(not p.isascii() or not p.isdigit() for p in parts):
        raise ValueError("تاریخ شمسی باید YYYY/MM/DD باشد")
    y,m,d=map(int,parts)
    lengths=month_lengths(y)
    if not 1<=m<=12 or not 1<=d<=lengths[m-1]:
        raise ValueError("روز یا ماه شمسی نامعتبر است")
    return y,m,d

def jalali_to_gregorian(value):
    y,m,d=parse_jalali(value)
    return _jal_cal(y)[0]+timedelta(days=sum(month_lengths(y)[:m-1])+d-1)

def gregorian_to_jalali(value):
    if not isinstance(value,date) or isinstance(value, __import__("datetime").datetime):
        raise ValueError("تاریخ میلادی باید روز تقویمی باشد")
    y=value.year-621
    for candidate in (y-1,y,y+1):
        if not 1<=candidate<3178:continue
        first=_jal_cal(candidate)[0]
        following=_jal_cal(candidate+1)[0]
        if first<=value<following:
            remaining=(value-first).days
            for month,size in enumerate(month_lengths(candidate),1):
                if remaining<size:
                    return f"{candidate:04d}/{month:02d}/{remaining+1:02d}"
                remaining-=size
    raise ValueError("تاریخ خارج از محدوده تقویم شمسی پشتیبانی‌شده است")
