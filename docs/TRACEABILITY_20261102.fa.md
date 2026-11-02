# ماتریس ردیابی معرفی جامع ↔ وضعیت کد

**تاریخ بررسی:** ۲ نوامبر ۲۰۲۶ (۱۱ آبان ۱۴۰۵)
**مرجع کد:** شاخه `main` در SHA `9d92fd6`. شاخه `test/phase8-p2-engineering-e2e-20261031` در SHA `de18ddae` برای مقایسه ستون «test» آورده شده است.
**روش:** بررسی ایستا. فایل‌ها خوانده و با جست‌وجوی کلیدواژه بررسی شدند. **هیچ تستی اجرا نشده است.** هر وضعیت باید با تست واقعی روی Windows تأیید شود.
**منبع الزامات:** سند «معرفی جامع» نسخه ۱.۰ (ارجاع فقط به شماره بخش).

## برچسب‌ها

- **Implemented:** کد وجود دارد و بخشی از آن شاهد دارد. هنوز تأیید پذیرش نشده است.
- **Partial:** بخشی از الزام در کد است، ولی کامل یا قابل اعتماد نیست.
- **Missing:** در ریپو شاهدی پیدا نشد.
- **Not Verified:** کد ممکن است وجود داشته باشد، ولی بدون آزمون واقعی نمی‌توان ادعا کرد.

## جدول ردیابی

| بخش سند | الزام خلاصه | وضعیت در `main` | وضعیت در `test` | شاهد (مسیر) | یادداشت |
|---|---|---|---|---|---|
| ۴.۱ | تب‌های افقی و Ribbon | Partial | Partial | `app/main.py` | تب افقی هست؛ Ribbon زمینه‌ای و Windows UI تست نشده |
| ۴.۱ | تم روشن/تاریک، RTL | Partial | Partial | `app/theme.py` | فونت bundle نشده |
| ۵ | ایجاد و مدیریت پروژه | Partial | Partial | `core/projects/` | فیلدهای قرارداد، تقویم، عوامل کامل نیست |
| ۶.۱ | PDF، کالیبراسیون، انتخاب | Partial | Partial | `core/drawings/` | تشخیص PDF اسکن‌شده در کد نیست |
| ۶.۲ | DWG/DXF | Not Verified | Partial | `core/cad/`، `core/drawings/dwg_converter.py` (test) | R1 باز است؛ `ezdwg` روی `main` در کد استفاده نمی‌شود |
| ۶.۳ | IFC | Partial | Partial | `core/bim/` | `ifcopenshell` اختیاری و کامنت‌شده |
| ۶.۴ | مدیریت نسخه نقشه | Partial | Partial | `core/revision/`، `core/revisions/` | ماژول تکراری |
| ۷.۱ | متره دستی و از نقشه | Partial | Partial | `core/takeoff/`، `app/manual_takeoff.py`، `app/graphical_takeoff.py` | جلوگیری از دوباره‌شماری باید تست شود |
| ۷.۳ | خانواده‌های متره | Partial | Partial | `core/aec/disciplines.py` | قواعد عمیق عمدتاً بتن و فولاد |
| ۸ | نمای سه‌بعدی و ارتباط زنده | Partial | Partial | `core/bim/`، `app/graphical_takeoff.py` | viewport سه‌بعدی مستقل روی `main` پیدا نشد؛ ارتباط دوطرفه تست نشده |
| ۸.۴ | کنترل برخورد هندسی | Missing | Partial | — | در `test` شاهد کمی دارد |
| ۹ | ریزمتره و BOQ | Partial (قوی‌تر) | Partial | `core/boq/` | منع ردیف بی‌نرخ در کد هست |
| ۱۰.۱ | فهرست‌بها و بانک نرخ | Partial | Partial | `core/iran/data.py` | ساختار ثبت منبع هست؛ داده عمداً بارگذاری نشده |
| ۱۰.۳ | برآورد | Partial | Partial | `core/estimate/` | — |
| ۱۱ | صورت‌وضعیت و قرارداد | Partial | Partial | `core/commercial/` | انطباق با قرارداد تست نشده |
| ۱۴ | مالی | Partial | Partial | `core/commercial/`، `core/cost_control/` | دو ماژول؛ احتمال موتور موازی (قاعده ۵) |
| ۱۲.۱ | WBS و CPM | Missing | Partial | — (`main`) | `core/projects/scheduling.py` فقط در `test` است |
| ۱۲.۲ | تبدیل مقدار به مدت | Not Verified | Not Verified | — | نیاز به سه مشاهده‌ی مستقل بهره‌وری |
| ۱۲.۳ | پیشرفت فیزیکی | Partial | Partial | `core/commercial/` | — |
| ۱۳ | مصالح و دفتر فنی | Partial | Partial | `core/projects/` | پیش‌نویس خرید در `test` بیشتر است |
| ۱۵ | AI محلی | Partial | Partial | `core/ai/gguf_runtime_v1.py`، `core/ai/local_engine.py` | مدل بسته نشده؛ گیت‌های A1–A4 شاهد ندارند |
| ۱۵ | سطوح AI (Edition) | **تضاد با سند** | — | `core/ai/edition_models.py` | سند Edition را منع کرده |
| ۱۶ | خروجی PDF/Word/Excel/CSV | Partial | Partial | `core/reports/` | Office و چاپ واقعی Not Verified |
| ۱۶.۴ | گیت آماده‌صدور | Partial | Partial | `core/reports/` | — |
| ۱۶.۳ | فونت فارسی bundle | Missing | Partial | — | — |
| ۱۷ | Snapshot و بازیابی | Partial | Partial | `core/sync/` | بازیابی بعد از Crash Not Verified |
| ۱۸ | کارایی و غیرعملکردی | Not Verified | Not Verified | — | نیاز به Windows واقعی |
| ۲ | بدون دکمه‌ی بی‌عملکرد | **تضاد با سند** | — | `core/platform/product_hub.py`، `core/sync/contracts.py` | `NotImplementedError` دارند |
| ۲ | Android خارج از دامنه | — | — | `android/`، `mobile/`، `website/` | باید از بسته‌ی اصلی جدا شوند |
| ۲ | فقط یک نسخه (بدون Light/Standard/Pro) | **تضاد با سند** | — | `packaging/installer.iss`، `packaging/installer-edition.iss` | دو installer |
| ۲۰ | هشت فاز مصوب | Partial | Partial | `docs/` | پوشه‌ی `docs/plans/` روی `main` نیست؛ سند فاز ۹ یا اولویت هفتم ممنوع است |

