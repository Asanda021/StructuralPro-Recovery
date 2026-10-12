# StructuralPro — گزارش اجرای مراحل ۱ تا ۳ برای متره دستی نازک‌کاری

**تاریخ:** ۲۰ مهر ۱۴۰۵ / ۱۱ اکتبر ۲۰۲۶  
**مخزن:** `Asanda021/StructuralPro`  
**PR:** https://github.com/Asanda021/StructuralPro/pull/481  
**آخرین SHA شاخه PR هنگام بررسی:** `57c1e941d8ec3e371c3332e0a0b77d21102b84a5`  
**وضعیت:** Open / Draft / Not merged

## مرحله ۱ — اجرای آزمون

- فایل ZIP اصلاح‌شده Work از نظر SHA-256 بررسی شد: `fda09d1b8058c8c876c9101f7353b65402196f46ad90baa5b61ed46055047a6d`.
- آزمون واقعی قابل اجرای محلی: `python -m pytest -q /mnt/data/StructuralPro_Finish_Patch_Independent_Branch_Tests.py` → **۷۳ موفق در ۰٫۰۸ ثانیه**. این آزمون روی شاخه محاسباتی جداشده از Patch است، **نه روی کل Checkout GitHub**.
- `PySide6` در محیط جاری نصب نیست، GitHub.com از داخل container به دلیل DNS پاسخ نمی‌دهد؛ بنابراین Checkout کامل، تست Qt/offscreen، ذخیره SQLite پروژه و اجرای گزارش در همین نوبت قابل تأیید اجرایی نبودند.
- در Github برای آخرین Commit PR #481: workflow runs = ۰ و commit statuses = ۰؛ «CI سبز» قابل ادعا نیست.

## مرحله ۲ — اصلاحات واقعی روی شاخه PR #481

- ۱۳ عملیات با اسمبلی و قالب‌های ورود صریح وارد مخزن شدند.
- پنجره RTL اختصاصی از همان فرم متره دستی PR #468 باز می‌شود و به همان سرویس `StructuralProApp.add_assembly_takeoff` متصل است؛ سرویس متره موازی ایجاد نشده است.
- ثبت **شناسه ثابت محل برای نازک‌کاری الزامی** شد؛ طبقه الزامی، آکس اختیاری و بدون حدس است؛ برای همان نوع عملیات + طبقه + شناسه محل، ثبت تکراری رد می‌شود.
- در خروجی‌های پروژه، ردیف‌های `work`, `procurement`, `material` با نقش و مرجع مشخصات ذخیره می‌شوند؛ فقط `work` وارد BOQ پرداختی می‌شود.
- فیلتر نقش در **۵ مسیر بازسازی BOQ** یکسان شد تا افزودن متره معمولی، متره نقشه‌ای، اصلاح ردیف یا پیشنهاد AI اجزای تأمین/مصرف را به BOQ بازنگرداند.
- یک نقص مرتبط هم اصلاح شد: ساخت BOQ پس از ثبت متره معمولی، اکنون گروه/رشته هر ردیف قبلی را حفظ می‌کند، نه اینکه گروه همه ردیف‌ها را با گروه آیتم تازه جایگزین کند.
- آزمون‌های جدید برای پنج طبقه، ذخیره/بازیابی پس از ایجاد سرویس مجدد، کنترل تکراری‌ها، تغییر نسخه، مقادیر قابل پرداخت و تهیه مصالح، فرم Qt RTL، و مسیر Excel/Word/PDF **به مخزن اضافه شده‌اند اما اجرا در Checkout کامل هنوز ممکن نبوده است**.
- آزمون Qt جدید عمداً در نبود PySide6 بی‌سروصدا Skip نمی‌شود.

## مرحله ۳ — وابستگی و تصمیم ادغام

- PR #481 (Draft) ← PR #468 (Draft) ← PR #467 (Draft) ← PR #462 (Draft؛ محافظ Build/Release) ← `main`.
- PR #464 نیز مستقل و Draft است و در مسیر `core/takeoff/manual_workbench.py` با #468 هم‌پوشانی دارد.
- PR #481 از نظر GitHub `mergeable=true` است؛ این فقط عدم تشخیص تعارض فوری است و به معنای موفقیت آزمون یا اجازه Merge نیست.
- **نتیجه ممیزی: Merge انجام نشود** تا آزمایش کامل و بازبینی انسانی/مهندسی، مرور امنیت Workflow و تعیین تکلیف PRهای پیش‌نیاز انجام شود. هیچ Build/Installer/Release ایجاد نشده و main دست‌نخورده باقی مانده است.

## دستور آزمون در Checkout کامل دارای وابستگی و Qt

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests/test_finish_takeoff_assemblies.py tests/test_finish_takeoff_ui_runtime.py tests/test_finish_takeoff_report_contract.py tests/test_master13_phase2_manual_transaction.py tests/test_master13_phase2_manual_dialog_runtime.py tests/test_manual_takeoff_workbench.py tests/test_manual_takeoff_input.py tests/test_manual_takeoff_ui_wiring.py
```

**نکته:** آزمون PDF در سطح وجود و بازشدن خروجی است؛ صحت بصری فونت فارسی، شکست صفحات، جدول‌ها و سربرگ شرکت در #480 هنوز نیازمند آزمون تصویری و بهسازی مستقل است. همچنین ورود ویرایش/حذف نسخه‌ای اسمبلی نازک‌کاری پس از ذخیره هنوز کامل نیست.

**آخرین وضعیت:** توسعه ثبت‌شده در PR، هنوز فاقد پذیرش نهایی و تست یکپارچه روی Checkout کامل است.
