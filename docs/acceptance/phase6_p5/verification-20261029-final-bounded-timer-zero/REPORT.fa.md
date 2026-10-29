# StructuralPro | فاز ۶، P6-5 | تصمیم نهایی دور محدود بررسی کرش ویندوز

**تاریخ:** ۲۰۲۶-۱۰-۲۹  
**حکم اجرایی:** دور تشخیصی محدود تکمیل شد: **۲ PASS مستقل Windows بدون Debugger با تایمر dump صفر**. اصلاح خودِ محصول ادعا نمی‌شود. **Native crash historical root cause OPEN؛ Windows stability gate OPEN؛ P6-5 PARTIAL.**

## مسئله‌ای که واقعاً ثابت شده
- [Run #40839501658](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40839501658): دو اجرای مستقل بدون CDB برای Oracle اصلی پنج‌طبقه، هر دو JUnit PASS؛ مجموع ۱۴ عملیات/۷۰ ردیف، آخرین `CASE_DONE`، SQLite `PRAGMA integrity_check=ok` و BOQ Oracle PASS.
- [Run #40845502382](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40845502382): اجرای بدون CDB، دو PASS برای سناریوی Lifecycle؛ اما یک تکرار همان سناریو زیر CDB با دومین فرصت `0xC0000005` و JUnit مفقود شکست خورد. CDB، `python312!Py_DumpTracebackThreads` و `python312!Py_AtExit` را در stack ثبت کرد؛ Checkpoint آخرِ این حادثه `REVIEW_CLICK_ENTER`، چرخه ۱، تعداد ۲۷ ردیف متعهد بود. **هم‌زمانی ثابت است، علیت ثابت نیست.**
- [Run #40853080441](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40853080441): کنترل A-C-C-A روی یک Runner با چهار پردازش مستقل زیر CDB. در A اول، تایمر faulthandler برابر **۴۵ ثانیه** بود؛ second-chance AV واقعی `0xC0000005` و `python312!Py_DumpTracebackThreads` رخ داد؛ آخرین Checkpoint `CONSTRUCT_ENTER` در چرخه ۱ پس از ۱۴ Commit. دو تکرار C با تایمر **صفر** هر دو JUnit PASS شدند؛ A آخر با تایمر ۴۵ نیز PASS شد. بنابراین **رابطه قطعی علت و معلولی بین تایمر و کرش اثبات نشده**، هرچند نقش آن یک فرضیه جدی و قابل کنترل در CI است.

## اقدام محدود این مأموریت
بدون تغییر فایل‌های app/core، Oracle و معیارهای داده، ابزار تشخیصی جدید `scripts/diagnostics/p6_native_timer_zero_decision.py` و Workflow مجزا `.github/workflows/phase6-p5-final-bounded-native-timer-zero.yml` ایجاد شد. هر اجرای واقعی:
- Python 3.12.10، PySide6 6.12.0، Windows Server 2022 و Qt native `windows`؛ بدون CDB، GDB و profiler.
- اجرای سناریوی **پنج چرخه باز و بسته شدن پنجره واقعی**، هر ۱۴ Commit، مجموع ۷۰ ردیف؛ SQLite واقعی، تست اصلی از داده‌های مصنوعی پنج‌طبقه بدون تغییر.
- `PYTHONFAULTHANDLER=1` و پلاگین faulthandler **فعال** ولی `faulthandler_timeout=0`. این تغییر فقط تایمر تولید trace هر ۴۵ ثانیه را حذف می‌کند، نه مشاهده خطاهای مرگبار را.
- حداکثر **دو** فرایند مستقل؛ متوقف‌شدن روی اولین شکست؛ زمان‌سنج سخت ۳۴۵ ثانیه برای هر کدام.
- ثبت فقط Checkpointهای ثابت عملیاتی و metadata بی‌خطر در `events.jsonl` و `last.json`؛ JUnit واقعی، شناسه خروج فرایند، اثر faulthandler و `PRAGMA integrity_check` روی SQLite بازشده به‌صورت فقط‌خواندنی؛ داده مهندسی، SQL خام، Dump و raw stdout آپلود نمی‌شوند.
- قبل از اجرا پنج blob محافظت‌شدهٔ محصول و Oracle با SHAهای مرجع مطابقت داده شدند.

**خطای ابزار در نخستین Run:** [#40865568526](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40865568526) RED بود، ولی Artifact نشان داد تست Child اول `ALL_DONE` را با ۷۰ Commit، JUnit معتبر و پروب تایمر صفر ثبت کرده است. خطای واقعی Runner بعد از پایان Child، `WinError 32` هنگام پاک‌کردن `projects.db` موقت ویندوز بود. این خطا **کرش Qt/محصول نیست**. با اصلاح صرفاً نحوه best-effort cleanup در پوشه موقت disposable Runner، شواهد JUnit حفظ و فرآیند مجدداً در یک اجرای محدود اجرا شد. فایل موقت قفل‌شده ممکن است تا پایان عمر Runner باقی بماند، اما به Artifact منتقل نمی‌شود.

## شاهد نهایی تصدیق‌شده
[GitHub Actions Run #40866225297](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40866225297) روی HEAD `2849718ad1fc772b263d6065d2849f0d72d33b98`: **SUCCESS**.

Artifact `p6-p5-final-no-debugger-timer-zero-checkpoints`، ID `12893383572`؛ ZIP SHA-256: `dff979a83c265b649825b182529322bcfd77f91d95603619568b68bcb5336f4a`. فایل ZIP دانلود و `summary.json`، هر دو JUnit، Probe و last/checkpoint بازخوانی شد.

| شاخص | تکرار ۱ | تکرار ۲ |
|---|---:|---:|
| مدت | ۱۰۹٫۴۵ ثانیه | ۱۱۰٫۹۷ ثانیه |
| Exit/Timeout | `0x00000000` / خیر | `0x00000000` / خیر |
| JUnit | ۱ PASS، صفر FAIL/ERROR/SKIP | ۱ PASS، صفر FAIL/ERROR/SKIP |
| آخرین Checkpoint | `ALL_DONE`، sequence ۹۶۷ | `ALL_DONE`، sequence ۹۶۷ |
| ردیف‌های Commitشده | ۷۰ | ۷۰ |
| Probe `faulthandler_timeout=0` و faulthandler فعال | تأیید شد | تأیید شد |
| SQLite `PRAGMA integrity_check` | `ok` | `ok` |
| BOQ / Final 70-row Oracle assertions | PASS | PASS |
| Native AV در Child بدون CDB | مشاهده نشد | مشاهده نشد |

**اعتبار شواهد:** `ALL_DONE` به معنی عبور کامل از چرخه‌های انتخاب، Review، Commit، Destroy و Reopen و Oracle اصلی همان سناریو است. آزمون اینجا **پروژه تجاری واقعی یا نقشه مهندسی واقعی** نیست؛ fixture پنج‌طبقه مصنوعی است. دو PASS تضمین فقدان کرش متناوب در محصول نیست.

## تصمیم فنی برای جلوگیری از دور باطل
۱. **دور آزمایش P6-5 در این مأموریت بسته می‌شود**؛ دو PASS معتبر با Watchdog Timer خاموش ثبت شد. تکرار نامحدود و profiler تکراری مجاز نیست.  
۲. پیکربندی `faulthandler_timeout=0` در این Workflow تشخیصی، **راهکار محدود کاهش تداخل ابزار CI** است، نه Patch رفع Native AV در محصول. `faulthandler` و timeout مستقل فرآیند همچنان برقرارند.  
۳. شواهد Crash تاریخی با کد `0xC0000005` و ماژول `python312` باقی‌اند. ریشه فنی و احتمال وقوع در کاربرد عادی محصول هنوز **اثبات یا رفع نشده**؛ مسیر بررسی هنگام وقوع مجدد با آخرین Checkpoint و CDB کالیبره موجود است.  
۴. هیچ تغییر حدسی در `Qt`، `SQLite`، `catalog()`، `verified()` و `deepcopy()` یا ادعای رفع SIGSEGV پذیرفته نمی‌شود. تست Windows و گیت نهایی فاز ۶ تا پذیرش واقعی نباید GREEN تجاری معرفی شوند.  
۵. مسیر بعدی کار در خود فاز ۶، **تکمیل اتصال عملی 2D↔3D↔Tree↔BOQ و سایر پذیرش‌های باقی‌مانده با ریسک Windows مستند** است. برای ادغام یا انتشار نهایی باید گیت پایداری ویندوز جداگانه تصمیم‌گیری و تأیید شود.

## وضعیت پروژه و چت
- نقشه‌راه ثابت: **۸ فاز**؛ پیشرفت رسمی کل محصول **۸۵٪**، نه درصد فاز ۶.
- **فاز ۶ P6-5 PARTIAL، Windows Stability OPEN**؛ P6-6 و فاز ۷ هنوز آغاز نشده‌اند.
- PR #34 **OPEN/DRAFT/UNMERGED**؛ هیچ Merge، تغییر main، ForcePush، ساخت EXE یا Release انجام نشده است.
- در این چت یک دور محدود تشخیص اجرا شد، WinError 32 صرفاً مربوط به پاک‌سازی پوشه آزمایشی تفکیک و رفع شد و **دو آزمون نهایی** با تایمر صفر، JUnit/SQLite/BOQ معتبر PASS شدند؛ باگ Native محصول همچنان به‌عنوان ریسک باز ثبت است.
