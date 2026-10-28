# کنترل نهایی رگرسیون گسترده جاری، ۲۸ اکتبر ۲۰۲۶

**حکم محدود و قابل استناد: PASS روی Linux برای مجموعه جاری.** این گزارش وضعیت تاریخی `verification-20261027-three-gates` را حذف یا بازنویسی نمی‌کند؛ شواهد قدیمی دو شکست baseline برای آن کد همچنان معتبرند.

## مرجع قطعی
- PR #34: `Asanda021/StructuralPro-Recovery`، شاخه `feature/phase6-p5-workspace-e3-e6-20261027`، `OPEN / DRAFT / UNMERGED`.
- کد و آزمون دقیق اجراشده: `7cbeac9b245586bf83922bc4dbf2783de56214ad`.
- Commit راه‌انداز Workflow (تغییر CI فقط): `8bb1f8976747013938f20e29680780601156cd74`.
- [اجرای GitHub Actions #40648107800](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40648107800)، Job `current-suite-linux` با شناسه `122681551868`، نتیجه `completed/success`.
- مرحله `Assert source SHA before broad QA`: موفق، Checkout دقیق روی `7cbeac9b...` قفل بوده است.
- فرمان اجرا: `python scripts/run_quarantined_workflow_qa.py --mode current --timeout 1200 --json phase6-broad-current.json --log phase6-broad-current.log --junit phase6-broad-current.xml`.
- JUnit / log / JSON واقعی و اصلی در Artifact `p6-broad-current-linux-7cbeac9b2455` همان Run وجود دارند؛ Artifact فعلاً منقضی نیست.

## نتیجه واقعی
| شاخص | مقدار |
|---|---:|
| test cases | ۸۳۷۵ |
| PASS | ۸۳۷۰ |
| FAIL | ۰ |
| ERROR | ۰ |
| SKIP | ۵ |
| pytest exit code | ۰ |
| timed_out | false |
| overall_green (طبق Runner رسمی) | true |

نتیجه از لاگ GitHub Actions و JSON چاپ‌شده Runner رسمی گرفته شده، نه از تخمین شمارش یا تبدیل گزارش ناتمام به PASS. پنج SKIP به معنی PASS نیستند؛ جزئیات هر مورد باید از JUnit Artifact استخراج شود. این Run فقط Linux بوده و جای اجرای کامل ۸۰۰۰+ تست روی Windows یا UAT فیزیکی را نمی‌گیرد.

## رفع دو شکست تاریخی
1. `tests/test_master13_desktop_shell_runtime.py::test_actual_shell_navigation_calendar_and_ribbon` روی شاخه PR34 با Commit `1e02a13e24ff443b9025e4c8d2aaabfdc0721c96` اصلاح شد: ناوبری اصلی افقی، درخت پروژه فقط در Dock معتبر E5؛ بدون حذف کنترل‌های واقعی.
2. `tests/test_phase6_p1_font_diagnostics.py::test_qt_glyph_capability_and_render_diagnostics` با Commit `7cbeac9b245586bf83922bc4dbf2783de56214ad` و اصلاح `app/desktop_preferences.py`: بررسی واقعی glyph فارسی، انگلیسی و اعداد؛ رندر QPainter و QLabel.

این دو آزمون هم در بسته اختصاصی CI #40646950999 روی Linux و Windows با **۴۶۳ PASS در هر سیستم** پذیرفته شده‌اند و هم در جمعیت جاری Linux که اکنون صفر FAIL/ERROR دارد. دو شکست مربوط به snapshot قدیمی #005a55f دیگر نباید به‌عنوان شکست HEAD فعلی نقل شوند.

## مرزهای باز و ادامه
- مجموع QA جاری **Linux** با ۵ SKIP و صفر شکست تأیید شد؛ **Windows** فقط بسته اختصاصی ۴۶۳ و ۱۳۰ historical و ۲۶ security و DPI را برای این کد گذرانده؛ رگرسیون کامل ۸۰۰۰+ Windows در این Run انجام نشده است.
- ۱۹۳ Workflow قرنطینه‌شده فقط مطابق محافظ امن در درخت Disposable بررسی شدند؛ هیچ Workflow تاریخی اجرا، Release/EXE، Merge یا ForcePush انجام نشده است.
- P6-4/P6-5 هنوز **PARTIAL**: قراردادهای E6 مالکیت مشترک/Crosswalk، W1 IFC MEP، E4 ناوبری تخصصی/DWG، Windows UAT فیزیکی و A2 تجاری همچنان در وضعیت قبلی `BLOCKED/NOT VERIFIED` هستند.
- `main` در زمان کنترل `9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` بوده است. برنامه دقیقاً ۸ فاز و پیشرفت ثبت‌شده ۸۵٪ ثابت می‌ماند.

**گام بعدی پذیرش:** استخراج اسامی ۵ SKIP از JUnit، در صورت نیاز اجرای هدفمند Windows برای موارد بومی، سپس بررسی قراردادهای تخصصی باقی‌مانده، بدون تبدیل `BLOCKED` به `PASS` بدون مدارک مهندسی.
