"""Indicative construction productivity catalog for the editable WBS.

IMPORTANT: No number is an official Iranian production standard. Sources
are marked per row; secondary compiled estimates and internal seed
assumptions require adjustment to site, crew, access and equipment.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING

REF_CMU="https://www.cmu.edu/cee/projects/PMbook/09_Construction_Planning.html"
REF_PMI="https://www.pmi.org/learning/library/schedule-101-basic-best-practices-6701"
REF_ORACLE="https://docs.oracle.com/cd/F74773_01/p6help/en/6616.htm"
REF_SECONDARY="https://www.infralens.in/handbook/labour-productivity"
REF_OFFICE="INTERNAL_STARTING_ASSUMPTION_NOT_A_STANDARD"

@dataclass(frozen=True)
class ProductionProfile:
    code:str
    discipline:str
    title:str
    unit:str
    low_per_crew_day:str
    high_per_crew_day:str
    crews:int
    predecessor:str
    relation:str
    lag_days:int
    rate_source:str
    keywords:tuple[str,...]

_RAW=[
 [
  "excavation_manual",
  "structure",
  "گودبرداری دستی",
  "m3",
  2,
  4,
  2,
  "mobilize",
  "FS",
  0,
  "office",
  [
   "گودبرداری دستی",
   "خاکبرداری دستی"
  ]
 ],
 [
  "excavation_machine",
  "structure",
  "گودبرداری مکانیکی",
  "m3",
  60,
  150,
  1,
  "mobilize",
  "FS",
  0,
  "office",
  [
   "گودبرداری مکانیکی",
   "خاکبرداری مکانیکی"
  ]
 ],
 [
  "backfill",
  "structure",
  "خاکریزی و تراکم",
  "m3",
  10,
  30,
  1,
  "foundation",
  "FS",
  0,
  "office",
  [
   "خاکریزی",
   "بکفیل"
  ]
 ],
 [
  "blinding",
  "structure",
  "بتن مگر",
  "m3",
  10,
  20,
  1,
  "earthwork",
  "FS",
  0,
  "office",
  [
   "بتن مگر"
  ]
 ],
 [
  "foundation_form",
  "structure",
  "قالب‌بندی پی و شناژ",
  "m2",
  8,
  12,
  2,
  "earthwork",
  "FS",
  0,
  "secondary",
  [
   "قالب پی",
   "قالب شناژ"
  ]
 ],
 [
  "foundation_rebar",
  "structure",
  "آرماتوربندی فونداسیون",
  "kg",
  200,
  400,
  2,
  "foundation_form",
  "SS",
  1,
  "secondary",
  [
   "آرماتور فونداسیون",
   "میلگرد پی"
  ]
 ],
 [
  "foundation_concrete",
  "structure",
  "بتن‌ریزی فونداسیون",
  "m3",
  20,
  50,
  1,
  "foundation_rebar",
  "FS",
  0,
  "office",
  [
   "بتن فونداسیون",
   "بتن ریزی پی"
  ]
 ],
 [
  "column_rebar",
  "structure",
  "آرماتوربندی ستون‌ها",
  "kg",
  200,
  300,
  2,
  "foundation",
  "FS",
  0,
  "secondary",
  [
   "آرماتور ستون",
   "خاموت ستون"
  ]
 ],
 [
  "column_form",
  "structure",
  "قالب‌بندی ستون",
  "m2",
  8,
  12,
  2,
  "column_rebar",
  "SS",
  1,
  "secondary",
  [
   "قالب ستون"
  ]
 ],
 [
  "column_concrete",
  "structure",
  "بتن‌ریزی ستون",
  "m3",
  8,
  20,
  1,
  "column_form",
  "FS",
  0,
  "office",
  [
   "بتن ستون"
  ]
 ],
 [
  "beam_rebar",
  "structure",
  "آرماتوربندی تیرها",
  "kg",
  250,
  350,
  2,
  "column_concrete",
  "FS",
  0,
  "secondary",
  [
   "آرماتور تیر",
   "میلگرد تیر"
  ]
 ],
 [
  "slab_form",
  "structure",
  "قالب‌بندی سقف و دال",
  "m2",
  6,
  10,
  2,
  "column_concrete",
  "FS",
  0,
  "secondary",
  [
   "قالب سقف",
   "قالب دال"
  ]
 ],
 [
  "slab_rebar",
  "structure",
  "آرماتوربندی دال",
  "kg",
  300,
  400,
  2,
  "slab_form",
  "SS",
  1,
  "secondary",
  [
   "آرماتور سقف",
   "آرماتور دال"
  ]
 ],
 [
  "slab_concrete",
  "structure",
  "بتن‌ریزی سقف",
  "m3",
  20,
  50,
  1,
  "slab_rebar",
  "FS",
  0,
  "office",
  [
   "بتن سقف",
   "بتن دال"
  ]
 ],
 [
  "steel_fabrication",
  "structure",
  "ساخت اسکلت فولادی",
  "kg",
  500,
  1400,
  1,
  "foundation",
  "FS",
  0,
  "office",
  [
   "ساخت اسکلت فلزی",
   "ساخت اسکلت فولادی"
  ]
 ],
 [
  "steel_erection",
  "structure",
  "نصب اسکلت فولادی",
  "kg",
  1000,
  2000,
  1,
  "steel_fabrication",
  "SS",
  2,
  "secondary",
  [
   "نصب اسکلت فلزی",
   "نصب اسکلت فولادی"
  ]
 ],
 [
  "steel_welding",
  "structure",
  "جوشکاری اتصالات",
  "m",
  10,
  20,
  1,
  "steel_erection",
  "SS",
  1,
  "office",
  [
   "جوشکاری اتصال",
   "جوش اتصال"
  ]
 ],
 [
  "steel_bolting",
  "structure",
  "پیچ‌ومهره اتصالات سازه",
  "count",
  35,
  70,
  1,
  "steel_erection",
  "SS",
  1,
  "office",
  [
   "پیچ سازه",
   "پیچ اتصال"
  ]
 ],
 [
  "composite_deck",
  "structure",
  "سقف عرشه فولادی",
  "m2",
  35,
  80,
  1,
  "steel_erection",
  "FS",
  0,
  "office",
  [
   "عرشه فولادی"
  ]
 ],
 [
  "timber_frame",
  "wood",
  "اسکلت چوبی",
  "m3",
  1,
  3,
  1,
  "foundation",
  "FS",
  0,
  "office",
  [
   "اسکلت چوبی"
  ]
 ],
 [
  "timber_finish",
  "wood",
  "کف‌پوش و پوشش چوبی",
  "m2",
  12,
  25,
  1,
  "timber_frame",
  "FS",
  0,
  "office",
  [
   "کف چوبی",
   "دیوار چوبی"
  ]
 ],
 [
  "block_wall",
  "architecture",
  "دیوار بلوکی",
  "m2",
  8,
  16,
  2,
  "slabs",
  "FS",
  0,
  "secondary",
  [
   "دیوار بلوکی",
   "بلوک سیمانی",
   "بلوک سفالی"
  ]
 ],
 [
  "brick_wall",
  "architecture",
  "دیوار آجری",
  "m2",
  8,
  12,
  2,
  "slabs",
  "FS",
  0,
  "secondary",
  [
   "دیوار آجری"
  ]
 ],
 [
  "aac_wall",
  "architecture",
  "دیوار هبلکس",
  "m2",
  10,
  20,
  2,
  "slabs",
  "FS",
  0,
  "office",
  [
   "هبلکس",
   "بلوک AAC"
  ]
 ],
 [
  "plaster_base",
  "architecture",
  "اندود زیرکار و گچ‌وخاک",
  "m2",
  10,
  18,
  2,
  "rough_mechanical",
  "FS",
  0,
  "secondary",
  [
   "گچ خاک",
   "اندود زیرکار"
  ]
 ],
 [
  "finish_plaster",
  "architecture",
  "گچ سفیدکاری",
  "m2",
  15,
  24,
  2,
  "plaster_base",
  "FS",
  0,
  "office",
  [
   "گچ سفید",
   "سفیدکاری"
  ]
 ],
 [
  "floor_screed",
  "architecture",
  "کف‌سازی و شیب‌بندی",
  "m2",
  20,
  40,
  1,
  "rough_mechanical",
  "FS",
  0,
  "office",
  [
   "کف‌سازی",
   "شیب بندی"
  ]
 ],
 [
  "waterproofing",
  "architecture",
  "عایق رطوبتی",
  "m2",
  15,
  35,
  1,
  "floor_screed",
  "FS",
  0,
  "office",
  [
   "ایزوگام",
   "عایق رطوبتی",
   "آب بندی"
  ]
 ],
 [
  "floor_tile",
  "architecture",
  "سرامیک کف",
  "m2",
  8,
  15,
  2,
  "waterproofing",
  "FS",
  0,
  "secondary",
  [
   "سرامیک کف",
   "کاشی کف"
  ]
 ],
 [
  "wall_tile",
  "architecture",
  "کاشی دیوار",
  "m2",
  6,
  10,
  2,
  "rough_mechanical",
  "FS",
  0,
  "secondary",
  [
   "کاشی دیوار",
   "سرامیک دیوار"
  ]
 ],
 [
  "stone_floor",
  "architecture",
  "سنگ کف و پله",
  "m2",
  4,
  8,
  2,
  "floor_screed",
  "FS",
  0,
  "secondary",
  [
   "سنگ کف",
   "سنگ پله"
  ]
 ],
 [
  "stone_facade",
  "architecture",
  "نمای سنگی",
  "m2",
  4,
  8,
  2,
  "masonry",
  "SS",
  3,
  "office",
  [
   "نمای سنگی",
   "سنگ نما"
  ]
 ],
 [
  "brick_facade",
  "architecture",
  "نمای آجری",
  "m2",
  5,
  11,
  2,
  "masonry",
  "SS",
  3,
  "office",
  [
   "نمای آجری",
   "آجر نما"
  ]
 ],
 [
  "aluminum_window",
  "architecture",
  "پنجره آلومینیومی",
  "m2",
  5,
  10,
  1,
  "masonry",
  "FS",
  0,
  "office",
  [
   "پنجره آلومینیوم"
  ]
 ],
 [
  "upvc_window",
  "architecture",
  "پنجره UPVC",
  "m2",
  6,
  12,
  1,
  "masonry",
  "FS",
  0,
  "office",
  [
   "پنجره یو پی وی سی",
   "پنجره UPVC"
  ]
 ],
 [
  "door_install",
  "architecture",
  "نصب درب",
  "count",
  3,
  7,
  1,
  "finishes",
  "SS",
  1,
  "office",
  [
   "درب داخلی",
   "درب ضد سرقت",
   "نصب درب"
  ]
 ],
 [
  "ceiling_gypsum",
  "architecture",
  "سقف کاذب و کناف",
  "m2",
  10,
  20,
  2,
  "rough_electrical",
  "FS",
  0,
  "office",
  [
   "سقف کاذب",
   "کناف"
  ]
 ],
 [
  "paint_primer",
  "architecture",
  "آستر رنگ",
  "m2",
  25,
  40,
  2,
  "finish_plaster",
  "FS",
  0,
  "secondary",
  [
   "آستر رنگ",
   "پرایمر رنگ"
  ]
 ],
 [
  "paint_finish",
  "architecture",
  "رنگ نهایی",
  "m2",
  20,
  27,
  2,
  "paint_primer",
  "FS",
  0,
  "secondary",
  [
   "رنگ پلاستیک",
   "رنگ اکریلیک",
   "رنگ نهایی"
  ]
 ],
 [
  "cabinet",
  "architecture",
  "کابینت آشپزخانه",
  "m",
  3,
  6,
  1,
  "floor_tile",
  "FS",
  0,
  "office",
  [
   "کابینت"
  ]
 ],
 [
  "plumbing_water",
  "mechanical",
  "لوله‌کشی آب سرد و گرم",
  "m",
  18,
  35,
  2,
  "masonry",
  "SS",
  1,
  "office",
  [
   "لوله آب",
   "آب سرد",
   "آب گرم"
  ]
 ],
 [
  "sewage_pipe",
  "mechanical",
  "لوله‌کشی فاضلاب",
  "m",
  20,
  40,
  2,
  "masonry",
  "SS",
  1,
  "office",
  [
   "لوله فاضلاب",
   "رایزر فاضلاب"
  ]
 ],
 [
  "gas_pipe",
  "mechanical",
  "لوله‌کشی گاز",
  "m",
  12,
  25,
  1,
  "masonry",
  "SS",
  2,
  "office",
  [
   "لوله گاز"
  ]
 ],
 [
  "radiator",
  "mechanical",
  "نصب رادیاتور",
  "count",
  5,
  10,
  1,
  "finishes",
  "SS",
  1,
  "office",
  [
   "رادیاتور"
  ]
 ],
 [
  "boiler",
  "mechanical",
  "نصب پکیج و دیگ",
  "count",
  2,
  5,
  1,
  "finishes",
  "SS",
  1,
  "office",
  [
   "پکیج دیواری",
   "دیگ گرمایش"
  ]
 ],
 [
  "hvac_duct",
  "mechanical",
  "کانال‌کشی تهویه",
  "m2",
  12,
  30,
  2,
  "masonry",
  "SS",
  1,
  "office",
  [
   "کانال تهویه",
   "کانال کولر",
   "کانال داکت"
  ]
 ],
 [
  "hvac_pipe",
  "mechanical",
  "لوله‌کشی مسی تبرید",
  "m",
  12,
  25,
  2,
  "masonry",
  "SS",
  1,
  "office",
  [
   "لوله مسی",
   "خط تبرید"
  ]
 ],
 [
  "hvac_unit",
  "mechanical",
  "نصب فن‌کویل و داکت‌اسپلیت",
  "count",
  2,
  5,
  1,
  "finishes",
  "SS",
  2,
  "office",
  [
   "داکت اسپلیت",
   "داکت‌اسپلیت",
   "فن کویل"
  ]
 ],
 [
  "sanitary",
  "mechanical",
  "نصب تجهیزات بهداشتی",
  "count",
  4,
  9,
  1,
  "wall_tile",
  "FS",
  0,
  "office",
  [
   "روشویی",
   "توالت فرنگی",
   "شیرآلات"
  ]
 ],
 [
  "mech_test",
  "mechanical",
  "آزمایش و راه‌اندازی مکانیک",
  "count",
  2,
  6,
  1,
  "mechanical_finish",
  "FS",
  0,
  "office",
  [
   "تست فشار لوله",
   "آزمایش نشتی"
  ]
 ],
 [
  "conduit",
  "electrical",
  "لوله‌گذاری و قوطی‌گذاری برق",
  "m",
  35,
  60,
  2,
  "masonry",
  "SS",
  1,
  "office",
  [
   "لوله برق",
   "لوله گذاری برق",
   "قوطی گذاری"
  ]
 ],
 [
  "wiring",
  "electrical",
  "سیم‌کشی برق",
  "m",
  60,
  120,
  2,
  "conduit",
  "FS",
  0,
  "office",
  [
   "سیم کشی برق",
   "سیم‌کشی برق"
  ]
 ],
 [
  "cable_tray",
  "electrical",
  "سینی کابل",
  "m",
  12,
  30,
  1,
  "masonry",
  "SS",
  1,
  "office",
  [
   "سینی کابل"
  ]
 ],
 [
  "switch_socket",
  "electrical",
  "نصب کلید و پریز",
  "count",
  18,
  40,
  1,
  "paint_finish",
  "FS",
  0,
  "office",
  [
   "کلید پریز",
   "کلید و پریز"
  ]
 ],
 [
  "panel_board",
  "electrical",
  "نصب تابلو برق",
  "count",
  1,
  3,
  1,
  "wiring",
  "FS",
  0,
  "office",
  [
   "تابلو برق"
  ]
 ],
 [
  "lighting",
  "electrical",
  "نصب روشنایی",
  "count",
  12,
  25,
  1,
  "paint_finish",
  "FS",
  0,
  "office",
  [
   "چراغ",
   "روشنایی"
  ]
 ],
 [
  "grounding",
  "electrical",
  "سیستم ارت",
  "count",
  1,
  3,
  1,
  "foundation",
  "FS",
  0,
  "office",
  [
   "ارتینگ",
   "سیستم ارت"
  ]
 ],
 [
  "data_network",
  "electrical",
  "تلفن و دیتا و شبکه",
  "point",
  15,
  30,
  1,
  "conduit",
  "FS",
  0,
  "office",
  [
   "تلفن",
   "دیتا",
   "شبکه"
  ]
 ],
 [
  "elevator_rail",
  "elevator",
  "نصب ریل آسانسور",
  "m",
  8,
  20,
  1,
  "slabs",
  "FS",
  0,
  "office",
  [
   "ریل آسانسور"
  ]
 ],
 [
  "elevator_door",
  "elevator",
  "درب طبقات آسانسور",
  "count",
  2,
  4,
  1,
  "elevator_rail",
  "FS",
  0,
  "office",
  [
   "درب آسانسور"
  ]
 ],
 [
  "elevator_cabin",
  "elevator",
  "کابین و موتور آسانسور",
  "count",
  1,
  2,
  1,
  "elevator_door",
  "FS",
  0,
  "office",
  [
   "کابین آسانسور",
   "موتور آسانسور"
  ]
 ],
 [
  "fire_alarm",
  "fire",
  "اعلام حریق و دتکتورها",
  "point",
  10,
  25,
  1,
  "rough_electrical",
  "FS",
  0,
  "office",
  [
   "دتکتور",
   "اعلام حریق"
  ]
 ],
 [
  "fire_pipe",
  "fire",
  "لوله‌کشی اطفای حریق",
  "m",
  10,
  25,
  1,
  "masonry",
  "SS",
  1,
  "office",
  [
   "اسپرینکلر",
   "لوله آتش نشانی",
   "لوله اطفا"
  ]
 ],
 [
  "fire_cabinet",
  "fire",
  "جعبه آتش‌نشانی",
  "count",
  2,
  5,
  1,
  "fire_pipe",
  "FS",
  0,
  "office",
  [
   "جعبه آتش نشانی",
   "جعبه آتش‌نشانی"
  ]
 ],
 [
  "site_paving",
  "site",
  "سنگفرش محوطه",
  "m2",
  15,
  35,
  1,
  "slabs",
  "FS",
  0,
  "office",
  [
   "سنگفرش محوطه",
   "کف پوش محوطه"
  ]
 ],
 [
  "site_kerb",
  "site",
  "جدول‌گذاری محوطه",
  "m",
  20,
  45,
  1,
  "slabs",
  "FS",
  0,
  "office",
  [
   "جدول کشی",
   "جدول‌گذاری"
  ]
 ],
 [
  "landscape",
  "site",
  "فضای سبز",
  "m2",
  25,
  50,
  1,
  "site_paving",
  "FS",
  0,
  "office",
  [
   "چمن کاری",
   "فضای سبز"
  ]
 ],
 [
  "demolition",
  "renovation",
  "تخریب کنترل‌شده",
  "m2",
  12,
  35,
  2,
  "mobilize",
  "FS",
  0,
  "office",
  [
   "تخریب دیوار",
   "تخریب نازک کاری"
  ]
 ],
 [
  "seismic_retrofit",
  "renovation",
  "مقاوم‌سازی سازه",
  "m2",
  3,
  8,
  2,
  "demolition",
  "FS",
  0,
  "office",
  [
   "مقاوم سازی",
   "بهسازی لرزه ای"
  ]
 ],
 [
  "restoration",
  "restoration",
  "مرمت اجزای موجود",
  "m2",
  3,
  9,
  1,
  "demolition",
  "FS",
  0,
  "office",
  [
   "مرمت",
   "بازسازی تاریخی"
  ]
 ]
]
CATALOG={x[0]:ProductionProfile(x[0],x[1],x[2],x[3],str(x[4]),str(x[5]),x[6],
       x[7],x[8],x[9],REF_SECONDARY if x[10]=="secondary" else REF_OFFICE,
       tuple(x[11])) for x in _RAW}
assert len(CATALOG)==len(_RAW)

def productivity_days(code,quantity,unit,*,crews=None,efficiency="1"):
    """Quantified tentative whole-workday range; no payable or baseline approval."""
    p=CATALOG[code]
    if unit!=p.unit:raise ValueError("واحد متره با واحد نرخ تولید این فعالیت یکسان نیست")
    if isinstance(quantity,bool):raise ValueError("مقدار متره معتبر نیست")
    try:
        q=Decimal(str(quantity));factor=Decimal(str(efficiency))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise ValueError("مقدار یا ضریب بهره‌وری نامعتبر است") from exc
    crew_count=p.crews if crews is None else crews
    if type(crew_count) is not int or not 1<=crew_count<=100:
        raise ValueError("تعداد اکیپ باید عدد صحیح ۱ تا ۱۰۰ باشد")
    if not q.is_finite() or q<0 or not factor.is_finite() or not Decimal("0.1")<=factor<=Decimal("2"):
        raise ValueError("کمیت یا ضریب بهره‌وری نامعتبر است")
    slow=Decimal(p.low_per_crew_day)*crew_count*factor
    fast=Decimal(p.high_per_crew_day)*crew_count*factor
    if slow<=0 or fast<slow:raise ValueError("نرخ تولید نامعتبر است")
    def days(rate):
        return int((q/rate).to_integral_value(rounding=ROUND_CEILING)) if q else 0
    return {"min_workdays":days(fast),"expected_workdays":days((fast+slow)/2),
            "max_workdays":days(slow),"status":"PRELIMINARY_UNAPPROVED",
            "source":p.rate_source,"unit":p.unit,"quantity":str(q),
            "crews":crew_count,"efficiency":str(factor)}

def matching_profile(label,disciplines):
    """Unambiguous label-only mapping, never fake classification/quantities."""
    import unicodedata
    def norm(x):
        return (unicodedata.normalize("NFKC",str(x or ""))
                .replace("ي","ی").replace("ك","ک").replace("\u200c"," ").upper())
    value=norm(label)
    matches=[p.code for p in CATALOG.values()
             if p.discipline in disciplines and any(norm(token) in value for token in p.keywords)]
    return matches[0] if len(matches)==1 else None

def catalog_metadata():
    return {"version":"2026-10-31-review-only","profiles":len(CATALOG),
            "disciplines":sorted(set(p.discipline for p in CATALOG.values())),
            "methodology":[REF_CMU,REF_PMI,REF_ORACLE],
            "warning":"همه نرخ‌ها و روابط ابتدایی‌اند و بدون تأیید مهندس مبنای قرارداد نیستند"}
