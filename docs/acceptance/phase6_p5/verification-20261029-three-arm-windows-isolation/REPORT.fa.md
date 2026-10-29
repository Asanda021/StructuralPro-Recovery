# StructuralPro | فاز ۶، اولویت ۵ | نتیجه آزمون تفکیکی سه‌مسیره Windows

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**Run:** https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40822722934  
**Source SHA:** `487d4079a2942d24946fb5c07f2cc448cdd6de0f`  
**وضعیت اجرای محدود:** `completed/success` و سه مسیر در دو تکرار مستقل **PASS**؛ **منشأ Access Violation هنوز اثبات نشده و گیت پایداری کلی Windows باز است.**

## شواهد قابل ممیزی

Artifact اصلی GitHub: `p6-windows-three-arm-native-isolation` با **ID 12876045500** و ZIP **SHA-256 `050b35b560e4b3727dc1974f3251ac38ebc073c88aca94326bfd68490f4c3342`**. برای هر مسیر `summary.json`، `run-1.xml`، `run-2.xml`، لاگ و نمونه‌های CPU/RSS بررسی شدند. شش JUnit معتبر و هر کدام یک PASS دارند؛ صفر FAIL، ERROR و SKIP. هیچ Timeout یا `0xC0000005` در این Run رخ نداد.

| مسیر | دامنه آزمون | اجرای ۱ | اجرای ۲ | نتیجه |
|---|---|---:|---:|---|
| A / core | سرویس واقعی محاسبات و SQLite، ۱۴ فرمول اصلی/۷۰ ردیف/۵ طبقه، بازبینی و انتقال به BOQ، خروجی XLSX/PDF، بدون `QApplication` | 75.06 ثانیه؛ PASS | 70.06 ثانیه؛ PASS | ۲ PASS |
| B / qt | ۷۰ ردیف جدول، انتخاب و اسکرول/مرتب‌سازی Qt، بدون ساخت سرویس پروژه یا SQLite | 5.01 ثانیه؛ PASS | 5.02 ثانیه؛ PASS | ۲ PASS |
| C / integrated | آزمون اصلی بدون تغییر `test_real_qt_fourteen_operations_five_floors_and_all_reports` با Qt، SQLite و گزارش | 115.09 ثانیه؛ PASS | 125.12 ثانیه؛ PASS | ۲ PASS |

مشخصات ثبت‌شده همان Run: Windows Server 2022 / `10.0.20348`، Python `3.12.10`، PySide6 و Qt `6.12.0`، SQLite `3.49.1`. گام کنترل یکسان‌بودن Blob کد محصول و فایل آزمون پیش از اجرا PASS شد. `native_root_cause_proven=false` در Summary اصلی هر سه مسیر ثابت مانده است. نمونه‌های RSS اوج واقعی حافظه نیستند و برای تشخیص نشت/رفع مشکل قابل استفاده قطعی نیستند.

## تفسیر و مرز نتیجه
- این آزمون فقط نشان می‌دهد هر سه مسیر در **دو تلاش موجود** موفق‌اند. **آزمون Qt مستقل محدود به جدول** است و تمام ویژگی‌های `ManualTakeoffDialog`، signal-slot و ساخت/تخریب مشترک ویجت‌ها را پوشش نمی‌دهد.
- آزمون core از API واقعی سرویس/SQLite و ۱۴ فرمول موجود استفاده می‌کند اما رویدادهای Qt را حذف کرده؛ بنابراین برای اثبات مستقل نبودن مشکلات Native در هریک از اجزا کافی نیست.
- شواهد قبلی `0xC0000005` روی Windows در Runهای https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632 و https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40821287426 همچنان معتبرند. سبز شدن نمونه جدید شکست‌های قبلی را خنثی نمی‌کند.
- این مجموعه به‌تنهایی اثبات نمی‌کند مشکل فقط در «ترکیب Qt و SQLite» است، زیرا حتی مسیر ترکیبی هم این بار PASS شده است. علت DLL/Native ناشناخته است.
- هیچ کد محصول یا آزمون اصلی تغییر نکرد، صرفاً اسکریپت تشخیصی، قابلیت انتخاب سه سناریو در runner و Workflow ایجاد شدند.

## گام بعدی دقیق در همان P6-5
به‌جای افزایش فازها یا بهینه‌سازی حدسی، تشخیص محافظت‌شده Native ویندوز باید بر **حلقه‌های واقعی signal-slot و عمر ویجت‌ها** در هنگام `review/commit/refresh_saved_rows` متمرکز شود. در صورت بازتولید، فقط exception code، نام ماژول و stack بدون Dump حافظه شخصی ذخیره شود. سپس آزمون مستقل RED→GREEN و رگرسیون واقعی پیش از تغییر موتور/اعلام رفع کرش الزامی است.

## خلاصه وضعیت پروژه و این صفحه
نقشه راه ثابت **۸ فاز** و پیشرفت رسمی **۸۵٪**؛ فاز ۶ اولویت ۵ **PARTIAL**. گیت اجرای تفکیکی **GREEN محدود**، گیت پایداری Windows **OPEN/RED تاریخی**. PR #34 **Open/Draft/Unmerged**، بدون Merge، Force Push، EXE/Release یا تغییر main؛ P6-6 و فاز ۷ شروع نشده‌اند. در این چت سه سناریو با شش JUnit PASS بررسی شدند؛ منشأ خطای متناوب همچنان باز است.
