"""Evidence-based, project-specific crew productivity calibration.

Scientific studies about Iranian labour productivity establish variability,
not a universally valid m2/day for every worksite. This module therefore
requires real observed output, crew counts, shifts and immutable evidence;
it NEVER promotes unobserved template rates to official field measurements.
"""
from __future__ import annotations
from decimal import Decimal,InvalidOperation,ROUND_CEILING
from hashlib import file_digest
from pathlib import Path
from statistics import median

from core.projects.production_catalog import CATALOG,normalized_production_unit


def _num(value,label):
    if isinstance(value,bool):raise ValueError(label+" نباید bool باشد")
    try: d=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError) as e:
        raise ValueError(label+" معتبر نیست") from e
    if not d.is_finite() or d<=0:raise ValueError(label+" باید مثبت و محدود باشد")
    return d


def _fingerprint(path):
    p=Path(path).expanduser().resolve(strict=True)
    if not p.is_file() or p.stat().st_size>100*1024*1024:
        raise ValueError("مدرک عملکرد کارگاه قابل استناد نیست")
    with p.open("rb") as f:
        return {"path":str(p),"sha256":file_digest(f,"sha256").hexdigest()}


def calibrate_productivity(profile_code, observations,*,reviewer,project_id):
    """Return a new user-reviewed project-specific rate range, not mutate global library.

    Each observation must have actual quantity, unit, working days, crews and
    the original file. No result if fewer than 3 independent dated records.
    """
    if profile_code not in CATALOG:raise ValueError("آیتم تولید در بانک وجود ندارد")
    if not isinstance(observations,list) or len(observations)<3:
        raise ValueError("برای کالیبراسیون حداقل ۳ مشاهده مستقل لازم است")
    if not str(reviewer).strip() or not str(project_id).strip():
        raise ValueError("پروژه و نام بازبین فنی الزامی است")
    expected_unit=CATALOG[profile_code].unit
    observed=[]
    fingerprints=[]
    dates=set()
    for row in observations:
        if not isinstance(row,dict):raise ValueError("مشاهده عملکرد نامعتبر است")
        day=str(row.get("observed_on",""))
        if day in dates or not day or len(day)>20:
            raise ValueError("تاریخ مشاهدات باید مستقل و یکتا باشد")
        dates.add(day)
        if normalized_production_unit(row.get("unit"))!=expected_unit:
            raise ValueError("واحد مشاهده با پروفایل متره مطابقت ندارد")
        q=_num(row.get("quantity"),"کمیت اجراشده")
        elapsed=_num(row.get("workdays"),"روزهای کاری")
        crews=_num(row.get("crews"),"تعداد اکیپ")
        if crews!=int(crews) or crews>100:
            raise ValueError("تعداد اکیپ صحیح معتبر لازم است")
        if elapsed>3650:raise ValueError("دوره مشاهده غیرمعمول است")
        record=_fingerprint(row.get("source_path",""))
        fingerprints.append({**record,"observed_on":day})
        observed.append(q/(elapsed*crews))
    low=min(observed)
    high=max(observed)
    central=Decimal(str(median(observed)))
    return {
        "schema":"structuralpro.project-productivity-calibration-v1",
        "profile_code":profile_code,"unit":expected_unit,
        "project_id":str(project_id),"reviewed_by":str(reviewer).strip(),
        "status":"PROJECT_OBSERVED_REVIEW_ONLY",
        "observation_count":len(observed),
        "low_per_crew_day":str(low),"median_per_crew_day":str(central),
        "high_per_crew_day":str(high),
        "source_documents":fingerprints,
        "warning":"خروجی محدود به شرایط و اکیپ پروژه بوده و خودبه‌خود مبنای قطعی زمان‌بندی نیست",
    }


def validate_calibration(calibration,profile_code,project_id):
    if not isinstance(calibration,dict) or calibration.get("schema")!="structuralpro.project-productivity-calibration-v1":
        raise ValueError("قالب کالیبراسیون معتبر نیست")
    if (calibration.get("profile_code")!=profile_code
            or calibration.get("project_id")!=project_id
            or calibration.get("observation_count",0)<3
            or calibration.get("status")!="PROJECT_OBSERVED_REVIEW_ONLY"):
        raise ValueError("کالیبراسیون متعلق به این پروژه و آیتم نیست")
    fingerprints=calibration.get("source_documents",[])
    if len(fingerprints)!=calibration["observation_count"]:
        raise ValueError("شواهد کالیبراسیون ناقص است")
    for f in fingerprints:
        if _fingerprint(f.get("path"))["sha256"]!=f.get("sha256"):
            raise ValueError("فایل شاهد عملکرد تغییر کرده است")
    return calibration


def calibrated_duration(calibration,quantity,*,crews=1,efficiency="1"):
    q=_num(quantity,"مقدار متره")
    c=_num(crews,"تعداد اکیپ")
    e=_num(efficiency,"ضریب بهره‌وری")
    if c!=int(c) or c>100 or not Decimal("0.1")<=e<=Decimal("2"):
        raise ValueError("پارامتر اکیپ/بهره‌وری معتبر نیست")
    low=_num(calibration["low_per_crew_day"],"نرخ مشاهده")
    high=_num(calibration["high_per_crew_day"],"نرخ مشاهده")
    mid=_num(calibration["median_per_crew_day"],"نرخ مشاهده")
    if not low<=mid<=high:raise ValueError("دامنه نرخ مشاهده ناسازگار است")
    def days(rate):return int((q/(rate*c*e)).to_integral_value(rounding=ROUND_CEILING))
    return {
        "min_workdays":days(high),"expected_workdays":days(mid),
        "max_workdays":days(low),
        "status":"PROJECT_OBSERVED_REQUIRES_BASELINE_APPROVAL",
        "observation_count":calibration["observation_count"],
    }
