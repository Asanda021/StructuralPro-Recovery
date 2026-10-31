"""Source-attributed nationwide Iranian public holiday proposals for 1405..1410.

Solar fixed dates are deterministic; lunar Hijri observances move and must be
reconciled with the official calendar and crescent announcement before the
project baseline is approved. Source Makanet year/month listings:
https://makanet.ir/time/holidays/ (1405)
https://makanet.ir/time/holidays/1406/
https://makanet.ir/time/holidays/1407/
https://makanet.ir/time/holidays/1408/
https://makanet.ir/time/month/1409/
https://makanet.ir/time/month/1410/
The 1408–1410 lunar dates are predictions (±1–2 days), NOT official law.
"""
from __future__ import annotations

YEAR_SOURCE={
    1405:"https://makanet.ir/time/holidays/",
    1406:"https://makanet.ir/time/holidays/1406/",
    1407:"https://makanet.ir/time/holidays/1407/",
    1408:"https://makanet.ir/time/holidays/1408/",
    1409:"https://makanet.ir/time/month/1409/",
    1410:"https://makanet.ir/time/month/1410/",
}
SOLAR_FIXED={
    "01/01":"نوروز","01/02":"نوروز","01/03":"نوروز",
    "01/04":"نوروز","01/12":"روز جمهوری اسلامی",
    "01/13":"روز طبیعت","03/14":"رحلت امام خمینی",
    "03/15":"قیام پانزدهم خرداد","11/22":"پیروزی انقلاب اسلامی",
    "12/29":"ملی شدن صنعت نفت",
}
# The exact lunar occurrences listed by Makanet for 1405/1406/1407; each
# entry is explicitly classified as source-published, still adjustable when
# Iran's competent calendar authority issues a correction.
# Two Eid al-Fitr occurrences may legitimately fall inside one Solar year.
_LUNAR={
1405: """
01/01|عید فطر
01/02|دوم عید فطر
01/25|شهادت امام جعفر صادق
03/06|عید قربان
03/14|عید غدیر
04/03|تاسوعا
04/04|عاشورا
05/13|اربعین
05/21|رحلت پیامبر و شهادت امام حسن
05/22|شهادت امام رضا
05/30|شهادت امام حسن عسکری
06/08|میلاد پیامبر و امام صادق
08/22|شهادت حضرت فاطمه زهرا
09/09|ولادت حضرت فاطمه زهرا
10/02|ولادت امام علی
10/14|شهادت امام موسی کاظم
10/16|مبعث پیامبر
11/04|نیمه شعبان
12/09|شهادت امام علی
12/19|عید فطر
12/20|دوم عید فطر
""",
1406: """
01/14|شهادت امام جعفر صادق
02/27|عید قربان
03/04|عید غدیر
03/25|تاسوعا
03/26|عاشورا
05/03|اربعین
05/11|رحلت پیامبر و شهادت امام حسن
05/12|شهادت امام رضا
05/20|شهادت امام حسن عسکری
05/29|میلاد پیامبر و امام صادق
08/12|شهادت حضرت فاطمه زهرا
08/29|ولادت حضرت فاطمه زهرا
09/21|ولادت امام علی
10/03|شهادت امام موسی کاظم
10/05|مبعث پیامبر
10/23|نیمه شعبان
11/29|شهادت امام علی
12/08|عید فطر
12/09|دوم عید فطر
""",
1407: """
01/03|شهادت امام جعفر صادق
02/17|عید قربان
02/25|عید غدیر
03/14|تاسوعا
03/15|عاشورا
04/24|اربعین
05/01|رحلت پیامبر و شهادت امام حسن
05/02|شهادت امام رضا
05/10|شهادت امام حسن عسکری
05/19|میلاد پیامبر و امام صادق
08/01|شهادت حضرت فاطمه زهرا
08/18|ولادت حضرت فاطمه زهرا
09/11|ولادت امام علی
09/23|شهادت امام موسی کاظم
09/25|مبعث پیامبر
10/12|نیمه شعبان
11/18|شهادت امام علی
11/27|عید فطر
11/28|دوم عید فطر
12/21|شهادت امام جعفر صادق
""",
1408: """
02/05|عید قربان
02/13|عید غدیر
03/03|تاسوعا
03/04|عاشورا
04/13|اربعین
04/21|رحلت پیامبر و شهادت امام حسن
04/22|شهادت امام رضا
04/30|شهادت امام حسن عسکری
05/08|میلاد پیامبر و امام صادق
07/21|شهادت حضرت فاطمه زهرا
08/08|ولادت حضرت فاطمه زهرا
08/30|ولادت امام علی
09/12|شهادت امام موسی کاظم
09/14|مبعث پیامبر
10/02|نیمه شعبان
11/07|شهادت امام علی
11/17|عید فطر
11/18|دوم عید فطر
12/11|شهادت امام جعفر صادق
""",
1409: """
01/25|عید قربان
02/02|عید غدیر
02/22|تاسوعا
02/23|عاشورا
04/01|اربعین
04/09|رحلت پیامبر و شهادت امام حسن
04/10|شهادت امام رضا
04/18|شهادت امام حسن عسکری
04/27|میلاد پیامبر و امام صادق
07/09|شهادت حضرت فاطمه زهرا
07/26|ولادت حضرت فاطمه زهرا
08/18|ولادت امام علی
08/30|شهادت امام موسی کاظم
09/02|مبعث پیامبر
09/20|نیمه شعبان
10/25|شهادت امام علی
11/05|عید فطر
11/06|دوم عید فطر
11/29|شهادت امام جعفر صادق
""",
1410: """
01/14|عید قربان
01/22|عید غدیر
02/11|تاسوعا
02/12|عاشورا
03/21|اربعین
03/29|رحلت پیامبر و شهادت امام حسن
03/30|شهادت امام رضا
04/07|شهادت امام حسن عسکری
04/16|میلاد پیامبر و امام صادق
06/29|شهادت حضرت فاطمه زهرا
07/15|ولادت حضرت فاطمه زهرا
08/07|ولادت امام علی
08/19|شهادت امام موسی کاظم
08/21|مبعث پیامبر
09/09|نیمه شعبان
10/14|شهادت امام علی
10/24|عید فطر
10/25|دوم عید فطر
11/18|شهادت امام جعفر صادق
""",
}
OFFICIAL_LUNAR_NAMES={
    "عید فطر","دوم عید فطر","شهادت امام جعفر صادق",
    "عید قربان","عید غدیر","تاسوعا","عاشورا","اربعین",
    "رحلت پیامبر و شهادت امام حسن","شهادت امام رضا",
    "شهادت امام حسن عسکری","میلاد پیامبر و امام صادق",
    "شهادت حضرت فاطمه زهرا","ولادت امام علی",
    "مبعث پیامبر","نیمه شعبان","شهادت امام علی",
}
def listed_holidays(year):
    """Returns every named holiday separately; duplicate-date events preserved."""
    if type(year) is not int or year not in YEAR_SOURCE:
        return []
    status="PUBLISHED_CALENDAR_REVIEWABLE" if year<=1407 else "PREDICTED_LUNAR_NOT_OFFICIAL"
    events=[{"date":f"{year:04d}/{monthday}","name":name,
             "kind":"solar_fixed","status":"FIXED_SOLAR",
             "source":YEAR_SOURCE[year]} for monthday,name in SOLAR_FIXED.items()]
    for line in _LUNAR[year].strip().splitlines():
        date_suffix,name=line.split("|",1)
        if name.strip() not in OFFICIAL_LUNAR_NAMES:
            continue  # A religious occasion is not automatically a public holiday.
        events.append({"date":f"{year:04d}/{date_suffix.strip()}",
                       "name":name.strip(),"kind":"lunar",
                       "status":status,"source":YEAR_SOURCE[year]})
    return sorted(events,key=lambda e:(e["date"],e["name"]))