## تکرار و بدهی فنی (بر اساس قاعده ۵ سند)

- ماژول‌های تکراری: `core/project` و `core/projects`؛ `core/revision` و `core/revisions`؛ `core/drawing` و `core/drawings`؛ `core/integration` و `core/integrations`؛ `core/release.py` و `core/release_readiness.py`؛ `core/sync.py`، `core/sync_engine.py` و `core/sync_store.py`؛ `core/security.py` و `core/security_hardening_v2.py`.
- قاعده: قبل از یکسان‌سازی، کدام ماژول توسط تست‌ها و برنامه استفاده می‌شود باید مشخص شود. حذف کورکورانه ممنوع است.
- نام‌های نسخه‌دار (`_v1`، `_v2`) و پیشوندهای فاز (`p31_`، `phase6_`) نیاز به تغییر نام دارند.

## کارهای بعدی پیشنهادی (داخل فاز ۸ و بدون فاز جدید)

1. **P8/P2:** آزمون DWG و Excel خصوصی در محیط مجاز؛ جدول اختلاف؛ تأیید مهندس.
2. انتقال `scheduling.py` از `test` به `main` در فاز ۴ همراه تست CPM.
3. تصمیم درباره‌ی Edition و installer دوم.
4. تکمیل یا حذف `NotImplementedError` در `product_hub.py` و `sync/contracts.py`.
5. bundle کردن فونت فارسی و آزمون RTL در گزارش‌ها (فاز ۷).
6. یکسان‌سازی ماژول‌های تکراری با تست، نه با حذف مستقیم.

## یادداشت پایانی

این ماتریس فقط بررسی ایستا است. وضعیت «Implemented» به معنی تأیید پذیرش نیست. طبق سند، تا آزمون واقعی روی Windows، Office و چاپگر و تصمیم مالک، انتشار مجاز نیست.
