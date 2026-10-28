# StructuralPro / PR #34 | اولویت فوری: baseline پنج‌طبقه و اندازه‌گیری مرحله‌ای
تاریخ ثبت: ۲۹ اکتبر ۲۰۲۶ (۱ آبان ۱۴۰۵)؛ معیار: شواهد اجرای واقعی، نه برآورد.

## دامنه و مرجع
مخزن: `Asanda021/StructuralPro-Recovery`؛ PR #34: https://github.com/Asanda021/StructuralPro-Recovery/pull/34 ؛ شاخه: `feature/phase6-p5-workspace-e3-e6-20261027`.
مرجع کد آزموده `cd855297af657a382c76909eabad7523688148a2`. برای آزمون Baseline دقیقاً `5fb5c69cec5751bbbecf7018c843c5e921128bb2` در Checkout اجرا شد. همان آزمون اصلی `tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports` با fixture مصنوعی، بدون دستکاری، و با JUnit واقعی استفاده شد.

## مقایسه سه اجرای قبلی روی Source SHA یکسان
1. https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943 : Linux کرش با کد `-11`/SIGSEGV در حدود ۳۴٪ تست‌ها، JUnit نهایی موجود نیست؛ Windows shardهای ۳گانه موفق اما Union همان Run به‌علت شکست Linux اجرا نشده است.
2. https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751958863 : Linux ۸٬۴۱۸ PASS، ۵ SKIP و Windows مجموع سه shard برابر ۸٬۴۱۶ PASS، ۷ SKIP؛ هر دو ۸٬۴۲۳ testcase و Union موفق.
3. https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40756726986 : GDB روی prefix تعداد ۲٬۸۷۹ آزمون موفق و focus دوبار ۲۲ آزمون موفق، بدون native signal ضبط‌شده. عدم بازتولید کرش، اثبات رفع مشکل نیست.

## baseline بدون cProfile
اجرای واقعی: https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632
- Linux سه subprocess تازه: ۸۰٫۳۰، ۷۵٫۱۰ و ۷۵٫۰۶ ثانیه؛ هر تکرار ۱ PASS، JUnit اصلی و خروجی `exit=0`.
- Windows تکرار نخست ۹۰٫۰۸ ثانیه / ۱ PASS؛ تکرار دوم ۶۵٫۰۵ ثانیه / `3221225477=0xC0000005` Access Violation / JUnit ندارد و سوم به علت شکست اجرا نشد. `timed_out=false`. شاخص حافظه نمونه‌برداری‌شده به‌ترتیب ۱۸۸٫۷۸۹ و ۱۱۵٫۳۰۵ MiB؛ **RSS نمونه‌ای است نه peak واقعی**.
- Artifact اصلی Windows: `p6-fivefloor-plain-baseline-windows`، Artifact ID `12849033197`.
- Trace خرابی Windows در حلقه `commit -> verified -> clean -> catalog -> pathlib.read_text` دیده شده است؛ این stack اثبات علت در pathlib یا JSON نیست. crash بدون profiler وقوع یافته است.

## آزمایش مرحله‌ای جداگانه بدون تغییر موتور محصول
ابزار صرفاً تشخیصی: `scripts/measure_fivefloor_stage.py`، اجرای Native Linux/Windows با Workflow `.github/workflows/phase6-fivefloor-staged-timings.yml` و کد ابزار در شاخه PR34. Workflow دقیقاً blobهای مرجع زیر را پیش از اجرا بررسی می‌کند:
- `core/takeoff/manual_formula_register.py`: `4e3750a0e797073d40bacb395e448da4f14b6c56`
- `app/manual_formula_controls.py`: `07e8ce4567eec5122253cd220a49fed6e2e27d9e`
- `tests/test_manual_formula_fivefloor_closure.py`: `f81c979051bcbaaf00015fa411314e28f370b291`
- اجرای معتبر CI: https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40765263869 ؛ اجرای ابتدایی https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40765237164 با خطای تنظیمی shallow Git `fatal: bad object` متوقف شد و به‌عنوان شکست محصول ثبت نمی‌شود.
- Linux از Artifact واقعی `p6-fivefloor-stage-offscreen`، Artifact ID `12848738784`: Oracle همان آزمون ۱ PASS؛ ۵۳٫۱۴۶ ثانیه wall شامل ابزار اندازه‌گیری. `verified()`: ۶۳۳ فراخوانی/۲۷٫۶۶۵۵۴۷ ثانیه تجمعی، `clean()`: ۴۱٬۱۱۲/۲۴٫۷۷۳۸۸۶ ثانیه، `catalog()`: ۴۱٬۳۰۶/۲۳٫۳۷۸۴۲۶ ثانیه، `deepcopy()`: ۸۹٬۰۴۵/۱۶٫۶۰۸۴۱۴ ثانیه، `evaluate_rows()`: ۶۵۲/۱٫۳۸۱۳۱۰ ثانیه، `fingerprints()`: ۱٬۳۷۲/۰٫۵۴۳۲۰۳ ثانیه.
- آزمایش مستقل ۲۰۰ فراخوانی روی کتابخانه ۸۵ خانواده واقعی: میانگین `catalog()` = ۰٫۵۶۸ میلی‌ثانیه، p95 = ۰٫۶۱۳ میلی‌ثانیه، بیشینه ۰٫۹۳۵۹ میلی‌ثانیه؛ Digest خروجی طی نمونه‌ها ثابت بوده است.
- این زمان‌ها در توابع تو در تو هستند و جمع نمی‌شوند. اجرای Instrumented به دلیل overhead معیار مستقیم سرعت قبل/بعد نیست.
- نتیجه Windows از Run مرحله‌ای باید صرفاً پس از دریافت JUnit و journal همان Run وارد این گزارش شود؛ در لحظه ثبت اولیه Linux موفق و Windows در حال اجراست. هیچ نتیجه پیش‌بینی‌شده را PASS فرض نکنید.

## تحلیل ایمنی و گام فنی مجاز
کاتالوگ در نسخه فعلی هر بار Inventory را از فایل می‌خواند و deepcopy می‌کند؛ `clean()` به دفعات زیاد آن را بازصدا می‌زند و `verified()` هر ردیف را از نو تأیید می‌کند. تکرار و هزینه مستند است، اما انتساب علت Access Violation به این الگو **اثبات نشده** است. ابتدا شواهد Windows را کامل کنید و ریشه‌یابی native جدا از کاهش هزینه CPU بماند. سپس تنها با Oracle مستقل/تست RED→GREEN، حفظ اعتبارسنجی و متریک قبل/بعد اقدام به اصلاح محصول شود.

## قیود و خلاصه وضعیت پروژه و گفت‌وگو
P6-5 همچنان **PARTIAL**؛ رگرسیون Broad روی یک SHA موفق، پذیرش همه خانواده‌ها/Windows UAT و پایداری بی‌کرش را اثبات نمی‌کند. PR #34 باید Open/Draft/Unmerged باقی بماند. بدون Merge، تغییر main، Force Push، EXE/Release و شروع P6-6/فاز ۷. نقشه‌راه دقیقاً ۸ فاز و پیشرفت ثبت‌شده ۸۵٪ است. این چت بر مقایسه سه اجرای واقعی، Baseline بدون profiler و اندازه‌گیری جداگانه هزینه توابع متمرکز شد؛ Access Violation مستقل از profiler به‌صورت واقعی بازتولید شد و بدون حدس زدن ریشه، اندازه‌گیری‌ها ثبت شدند.
