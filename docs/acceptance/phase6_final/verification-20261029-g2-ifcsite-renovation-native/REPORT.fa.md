# StructuralPro | نتیجه آزمون G2 برای زمین IFC4 و وضع موجود بازسازی

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**PR:** #34 (Draft, Open, Unmerged)  
**دامنه:** نمایش هندسهٔ اصیل و قابل‌ردیابی فقط‌خواندنی در نرم‌افزار اصلی؛ نه استنتاج مقدار یا تأیید عملیات بازسازی.

## ۱. چه چیزی واقعاً ساخته شد؟

1. `core/drawings/site_context.py` و `app/ifc_site_viewport.py`: نمایش مستقل `IfcSite` مدل IFC4 **فاقد IfcElement**، با هش SHA256 فایل واقعی، Revision، سقف ۴۰٬۰۰۰ مثلث، انتخاب واقعی فایل از پنجره فارسی، Worker و Orbit/Pan/Zoom. هیچ `pick`، فهرست اعضای مهندسی، `quantity_authority` یا ثبت BOQ وجود ندارد. در مدل رسمی swisstopo که GUID مکانی غیرکانونی دارد، هیچ هویت عضو مالی پذیرفته نشده و هش فایل مبنای بازبینی است؛ کنترل سخت‌گیرانهٔ GlobalId اعضای مهندسی تغییر نکرد.
2. `core/drawings/existing_building_reference.py` و `app/ifc_existing_reference_viewport.py`: یک مسیر مجزای IFC2X3 **صرفاً برای مشاهده مرجع وضع موجود** در پروژه‌های بازسازی، بدون تغییر `BIMAdapter` و بدون مجوز مهندسی/متره/پرداخت. از هر منبع، **یک عضو واقعی** به شکل bounded و قابل بازبینی نمایش داده می‌شود؛ شمارش همه عناصر در خلاصهٔ منبع باقی می‌ماند. هیچ مرحلهٔ تخریب/تقویت/مرمت از مدل استنتاج نشده است.
3. `app/graphical_takeoff.py`: دو دکمهٔ فارسیِ واقعی برای انتخاب فایل، Worker غیرهم‌زمان، SHA، بررسی تغییر Revision و حفظ وضعیت پروژه.
4. چهار تست fail-closed جدید در `tests/test_phase6_g2_spatial_readonly_guards.py`: هویت زمینهٔ مکانی جدا از عضو، رد نوع Schema نامعتبر، منبع دست‌کاری‌شده، عدم مجوز BOQ و عدم صدور شناسهٔ عضو.

## ۲. آزمون اصل فایل‌های منتشرشده

### الف) نمونه رسمی زمین swisstopo، IFC4

منبع: Swiss Federal Office of Topography، `https://www.swisstopo.admin.ch/en/buildings-terrain-ifc`. ZIP اصلی SHA256 `6e2a370ca56a0a09e4baf52cbe008a88d9f39b97dc1e0bf66c8073d445f3d189`.

| منبع | هندسه از `IfcSite` | Windows | Linux |
|---|---:|---|---|
| terrain IFC4 #1 | ۱٬۹۵۶ مثلث | PASS | PASS |
| terrain IFC4 #2 | ۱٬۸۵۳ مثلث | PASS | PASS |

