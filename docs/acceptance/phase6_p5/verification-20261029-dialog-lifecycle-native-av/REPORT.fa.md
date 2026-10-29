# StructuralPro | P6-5 | بازتولید Access Violation در چرخه عمر پنجره واقعی Qt

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**حکم:** Windows CI **RED**؛ Native Access Violation با کد **0xC0000005** دوباره ثبت شد؛ علت Native هنوز NOT PROVEN؛ اصلاح کد محصول صفر؛ P6-5 PARTIAL.

## هدف و روش
آزمون‌های قبلی Core+SQLite، Qt جدول ساده و فرم واقعی بدون تخریب مکرر پنجره سبز بودند؛ خطای تاریخی پنج‌طبقه هنوز باز بود. یک Oracle تشخیصی مستقل با نام test_native_real_dialog_destroy_reopen_every_fourteen_commits در scripts/diagnostics/p6_native_isolation_oracles.py ایجاد شد. از ۱۴ CASE مصنوعی مرجع استفاده شد؛ مجموعاً ۷۰ ردیف در SQLite واقعی ساخته می‌شوند. در سناریوی کامل، پنج چرخه ۱۴‌تایی Review و Commit با کلیک Qt واقعی اجرا می‌شود؛ بعد از هر چرخه، Sort/Filter/Refresh، حذف QObject/ویجت با DeferredDelete و کنترل isValid، بستن Store و بازگشایی مستقل SQLite و کنترل BOQ انجام می‌شود.

Runner موجود فقط بازوی dialog_lifecycle را گرفت. Workflow جدید .github/workflows/phase6-windows-dialog-lifecycle.yml دو بار Lifecycle را در فرآیند مستقل و یک بار تست اصلی یکپارچه را روی Windows Server 2022 / Python 3.12 / native Qt اجرا می‌کند. CI روی Blob SHA فایل‌های محصول و آزمون اصلی قفل PASS داشت؛ هیچ فایل app/، core/ یا آزمون اصلی تغییر نکرده است.

## شواهد اصلی
[GitHub Actions Run #40841278108](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40841278108) در commit dfa176b8af5ba0b287d57ec0c22cce0492b51357 با completed/failure پایان یافت. خطای گیت ناشی از شکست واقعی بازوی Lifecycle دوم است، نه فقط ایراد قالب گزارش.

[Artifact ID 12883525637](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40841278108/artifacts/12883525637) با نام p6-windows-real-dialog-lifecycle-no-debugger؛ SHA-256 ZIP: c8a0bfab365fcc16a13c1848a46e06f277753c892b51cfb2b380eef0a47285cf. Summary، لاگ و فایل‌های JUnit واقعی بازدریافت و بررسی شدند.

| بازو | مدت | کد خروج | JUnit | Timeout | وضعیت |
|---|---:|---|---|---|---|
| Lifecycle شماره ۱ | 125.08s | 0x00000000 | ۱ PASS، صفر FAIL/ERROR/SKIP | false | PASS؛ پنج چرخه، ذخیره و بازگشایی و BOQ بررسی شدند |
| Lifecycle شماره ۲ | 50.05s | **0xC0000005** | **فاقد فایل JUnit** | false | **Native CRASH**؛ سناریو کامل نشد |
| Integrated مرجع | 125.09s | 0x00000000 | ۱ PASS، صفر FAIL/ERROR/SKIP | false | PASS |

Windows Event ID1000 در نمونه شکست وضعیت no_matching_event داشت؛ ماژول PE/DLL مقصر از این Run معلوم نشد.

## آخرین مرز مشاهده‌شده
لاگ خطادار پیام صریح Windows fatal exception: access violation دارد. آخرین Stack پایتون:
- scripts/diagnostics/p6_native_isolation_oracles.py:373، فراخوانی dialog.refresh_formula_rows()
- app/manual_formula_controls.py:114، تابع refresh
- app/manual_formula_controls.py:103، تابع rows
- core/platform/application.py:890، load_manual_formulas
- manual_formula_register.py:239 load؛ :98 verified؛ :37 clean؛ :22 catalog
- json.decoder.raw_decode:354.

یک خروجی faulthandler_timeout چهل‌وپنج‌ثانیه‌ای با trace خطا درهم‌تنیده است؛ خود اجرا timed_out=false بوده است. Stack پایتون نه نام DLL خطاکننده را ثابت می‌کند و نه اثبات می‌کند JSON، SQLite، Qt، deepcopy یا تخریب QWidget علت خطاست. تنها یک مرز مرتبط با Refresh پس از عملیات روی ویجت واقعی ثبت شده است.

## تصمیم اجرایی
Native AV واقعی و متناوب بازتولید شد؛ بنابراین **گیت Windows همچنان RED است**. گام بعدی، checkpoint دقیق قبل/بعد Refresh و teardown و در صورت بازتولید تحت CDB کالیبره‌شده، گردآوری exception PC module بدون dump، memory، raw debugger logs یا اطلاعات شخصی است. بهینه‌سازی عملکرد catalog/verified جدا از ریشه Native است و درمان حدسی پذیرفته نیست. هیچ کد محصول دست‌کاری نشده و ادعای رفع کرش مطرح نیست.

## خلاصه وضعیت پروژه و گفت‌وگو
نقشه‌راه ثابت ۸ فاز، پیشرفت رسمی ۸۵٪؛ فاز ۶ اولویت ۵ PARTIAL، Windows stability RED. PR #34 Open/Draft/Unmerged، بدون Merge، ForcePush، تغییر main، EXE/Release یا شروع P6-6/فاز ۷. در همین گفت‌وگو آزمون جدید ساخته شد و **دو PASS معتبر و یک کرش واقعی** در Artifact آن ثبت شد.
