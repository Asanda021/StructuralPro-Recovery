# StructuralPro | P6-5 | تفکیک پنجره واقعی متره در Windows: مشاهده در برابر بازبینی و قطعی

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**حکم:** **چهار JUnit PASS محدود؛ Native ROOT CAUSE NOT PROVEN؛ Windows stability gate همچنان OPEN/RED تاریخی؛ P6-5 PARTIAL.**

## زمینه و سؤال آزمون
- [Baseline بدون پروفایلر #40764179632](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632): وقوع Access Violation واقعی `0xC0000005` در مسیر ثبت قطعی، بدون JUnit نهایی.
- [مقایسه هم‌محیط #40821287426](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40821287426): وقوع مجدد `0xC0000005` در callback بازبینی فرم واقعی، بدون JUnit. سه تکرار دیگر PASS شدند.
- [سه بازوی مستقل #40822722934](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40822722934): دو PASS در هر بازو (Core+SQLite مستقل، Qt جدول ساده، آزمون کامل اصلی)، ولی جدول ساده، فرم واقعی محصول نبود.
- پرسش فعلی: آیا خطا در صرفاً نمایش/انتخاب/Refresh **فرم واقعی** رخ می‌دهد یا در همان فرم همراه با عملیات Review/Commit و SQLite؟

## تغییرات صرفاً تشخیصی
- اضافه‌کردن آزمون‌های مستقل به `scripts/diagnostics/p6_native_isolation_oracles.py`:
  1. `test_native_real_manual_dialog_readonly_70_rows`: از **همان ۱۴ CASE مصنوعی آزمون مرجع** و کپی چهار طبقه، ۷۰ ردیف واقعی ثبت نسخه‌دار را قبل از ایجاد QApplication در SQLite می‌سازد؛ سپس پنجره واقعی `ManualTakeoffDialog` را باز می‌کند و انتخاب/مرتب‌سازی/Refresh تمام ۷۰ ردیف و عدم تغییر Digest پایگاه را کنترل می‌کند.
  2. `test_native_real_manual_dialog_review_commit_70_rows`: دقیقاً همان ۷۰ ردیف را قبل از Qt می‌سازد؛ سپس با `QTest.mouseClick` دکمه‌های واقعی Review و Commit برای هر ردیف را می‌زند، وضع هر مرحله را بررسی می‌کند، BOQ ۷۰ ردیفی و جمع دقیق ۱۴ عنوان در پنج طبقه را می‌سنجد و پس از بستن پروژه، SQLite را بازگشایی می‌کند. **این بازو Export اصلی یا ورود/کپی به‌وسیله UI را اجرا نمی‌کند**، پس جایگزین آزمون یکپارچه نیست.
- Runner `scripts/diagnose_windows_native_crash.py` فقط انتخاب `--arm dialog_read|dialog_commit` را افزوده است؛ مسیرهای `core|qt|integrated` دست‌نخورده‌اند. پایش دوره‌ای RSS/CPU، کد خروج، JUnit واقعی و Event ID1000 محدود در صورت شکست برقرار است؛ Dump حافظه ثبت نمی‌شود.
- Workflow جدید `.github/workflows/phase6-windows-dialog-split.yml`، Windows Server 2022، Python 3.12 و Qt Native Windows. **هیچ کد محصول یا آزمون اصلی تغییر نکرده است**. در CI Blob این فایل‌ها تأیید شد:
  - `manual_formula_register.py`: `4e3750a0e797073d40bacb395e448da4f14b6c56`
  - `manual_formula_controls.py`: `07e8ce4567eec5122253cd220a49fed6e2e27d9e`
  - `manual_takeoff.py`: `12828195669dc2586cc3d5300e0781cf93183135`
  - `core/projects/store.py`: `0aa448bcc0f67bab12c37592f7abf01fd0e1765d`
  - `test_manual_formula_fivefloor_closure.py`: `f81c979051bcbaaf00015fa411314e28f370b291`

## نتایج واقعی
- [GitHub Actions #40824120352](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40824120352)، Source SHA `b601c23a090aa5888c951dcdabdceff92184b78e`، **completed/success**.
- Artifact: `p6-native-real-dialog-read-vs-commit`، ID `12875937174`؛ ZIP SHA-256 `2da4ca0964405236e990594ced56121e26e27c8ead9307f9bde6af19ad443627`.
- داده دقیق و JUnit استخراج‌شده از Artifact، نه استنتاج از رنگ Workflow:

| بازو | تکرار | Wall | Exit | JUnit | RSS sampled MiB |
|---|---:|---:|---|---|---:|
| `dialog_read` فرم واقعی، بدون mutation | ۱ | 10.03s | `0x00000000` | ۱ PASS، صفر FAIL/ERROR/SKIP | 78.672 |
| `dialog_read` | ۲ | 5.00s | `0x00000000` | ۱ PASS، صفر FAIL/ERROR/SKIP | 2.441 |
| `dialog_commit` فرم واقعی و عملیات قطعی | ۱ | 120.11s | `0x00000000` | ۱ PASS، صفر FAIL/ERROR/SKIP | 114.324 |
| `dialog_commit` | ۲ | 115.08s | `0x00000000` | ۱ PASS، صفر FAIL/ERROR/SKIP | 111.703 |

- همه `timed_out=false` و `access_violation=false`؛ علت Native `native_root_cause_proven=false`.
- محیط مستند این Run: Python `3.12.10`، PySide6 و Qt `6.12.0`، SQLite `3.49.1`، Windows build `10.0.20348`.
- `max_observed_sampled_rss_mib` فقط نمونه ۵ ثانیه‌ای است و ممکن است در اجرای کوتاه دوم مقدار بسیار کم `2.441` ثبت کند؛ **اوج واقعی حافظه نیست**. زمان‌های بین بازوها نیز Benchmark هم‌ارز سرعت محصول نیستند.
- ابزار pytest با `faulthandler_timeout=45` ممکن است طی اجرای طولانی PASS، stack snapshot تایم‌اوت موقت چاپ کند؛ **این پیام کرش واقعی نیست** مگر کد خروج و JUnit آن را تأیید کند.

## جمع‌بندی با حدود استنتاج
- نمایش و انتخاب ۷۰ ردیف در فرم واقعی: دو PASS؛ به‌تنهایی خطای Native بازتولید نشد.
- Review/Commit با دکمه‌های واقعی Qt روی همان ۷۰ ردیف: دو PASS همراه با صحت BOQ و بازگشایی؛ کرش متناوب تاریخی را نفی نمی‌کند.
- هر دو crash تاریخی در callbackهای بازبینی/قطعی هنگام `verified() → clean() → catalog()` دیده شده‌اند؛ فریم Python **نام DLL مقصر یا منشأ حافظه را ثابت نمی‌کند**.
- گام بعدی **همین P6-5**: تشخیص Native از جنس crash-site با Debugger غیرمداخله‌گر/stack و checkpoint کم‌حجم در مرزهای Review/Commit، بدون ذخیره memory dump یا اطلاعات شخصی؛ فقط بعد از ریشه‌یابی معتبر، آزمون RED→GREEN و سپس اصلاح مجاز. بهینه‌سازی عملکرد `catalog()` و `verified()` مسئله مستقلی است.

## وضعیت پروژه و چت
۸ فاز ثابت؛ پیشرفت رسمی ثبت‌شده ۸۵٪؛ **P6-5 PARTIAL**؛ گیت پایداری Windows باز. PR #34 Open/Draft/Unmerged؛ بدون Merge، ForcePush، main، EXE/Release یا آغاز P6-6/فاز ۷. این چت آزمون واقعی پنجره Qt را دو بخش کرد، چهار JUnit PASS خواند و شواهد ثبت کرد؛ **رفع خطا اعلام نمی‌شود**.