- [CI اصلاح نهایی روی کد با کنترل Revision، #40949293755](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40949293755): هر ۲ Job SUCCESS.
- Windows artifact `12929479270`، SHA256 ZIP `bb294e4b80b12a5f0ae5af7564543703a6745b4b5277592633a2dab7c382ef56`.
- Linux artifact `12931405261`، SHA256 ZIP `4adfdbbe1ec49e788c600f35c3bed06bdb38708d1f5a79fea22841fb45aca398`.
- هر دو فایل دارای IfcSite spatial context، بدون یک IfcElement قابل متره؛ Source mutation بعد از نمایش رد شد. نه اختیار GIS/georeference مهندسی گرفته شده و نه IfcSite به IfcElement جعل شده است.

### ب) دو فایل واقعی از پروژه اروپایی بازسازی BIM4EEB

منبع: `https://zenodo.org/records/6685810`، DOI `10.5281/zenodo.6685810`، اصل IFC2X3 و MD5 ناشر.

| منبع وضع موجود | اعضای منبع | دارای هندسه | یک عضو واقعی پیش‌نمایش‌شده | Windows / Linux |
|---|---:|---:|---:|---|
| Finland | ۹۳۹ | ۹۳۹ | ۴۸ مثلث | PASS / PASS |
| Poland | ۳۶۲ | ۳۵۶ | ۱۶۰ مثلث | PASS / PASS |

- [CI روی کد با کنترل Revision، #40949293789](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40949293789): هر ۲ Job SUCCESS.
- Windows artifact `12930104268`، SHA256 ZIP `43e9e991a4be3e442a5dab06514fde27c597312797ed4401e0984fc8b18c9e83`.
- Linux artifact `12929664809`، SHA256 ZIP `d5f426b7b1b49a905b88ec617f09bf9af7314d7d163407cff1caa05332898179`.
- محتوای IFC اصلی در Artifactها کپی نشده؛ هش‌های اولیهٔ منبع تأیید شدند. فقط یک عضو واقعی هر بار نمایش داده شده، نه کل ساختمان هم‌زمان؛ باقی عناصر source-only و بدون هندسهٔ بارشده اعلام می‌شوند.
- مدل‌های مذکور **دادهٔ ساختمان موجود مرتبط با تحقیق بازسازی‌اند**، اما نبود سند مراحل عملیات بازسازی در IFC آنها به‌صورت `renovation_phases_verified=False` منعکس شده است. این دو مدل **تأیید پشتیبانی مهندسی IFC2X3 نیستند**.

### ج) تست‌های ایمنی و رگرسیون هدفمند

- [CI گیت‌های fail-closed #40949948916](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40949948916): Windows ۷ PASS، Linux ۷ PASS، صفر FAIL/ERROR/SKIP؛ اصل JUnit هر دو سیستم مستقل خوانده شد.
- [CI مسیر اصلی انتخاب و تعویض اعضای IFC4 #40949293742](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40949293742): SUCCESS در هر دو سیستم؛ Workflow با pin قدیمی `BIMAdapter` اصلاح و دوباره اجرا شد. شکست‌های قبلی آن پیش از pytest و صرفاً ناشی از pin نامعتبر ثبت شده‌اند.
- [CI ارتباط چهارطرفه #40949293865](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40949293865): SUCCESS در هر دو سیستم؛ مسیر مهندسی پیشین دست‌نخورده.
- **رگرسیون جامع نسخهٔ جدید: PASS تأییدشده.** [GitHub Actions #40949336798](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40949336798) روی آخرین HEAD کد محصول `683e2ad428d62e4980daa702438060621c845150`، تمام **۵ Job موفق**: Linux **۸٬۴۵۸ PASS / ۵ SKIP / ۰ FAIL/ERROR/Timeout** و Windows جمع یکتای سه shard **۸٬۴۵۶ PASS / ۷ SKIP / ۰ FAIL/ERROR/Timeout**. هر دو سیستم **۸٬۴۶۳ testcase از ۷۱۷ ماژول فعال**. کنترل JUnit union تأیید کرد تست اضافه/گم‌شده/تکراری وجود ندارد؛ MANIFEST SHA256 `b659af82c169aec6ca617cf98636dda447f84462a6088df344a105e807d5fbb0`. ۱۵ ماژول قراردادهای Historical/Release از این شمارش مستثنی‌اند و PASSهای قدیمی بدون اجرا روی این نسخه به شمارش اضافه نمی‌شوند.

| شاهد اصل JUnit | Artifact ID | SHA256 فایل ZIP |
|---|---:|---|
| Linux کامل | `12931407341` | `ef72fa7fb9a8c42a43c5ccecf1809cd251eba034f3eda9cdb5b53ba6a6a789ef` |
| Windows shard 0 | `12932041377` | `bbafc267892b9db6a3348d023b7882403d0829e0516c425ec240988398ec7f85` |
| Windows shard 1 | `12931731830` | `deeb11c2517feb79664ca3d6182c857465b76f1a4dd74ae005e99c5772aacfe0` |
| Windows shard 2 | `12931732416` | `c10021f1a304c824fc5b40b8fb0903cb6eaf11ae5fde871c91c4c71c3dfd43b1` |
| Verified JUnit union | `12930863520` | `3d2f99959aa5dbfe76d2babc20cab23bfd2222aab1b42b29ca00c89938bc57b5` |

تمام JSONهای Runner اصلی بر روی HEAD آزموده‌شده با `pytest_exit_code=0`، `timed_out=false` و `overall_green=true` مستقلاً بازبینی شدند؛ union `verified=true`. آخرین commitهای بعدی فقط Workflowهای تشخیصی و شواهد هستند، نه تغییر در کد app/core یا تست‌های رجعتی.

## ۳. مرز پذیرش و NO-GO

**ACCEPTED در دامنهٔ خودکار خواندن و نمایش ایمن:** نمونهٔ اصلی زمین IFC4 از `IfcSite` و مدل اصیل وضع موجود IFC2X3 به شکل یک پیش‌نمایش فقط‌خواندنی، SHA/Revision، پنجره فارسی، دوربین و صفر دخالت در BOQ. کاربر همچنان می‌تواند از مسیر اصلی IFC4 برای اعضای مهندسی مطابق قرارداد قبلی استفاده کند.

**NOT ACCEPTED و نباید جایگزین گردد:** IFC2X3 محاسباتی/متره و QTO، پوشش هم‌زمان تمام اعضای مدل بزرگ، مداخله‌های مهندسی بازسازی، نقشه GIS و تبدیل مختصات، تأیید سخت‌افزار فیزیکی Windows، آماده‌بودن Installer و انتشار نسخهٔ نهایی.

G2 طبق مصوبهٔ «نمایش زندهٔ چندرشته‌ای» در این مرحله پوشش منابع قبلاً مسدودِ **terrain spatial context و ساختمان موجود مرجع** را دارد. پذیرش مهندسیِ بازسازی و اختیارات مالی **به‌هیچ‌وجه صادر نمی‌شود**. وضعیت رسمی بستن کل فاز ۶ تا رگرسیون کامل و G4 مالک **PARTIAL** می‌ماند.

## خلاصه وضعیت پروژه و این چت

- G1: پذیرش خودکار محدود؛ ریشه کرش تاریخی قطعی اثبات نشده.
- G2: نمایش `IfcGeographicElement` قبلاً پذیرفته؛ این نوبت `IfcSite` IFC4 و IFC2X3 وضع موجود در دامنهٔ *فقط بصری* پذیرفته شدند؛ رگرسیون جامع نهایی نیز موفق و در ماتریس گیت‌ها ثبت شد؛ این پذیرش همچنان فقط دامنهٔ نمایش بصریِ منبع‌محور است.
- G3: فاقد قرارداد مستقل مصوب، NONBLOCKING.
- G4: آزمایش چندمانیتور/GPU/Sleep-Resume روی Windows واقعی مالک و امضای او انجام نشده.
- G5: تنها یک نسخهٔ واحد Windows مصوب، بیلد/EXE/Release انجام نشده.
- ۸ فاز ثابت، ۸۵٪ رسمی، فاز ۶ تا تکمیل گیت‌ها PARTIAL، PR #34 بدون Merge.
