# StructuralPro | فاز ۶، اولویت ۵ | تفکیک Native: Core/SQLite در برابر Qt و آزمون یکپارچه

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**نتیجه:** اجرای تشخیصی **GREEN محدود (۶ PASS)**؛ علت Native Access Violation همچنان **NOT PROVEN**؛ گیت پایداری Windows به دلیل بازتولید قبلی **OPEN/RED تاریخی**؛ P6-5 **PARTIAL**.

## دلیل انجام مأموریت
[Run #40764179632](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632): Windows در دومین تکرار unprofiled با `0xC0000005` و JUnit مفقود شکست خورد. [Run #40821287426](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40821287426): همان کد محصول و آزمون روی یک Windows Runner و یک dependency environment: دو PASS تاریخی، یک CRASH `0xC0000005` در Checkout جاری با زمان ۵۰٫۰۵ ثانیه و بدون JUnit، یک PASS جاری. خطا **واقعاً متناوب** است؛ چهار PASS پیشین درمان آن نیست.

هدف این مأموریت، آزمایش کنترل‌شده مستقل برای تفکیک مسیرهای Python/SQLite و رویدادهای Native Qt، **بدون اصلاح محصول** بود.

## طراحی مستقل آزمون جدید
فایل تشخیصی خارج از کشف عادی تست‌ها: `scripts/diagnostics/p6_native_isolation_oracles.py`. ابزار موجود `scripts/diagnose_windows_native_crash.py` صرفاً پذیرش سه انتخاب `--arm core|qt|integrated` را اضافه کرد؛ حالت پیش‌فرض `integrated` و آزمون قبلی بدون تغییر محفوظ‌اند. Workflow جدید `.github/workflows/phase6-windows-native-isolation.yml` با **یک Windows Server 2022 Runner** و **یک مجموعه وابستگی** هر بازو را در دو subprocess جدا اجرا کرد:

| بازو | سناریوی واقعی | محدودیت شواهد |
|---|---|---|
| A `core` | استخراج AST ثابت ۱۴ ورودی از **همان آزمون اصلی** بدون import Qt آزمون؛ ثبت مستقیم ۱۴ ردیف مستند، کپی چهار طبقه تا ۷۰ ردیف با هویت مستقل، رد ویرایش ناقص، بازبینی/قطعی ۷۰ ردیف، اعتبارسنجی ۷۰ BOQ و مقدارهای دقیق Decimal، خروجی واقعی PDF/XLSX و بازگشایی SQLite | `QCoreApplication.instance() is None` پیش و پس از سناریو؛ PySide6.QtCore ممکن است import شود ولی event loop یا QWidget ساخته نمی‌شود |
| B `qt` | `QApplication` Native Windows و `QTableWidget` با ۷۰ سطر؛ چهار دوره Sort/Scroll/Click/Selection، جمعاً ۲۸۰ انتخاب کنترل‌شده | **نه فرم کامل StructuralPro**؛ نه `StructuralProApp`، نه SQLite و نه callbackهای واقعی محصول |
| C `integrated` | **همان** `tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports`، بدون تغییر | مثل هر تکرار محدود دیگر، نبود کرش علت را اثبات نمی‌کند |

سه Blob مرجع در CI تأیید شد: `manual_formula_register.py` SHA `4e3750a0e797073d40bacb395e448da4f14b6c56`، `manual_formula_controls.py` SHA `07e8ce4567eec5122253cd220a49fed6e2e27d9e`، `tests/test_manual_formula_fivefloor_closure.py` SHA `f81c979051bcbaaf00015fa411314e28f370b291`؛ `core/projects/store.py` نیز SHA `0aa448bcc0f67bab12c37592f7abf01fd0e1765d` دست‌نخورده ماند.

## CI واقعی و JUnit
- [Run #40822722934](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40822722934): `completed/success` بر روی Commit `487d4079a2942d24946fb5c07f2cc448cdd6de0f`.
- Artifact قابل ممیزی `p6-windows-three-arm-native-isolation`، ID `12876045500`، ZIP SHA256 `050b35b560e4b3727dc1974f3251ac38ebc073c88aca94326bfd68490f4c3342`.
- همه آزمون‌ها `exit=0`، `timed_out=false`، JUnit **۱ PASS/صفر FAIL، ERROR یا SKIP** در هر subprocess؛ هیچ `0xC0000005` جدید در این Run رخ نداد.

| مسیر | تکرار ۱ wall | تکرار ۲ wall | نتیجه |
|---|---:|---:|---|
| A: ۷۰ ردیف Core + SQLite بدون QApplication | ۷۵٫۰۶ ثانیه | ۷۰٫۰۶ ثانیه | هر دو PASS |
| B: ۷۰ سطر Qt فقط، ۲۸۰ رویداد انتخاب | ۵٫۰۱ ثانیه | ۵٫۰۲ ثانیه | هر دو PASS |
| C: Qt + Core + SQLite + خروجی، آزمون اصلی | ۱۱۵٫۰۹ ثانیه | ۱۲۵٫۱۲ ثانیه | هر دو PASS |

**نکته مقایسه:** سناریوها هم‌اندازه نیستند و زمان‌های این جدول معیار درصد اختلاف سرعت محصول، overhead ذاتی Qt، یا اثبات منشأ crash نیستند. RSS دوره‌ای نمونه‌برداری شده است و peak واقعی محسوب نمی‌شود. عبارت `valid_original_test_pass` در runner برای بازوهای جدید به معنای **JUnit معتبر همان بازو** است؛ تنها بازوی C اجرای «آزمون اصلی» محسوب می‌شود.

## محیط مشترک Windows
Manifest از همان Run: Python `3.12.10`، PySide6/Qt/shiboken6 `6.12.0`، SQLite `3.49.1`، pytest `9.2.0`، Windows build `10.0.20348`. fingerprint کتابخانه‌های Allowlist موجود است. چون در این اجرای تشخیصی crash رخ نداد، رویداد Application Error 1000 جمع‌آوری نشد و نام DLL عامل خرابی نامشخص باقی ماند.

## نتیجه‌گیری با محدودیت علمی
۱. مسیر مستقل **Core+SQLite با ۷۰ ردیف** در ۲ تکرار PASS شد، بنابراین خرابی قطعی و بازتولیدشونده در این مسیر مشاهده نشد؛ نفی قطعی خطای متناوب Python/SQLite نیست.
۲. جدول ساده **Native Qt بدون SQLite** نیز PASS شد؛ از این آزمایش نمی‌توان سالم‌بودن تمام callbackهای واقعی پنجره متره را نتیجه گرفت.
۳. **سناریوی کامل** ۲ PASS گرفت ولی قبلاً با `0xC0000005` شکست خورده است؛ بنابراین **ROOT CAUSE NOT PROVEN** و گیت Windows **OPEN** باقی می‌ماند.

**قدم بعدی داخل همین P6-5:** تقسیم تعامل‌های فرم واقعی `ManualTakeoffDialog` به subflowهای محدود (Selection/Refresh، Review/Commit، Report/Close)، با حفظ Oracle مقدار، نسخه، BOQ و عدم دگرگونی کد محصول. شواهد کامل crash و احتمال DLL تنها در آزمون Native مجدد قابل استناد است؛ هیچ بهینه‌سازی `catalog()/verified()` را به‌عنوان رفع Access Violation محسوب نکنید.

## خلاصه پروژه و این گفت‌وگو
- نقشه‌راه دقیقاً **۸ فاز**، پیشرفت رسمی **۸۵٪** بدون تغییر.
- **P6-5 PARTIAL**؛ P6-6 و فاز ۷ شروع نشده‌اند.
- PR #34 باید Open/Draft/Unmerged بماند؛ بدون Merge، تغییر main، EXE/Release یا Force Push.
- در این چت، سه بازوی مجزا واقعاً ساخته، شش تست Windows اجرا و Artifact/JUnit بررسی شد. کد محصول و آزمون مرجع بدون تغییر ماندند؛ گیت کلی پایداری هنوز باز است.
