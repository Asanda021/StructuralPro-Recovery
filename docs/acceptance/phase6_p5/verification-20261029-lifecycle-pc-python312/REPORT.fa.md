# StructuralPro | P6-5 | شناسایی ماژول Exception PC در کرش واقعی چرخه عمر Qt

**تاریخ بررسی:** ۲۹ اکتبر ۲۰۲۶  
**حکم:** آزمایش تشخیصی در دامنه مشخص COMPLETE؛ **گیت Windows Native RED، Access Violation با کد 0xC0000005 زیر CDB بازتولید شد**. نام ماژول محل Exception PC **python312** تأیید شد؛ **علت ریشه‌ای Native اثبات نشده**. P6-5 همچنان PARTIAL است.

## منشأ و قرارداد اجرا
- PR #34 در شاخه feature/phase6-p5-workspace-e3-e6-20261027؛ کد محصول و آزمون پنج‌طبقه اصلی تغییری نکرده‌اند.
- Run قبلی #40841278108 خطای 0xC0000005 را هنگام Refresh جدول ثبت کرد؛ JUnit نداشت و نام DLL مشخص نبود.
- در ادامه فقط سه نوع تغییر تشخیصی انجام شد: فایل جدید scripts/diagnostics/p6_lifecycle_checkpoint.py با ژورنال JSONL و last.json دارای flush/fsync و atomic replace؛ نشانگرهای اختیاری در آزمون مستقل چرخه عمر پنجره؛ اتصال بازوی dialog_lifecycle به runner عادی و ابزار Microsoft CDB کالیبره‌شده.
- در هر تکرار، Checkpoint جداگانه ذخیره می‌شود. فقط sequence، نوع مرحله، شماره چرخه و تعداد ردیف قطعی ثبت شده است؛ **هیچ نام عضو، قیمت، مقدار متره، SQL، حافظه، متغیر، آدرس رجیستر، مسیر شخصی یا Dump منتشر نشده**.
- Source run: `234eb64a46420367201ef8b5d5b8f6c8682654c5`. CI SHA فایل‌های app/manual_takeoff.py، app/manual_formula_controls.py، core/takeoff/manual_formula_register.py، core/projects/store.py و tests/test_manual_formula_fivefloor_closure.py را با Blobهای قفل‌شده تطبیق داد و PASS شد.

