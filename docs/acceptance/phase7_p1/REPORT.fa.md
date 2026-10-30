# StructuralPro | فاز ۷، اولویت ۱: صحت گزارش‌های فارسی و چهار قالب خروجی

**گزارش اجرایی ۳۱ اکتبر ۲۰۲۶** | مرجع PR [#35](https://github.com/Asanda021/StructuralPro-Recovery/pull/35)

## دامنه مصوب اولویت ۱
ارتقای **همان** مسیرهای موجود تهیه گزارش با تمرکز بر دقت Decimal، جدول و صفحات فارسی/RTL، تاریخ جلالی، سربرگ/پابرگ، و فایل‌های PDF/XLSX/DOCX/CSV؛ بدون موتور BOQ/مالی/متره دوم. تولید نقشه دوبعدی خودکار اولویت ۲ است و در این اجرا آغاز نشده است. قالب سفارشی/خروجی دسته‌ای E7 در اولویت ۳ مستقل توسعه می‌یابد.

## کد و اصلاحات واقعی
- منبع فاز ۶ برای شروع شاخه: `66022c2dd1476b37399d83480be108a0002cae96`. PR #34 پس از آن فقط مدارک تصمیم مالک را تغییر داده است.
- Commit عملکردی و تست اصلاح‌شده: `b55b7da1404742d97a89638215b2c5cd1e71ab17`.
- `core/reports/decimal_values.py`: تبدیل fail-closed Decimal و جمع با precision وابسته به کوچک‌ترین و بزرگ‌ترین رقم موجود؛ عدم گردکردن مقادیر منبع.
- `core/reports/designer.py`: جمع‌بندی گروهی دقیق حتی برای اعداد بزرگ‌تر از precision پیش‌فرض Decimal؛ گروه مخفی‌شده در ستون نمایش مانع جمع دقیق نیست.
- `core/reports/service.py`: جمع دقیق مبلغ گزارش به‌جای float؛ هیچ تغییر در تراکنش/BOQ.
- `core/reports/project_report.py`: اعتبارسنجی عدد متناهی و غیرمنفی بدون coercion به float؛ داده بد به‌صورت خطا.
- `core/reports/production.py`: جمع دقیق ردیف‌های گزارش؛ حفظ داده اصلی.
- `core/reports/formatting.py`: نمایش مبلغ با Decimal، بدون گم‌شدن دقت در فرمت‌کردن.
- آزمون‌های جدید `tests/test_phase7_p1_exact_persian_reports.py` و `tests/test_phase7_e7_decimal_report_layout.py` به همراه تست‌های قدیمی فرمت‌های چهارگانه اجرا شدند.

## شواهد RED/GREEN قابل حسابرسی
- اجرای اولیه [#41126853799](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41126853799) در Linux: **۵۷ PASS، ۳ FAIL** به‌سبب باقی‌ماندن یک ارجاع `subtotal` در انتهای گروه‌بندی؛ خطا حذف یا Skip نشد و با Commit بعدی اصلاح شد.
- اجرای اصلاح‌شده [#41127034901](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41127034901) در SHA `b55b7da1404742d97a89638215b2c5cd1e71ab17`: **Linux ۶۰ PASS و Windows Native ۶۰ PASS؛ صفر FAIL/ERROR/SKIP**؛ یک `fitz` FutureWarning موجود در هر محیط ثبت شده است.
- آزمون‌ها رشته فارسی و شناسه صفرابتدایی، ۱۵+ رقم Decimal در XLSX، استخراج Word با bidi، ساخت PDF، CSV با BOM، تاریخ جلالی، صفحه‌بندی، مقادیر نامعتبر/NaN/Infinity، حفظ snapshot داده و نتایج عددی را کنترل می‌کنند. کیفیت بصری تمام صفحات Office/چاپ واقعی با این CI اثبات نمی‌شود.
- [رگرسیون جامع #41127109963](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41127109963) روی SHA `cf4a446d82e85bc48315d9d7f235b65053684e6f` راه‌اندازی شد. **۷ Job برابر SUCCESS**؛ Linux: **۸٬۵۱۰ PASS، ۵ SKIP، صفر FAIL/ERROR**، Windows (۳ شارد): **۸٬۵۰۸ PASS، ۷ SKIP، صفر FAIL/ERROR**؛ `verify-full-union`: **۱۲ PASS**، ۷۲۳ ماژول، پوشش دقیق **۸٬۵۱۵ کیس** در هر سیستم، صفر timeout، JUnit و SHA-256 همه Artifactها راستی‌آزمایی شد. این SHA نسبت به تست قبلی فقط Workflow گسترده را اضافه کرده است.

## تصمیم و مرزهای پذیرش
- `P7_P1_TARGETED_WINDOWS_LINUX = PASS_60_EACH`.
- `P7_P1_BROAD_CROSS_MODULE = PASS_8515_CASES_EACH_OS_UNION_VERIFIED`؛ اجرای #41127109963 (SHA `cf4a446...`) تأیید شد.
- `PHYSICAL_MS_OFFICE_PRINT = DEFERRED_TO_PHASE8` طبق تصمیم صریح مالک، بدون نتیجه فرضی.
- `PHASE7_P1_AUTOMATED_TECHNICAL_SCOPE = ACCEPTED`؛ کنترل بصری نهایی MS Office و چاپ فیزیکی در فاز ۸ انجام می‌شود و اکنون PASS فرضی ندارد.
- هیچ تغییر main، Merge، EXE، Release یا ForcePush انجام نشده؛ PR #35 Draft/Unmerged می‌ماند.

## وضعیت پروژه و چت این صفحه
- فازهای ۱ تا ۵: سوابق پذیرش فنی محفوظ.
- فاز ۶: تحویل فنی خودکار؛ G4 فیزیکی به آزمایش نسخه نهایی در فاز ۸ موکول شده است.
- فاز ۷: **اولویت ۱ از نظر پذیرش فنی خودکار بسته شد**؛ اولویت ۲ در PR #36 شروع شده و خروجی SVG و اتصال نسخه‌دار SQLite ↔ BOQ با آزمون‌های هدفمند وجود دارد؛ اولویت‌های ۳ تا ۶ آغاز نشده‌اند.
- فاز ۸: پذیرش نهایی، شروع نشده.
- تعداد فازها دقیقاً ۸ و درصد رسمی اعلام‌شده کل پروژه ۸۵٪ بدون تغییر است.
