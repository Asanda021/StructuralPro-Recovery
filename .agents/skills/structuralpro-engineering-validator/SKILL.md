---
name: structuralpro-engineering-validator
description: Independently validate StructuralPro civil-engineering takeoff, CAD/PDF/IFC geometry, BOQ, pricebook, estimates, statements, project planning and source-linked outputs. Use for real drawing-to-finance acceptance; never guess quantities or prices.
---

# StructuralPro | بازبین مستقل صحت مهندسی

**Immutable safety flags:** `NO_MERGE / NO_MAIN_WRITE / NO_EXE / NO_INSTALLER / NO_RELEASE` تا زمانی که مالک صریحاً مجوز دهد.

## اصل بنیادین
هیچ مقدار، طول، مساحت، حجم، وزن، مقدار آرماتور، قیمت، ضریب، پیشرفت، بهره‌وری یا تاریخ پایان را بدون **شاهد مهندسی مستقل و قابل بازیابی** قطعی اعلام نکن. AI نقش پیشنهاددهنده دارد؛ محاسبه معتبر فقط از موتور قابل آزمون و ورودی‌های بازبینی‌شده است. هیچ‌گاه داده یا قیمت فرضی به BOQ/SQLite واقعی commit نشود.

## سطح دسترسی و محرمانگی
- پیش‌فرض **read-only**؛ بدون اصلاح سورس، تغییر داده قرارداد، ادغام PR یا انتشار.
- نقشه، اکسل، نرخ، اطلاعات کارفرما و فایل پروژه خصوصی را به GitHub، CI، کامنت عمومی یا سایت شخص ثالث منتقل نکن؛ برای تست عمومی از داده مجاز و غیرمحرمانه استفاده کن.
- اگر نقشه اصلی، ابزار CAD معتبر، Windows یا Excel در دسترس نیست، `NOT_TESTED` بنویس. داده مصنوعی فقط `SYNTHETIC_TEST_PASS` است، نه `REAL_ENGINEERING_ACCEPTED`.
- SHA کامل source، نسخه نقشه، شناسه نشست و روش تولید expected quantity را ثبت کن.

## آزمون زنجیره مستقل؛ به ترتیب
1. **Import & coverage:** فایل واقعی PDF/DWG/DXF/IFC را با مجوز معتبر باز کن؛ header/units/scale، لایه‌ها، BLOCK/MINSERT/XREF/HATCH/DIM/TEXT/MTEXT/SPLINE/AEC/MEP/SHX/Proxy، هندسه پنهان و unsupported را حسابرسی کن. AC1032 به‌تنهایی به معنی سازگاری تمام آبجکت‌های AutoCAD 2027 نیست.
2. **Geometry:** کنترل مقیاس و ابعاد معلوم، window selection/clipping، دایره/قوس/منحنی، محدوده، کسورات/بازشو، همپوشانی، احجام بتن، قالب و جزئیات میلگرد/فولاد. هیچ تبدیل «نمایش» به «مجوز متره» بدون مدارک معتبر انجام نده.
3. **Identity & review:** هر مقدار ← پروژه، طبقه، عضو، هندسه، واحد، نسخه/هش منبع، فرمول، متصدی بررسی و وضعیت تأیید. روی source stale، CAS mismatch و تکرار هویت باید fail-closed باشد.
4. **BOQ & pricing:** برای حداقل یک پروژه پنج‌طبقه واقعی، ریزمتره مستقل و خروجی برنامه را به تفکیک ردیف و واحد تطبیق بده؛ ردیف بی‌منبع، تفاوت واحد، تکرار کسورات، اختلاف Decimal یا mapping قیمت بدون تأیید را خطا بدان.
5. **Estimate & statement:** فهرست‌بها با نسخه/سال/منبع و شمول ضریب بررسی شود؛ پول و Decimal بدون float؛ کارکرد دوره/تجمعی، سقف قرارداد، اصلاحیه، کسورات، موجودی و پرداخت از هم تفکیک شوند. قیمت روز یا نرخ تولید بدون سند ممنوع.
6. **Planning:** WBS/فعالیت‌ها، روابط FS/SS/FF/SF، تقویم واقعی، CPM و float، overlap، ظرفیت اکیپ، progress و حفظ ویرایش کاربر در reload/undo. مدت فقط با نرخ بهره‌وری معتبر؛ بدون مدت معتبر، ETA قطعی نده.
7. **Reports:** PDF/XLSX/DOCX/CSV در Windows با Excel/Word واقعی یا ابزار معتبر باز شوند؛ RTL، فونت، اعداد، فرمول، جمع‌ها، مقیاس چاپ، Manifest و SHA گزارش کنترل شوند.
8. **2D ↔ 3D ↔ Tree ↔ BOQ:** ناوبری و هایلایت صحیح عضو در دو سوی اتصال و حالت unlinked/ambiguous تأیید شود، نه mapping حدسی.

## روش تطبیق و اثبات
- برای هر نمونه: `fixture name (non-sensitive) | source SHA | plan/revision | expected independent calculation | observed | unit | tolerance with rationale | evidence artifact | result`.
- منبع expected مستقل از موتور اصلی باشد (محاسبه دستی مهندسی، ابزار دوم با روش مستقل یا مرجع معتبر). `expected` را از خود خروجی StructuralPro استخراج نکن.
- اختلاف مقدار یا واحد، کمبود پوشش اجزای CAD، عدم حفظ اطلاعات، تخطی از gate تأیید و خطای مالی → `BLOCKED` تا تحلیل ریشه‌ای.
- مقادیر گنگ/نامعلوم `UNKNOWN/NEEDS_ENGINEER_REVIEW` هستند، نه صفر.

## خروجی الزام‌آور
`HEAD_SHA`، سیستم‌عامل و ابزار، مشخصات غیرمحرمانه تست، ماتریس coverage، جدول اختلاف کمیت/مالی با فرمول مستقل، فهرست خطاها با شدت P0..P3، آزمون‌های انجام‌شده/انجام‌نشده، Regression tests to add و حکم `PASS_LIMITED / PARTIAL / NO_GO`.

**هشدار:** تا آزمون واقعی هندسه و توافق مهندس روی ردیف‌های مهم، `REAL_DWG_E2E=NOT_ACCEPTED` باقی می‌ماند؛ موفقیت CI جایگزین پذیرش نقشه اصلی نیست. قرارداد مشترک `docs/quality/QUALITY_AUDIT_CONTRACT_FA.md` را در صورت دسترس بخوان.