## اجرای واقعی Windows
[GitHub Actions #40843013644](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40843013644)، نتیجه **completed/failure** به دلیل شکست حقیقی یکی از چهار اجرای child، نه صرفاً خطای گزارش.

[Artifact #12883324289](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40843013644/artifacts/12883324289): p6-lifecycle-native-checkpoints-cdb-without-dumps؛ ZIP SHA256 **cbb521693ec21ec86b35bcf521bcb5bd3e8d4a323ae5a5061a6d6fb9b323fd89**. ZIP بازدریافت و Summary، XMLهای واقعی، دو نوع ژورنال و اثرانگشت محیط آن مستقیماً خوانده شدند.

| بازو | Wall | نتیجه اجرا | JUnit | آخرین Checkpoint |
|---|---:|---|---|---|
| بدون Debugger، تکرار ۱ | **120.11s** | exit 0، PASS | ۱ PASS، ۰ FAIL/ERROR/SKIP | ALL_DONE، sequence 67، چرخه پنجم و ۷۰ ردیف |
| بدون Debugger، تکرار ۲ | **130.11s** | exit 0، PASS | ۱ PASS، ۰ FAIL/ERROR/SKIP | ALL_DONE، sequence 67، چرخه پنجم و ۷۰ ردیف |
| **CDB، تکرار ۱** | **50.41s** | **second-chance 0xC0000005، CRASH** | **فایل ندارد** | **DIALOG_READY، sequence 16، cycle=1، committed=14** |
| CDB، تکرار ۲ | **210.95s** | CDB exit 0، PASS محدود | ۱ PASS، ۰ FAIL/ERROR/SKIP | ALL_DONE، sequence 67، چرخه پنجم و ۷۰ ردیف |

**نکته ارزیابی:** `debugger_exit_code=0` در اجرای CDB شماره ۱ به معنی سلامت تست نیست: CDB پس از گرفتن استثنا با فرمان quit خارج شد. `second_chance_marker=true`، کد `0xC0000005`، **نبود JUnit** و `valid_test_pass=false` آن اجرا را قطعی **RED** می‌کند. اجرای CDB دوم JUnit PASS معتبر دارد. هیچ TimeOut اجرایی گزارش نشده است.

## یافته Native جدید و حدود آن
- **Exception PC module:** `python312` از `lm a @rip`، با `native_pc_module_proven_by_lm_address=true` و کد استثنا `0xC0000005`.
- **Nearest symbol:** `python312!Py_DumpTracebackThreads` از `ln @rip`، **نزدیک‌ترین نماد قابل بازیابی**، نه اثبات قطعی تابع سازنده نقص حافظه.
- نمادهای قابل بازیابی در پشته Native: `python312!Py_DumpTracebackThreads`، `python312!Py_AtExit`، `python312!PyInterpreterState_Delete`، `ucrtbase!thread_start<unsigned`، `kernel32!BaseThreadInitThunk`، `ntdll!RtlUserThreadStart`.
- این داده‌ها **محل وقوع استثنا در python312.dll را تأیید می‌کنند** و سرنخی درباره traceback/چرخه پایان عمر مفسر ارائه می‌دهند، اما **ثابت نمی‌کنند Python ذاتاً معیوب است، شیء Qt باعث فساد حافظه شده، یا crash از Refresh/SQLite ناشی شده است**.
- در اجرای خطادار، همه گام‌های چرخه صفر تا `REOPEN_EXIT` به ترتیب کامل شدند: ۱۴ Commit، Refresh، تخریب Native dialog، Store close و SQLite reopen همگی Checkpoint خروج دارند. سپس `DIALOG_ENTER` و `DIALOG_READY` برای cycle=1 ثبت شدند. بنابراین شکست **بعد از آماده‌شدن دومین Dialog و قبل از تکمیل batch دوم** مشاهده شد. در این دامنه، آخرین نشانگر به معنای وجود stack دقیق Python در نقطه خطا نیست.
- در Run تاریخی قبلی #40841278108 آخرین Python frame هنگام Refresh/JSON بود؛ **این دو مرز متفاوت**، و یک ریشه مشترک برایشان هنوز اثبات نشده است.

## محیط مشترک واقعی
Windows Server 2022 build `10.0.20348`، Python `3.12.10` (64-bit)، PySide6/Qt `6.12.0`، SQLite `3.49.1`، pytest `9.2.0`. SHA256 allowlist همان ZIP برای `python312.dll`: `9a0e3435aaa680d868150f87ab3e388ad2eebc22f87e036155c7b4eda8cd2120`. این صرفاً اثرانگشت نسخه فعلی است، نه دلیل مقصر بودن فایل.

## تصمیم و ادامه همان فاز
۱. **مسیر واقعی کرش Native اکنون به ماژول PC مشخص python312.dll محدود شده** ولی منشأ فساد حافظه، trigger اولیه و ارتباط آن با Qt/PySide6 یا faulthandler هنوز باز است. 
۲. قدم بعدی فقط **تحلیل دقیق مرحله درون چرخه دوم** (قبل/بعد انتخاب و Review/Commit، با Checkpoint کم‌حجم) و کنترل تأثیر faulthandler/CDB و ترتیب نابودی QObject بر stack نهایی است؛ باید با Run محدود و معیار تکرارپذیری انجام شود. بدون شاهد RED→GREEN کد محصول تغییر داده نشود.
۳. بهینه‌سازی `catalog()` / `verified()` برای CPU موضوع مجزاست و **به‌عنوان درمان Native AV گزارش نمی‌شود**.
۴. CDB فقط PC module و نمادهای sanitized را منتشر کرد. raw debugger log، dump، آدرس حافظه و متغیرهای حساس ذخیره نشد.

## خلاصه وضعیت پروژه و این گفت‌وگو
نقشه‌راه دقیقاً **۸ فاز**، پیشرفت رسمی **۸۵٪** بدون افزایش؛ **فاز ۶، P6-5 PARTIAL**. Windows Native stability **RED**، چون CDB Run اول شکست واقعی داشت. PR #34 **Open/Draft/Unmerged**، بدون Merge، ForcePush، تغییر main، EXE/Release یا شروع P6-6 و فاز ۷. در این گفت‌وگو سنجش نقطه توقف چرخه عمر پیاده شد؛ دو PASS عادی، یک PASS زیر CDB و یک Native AV با **ماژول Exception PC شناسایی‌شده** ثبت شدند؛ رفع قطعی ادعا نمی‌شود.
