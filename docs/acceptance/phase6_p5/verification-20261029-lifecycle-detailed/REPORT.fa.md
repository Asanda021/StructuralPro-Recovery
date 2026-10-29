# چرخه عمر Native با checkpoint دقیق — ۲۹ اکتبر ۲۰۲۶

**حکم: PARTIAL؛ Windows Native stability همچنان RED؛ علت ریشه‌ای Access Violation اثبات نشده است.**

## منشأ و تغییرات
HEAD اولیه `a7a7e1933bacd424a033edf3549679625dfd2c30`؛ Source تشخیصی آزموده‌شده `7d6bc31dd146e4d88c273417b950cf34708827b6`؛ Tree `e2427f86a90fd0c1e63d22eb5487387400e00a0e`. HEAD نهایی، commit حاوی این گزارش است.
سه فایل تغییر کردند: `scripts/diagnostics/p6_native_isolation_oracles.py` فقط آزمون مستقل lifecycle موجود با markerهای دقیق‌تر؛ `scripts/diagnostics/p6_lifecycle_checkpoint.py` فقط allowlist رویدادها؛ `.github/workflows/phase6-windows-lifecycle-native-site.yml` نام/مسیر خروجی جدید با همان چهار child محدود. کد محصول و آزمون اصلی پنج‌طبقه دست‌نخورده‌اند؛ CI پنج blob قفل‌شده محصول/آزمون را کنترل کرد و PASS شد.

CHECKPOINT جدید: SELECT_ENTER/EXIT، REVIEW_CLICK_ENTER/EXIT، COMMIT_CLICK_ENTER/EXIT، EVENTS_ENTER/EXIT، CONSTRUCT_ENTER/EXIT و DEFERRED_ENTER/EXIT. Refresh و Store close و Reopen از قبل marker داشتند. شمار committed در cleanup اکنون آخرین شمار تأییدشده است، نه انتهای فرضی batch. پیام‌ها فقط stage/cycle/committed_rows/sequence/monotonic و دو پرچم ثابت عدم ذخیره داده/حافظه دارند. هیچ مقدار،SQL،شناسه عضو،آدرس حافظه یا dump افزوده نشده است. flush/fsync و atomic replace موجود حفظ شد.

## اجرای واقعی و شواهد
[Run40845502382](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40845502382) **completed/failure**؛ شکست، نتیجه واقعی CDB child1 است. Windows Server2022،Python3.12.10،Qt windows؛ نسخه‌های دقیق و اثرانگشت مجاز در environment.json است. فقط دو child عادی ودوchild CDB اجرا شدند. self-checkها و کامپایل ابزارهای تشخیصی در Windows موفق شدند.

|بازو|Wall ثانیه|Exit|JUnit|آخرین checkpoint|AV|Timeout|
|---|---:|---|---|---|---|---|
|عادی۱|85.08|0|۱PASS/۰FAIL/ERROR/SKIP|ALL_DONE،967،cycle4،۷۰ردیف|مشاهده نشد|false|
|عادی۲|80.06|0|۱PASS/۰FAIL/ERROR/SKIP|ALL_DONE،967،cycle4،۷۰ردیف|مشاهده نشد|false|
|CDB۱|52.19|debugger0؛ child CRASH|Missing|REVIEW_CLICK_ENTER،359،cycle1،۲۷ردیف|second-chance0xC0000005|false|
|CDB۲|111.23|debugger0؛JUnitمعتبر|۱PASS/۰FAIL/ERROR/SKIP|ALL_DONE،967،cycle4،۷۰ردیف|مشاهده نشد|false|

در CDB۱ exit0 متعلق به خود Debugger پس از دریافت استثنا وquit است و PASS نیست. `valid_test_pass=false`،`second_chance_marker=true` وJUnitمفقود است.

[Artifact12884543984](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40845502382/artifacts/12884543984) با ZIP SHA256 `8f474ec929b8c96afc698697a0ddb16ebd591dc3fef32402d11b08c39d08614f` بازدریافت و با digest سرویس تطبیق داده شد. چهار journal از نظر sequence،زمان یکنواخت نامتناقص و تطابق last.json بازخوانی شدند. سه JUnit واقعی با یک PASS در هرکدام بررسی شدند؛ برای childکرش‌کرده XML ساخته نشد. summaryها،نسخه محیط،journalهایgzip وJUnit در همین پوشه وManifest پایدارند.

## مرز واقعی کرش
در CDB۱ آخرین عملیات کامل، SELECT_EXIT باsequence358 درcycle1 وcommitted_rows27 است؛ سپس REVIEW_CLICK_ENTER باsequence359 صادر شد ولی REVIEW_CLICK_EXIT وجود ندارد. رویدادهای357/358 انتخاب سطر بعدی را کامل نشان می‌دهند. Commit قبلی درsequence353تا356 شامل CLICK وprocessEvents کامل شد و assert بعدی شمارBOQرا۲۷تأیید کرد. بنابراین کرش در بازه فراخوانی دکمه Review بعدی رخ داد؛ نه اثبات قطعی در تابع Review و نه اثبات علت فساد حافظه. ممکن است thread دیگر هنگام بلوکبودن callback یا event loop استثنا گرفته باشد.

Exception PC module=`python312` باlm a @rip تأیید شده؛ نزدیک‌ترین نماد=`python312!Py_DumpTracebackThreads`. نمادهای sanitized پشته شامل Py_AtExit،PyInterpreterState_Delete،ucrtbase thread_start وthread entryهایkernel32/ntdllهستند. این‌ها محل استثنا/نماد نزدیک را نشان می‌دهند، نه علت معیوب‌بودن Python،Qt،SQLite،faulthandler یاdeepcopy.

چرخه صفر در همان child،DeferredDelete وisValid=false وdestroyedدقیقاًیک‌بار،Store close وReopen را گذرانده است. این شاهدی مخالف نتیجه‌گیری ساده «حذف پنجره قبلی حتماً خراب بود» است؛ callback یاwrapper حذف‌شده نیز از این شواهد اثبات نشده‌اند. بار پردازشی verified/catalog همچنان می‌تواند مدت رخدادهای هم‌زمان را تغییر دهد ولی شواهدی از رابطه علی باAVنداریم. حافظه خام/آدرس‌ها استخراج یا منتشر نشدند.

در سه اجرایPASS،Oracleاصلی lifecycle جمعDecimal۷۰ردیف و۷۰sourceیکتا وReopenبعدهرچرخه را تأیید کرده است. درchildکرش‌کرده تا۲۷Commit وassert شمارBOQپیشرفت مشاهده شد؛ صحت نهایی وintegrityفیزیکی دیتابیس پس ازکرش **NOT VERIFIED** است، چون فایلSQLiteاینchildدرArtifactنیست. checkpointجای integrity_check نیست.

## Faulthandler و تصمیم
پیکربندی قبلی حفظ شد: PYTHONFAULTHANDLER=1 وpytest faulthandler_timeout=45 درRunnerعادی؛ CDBنیز پیکربندی خودRunnerرا حفظ کرد. مقایسه جدا باfaulthandlerغیرفعال **NOT EXECUTED**؛ هیچ نتیجه‌ای درباره مقصر یا بی‌تقصیربودن آن مجاز نیست. ثبتfsync واجرایCDBزمان‌بندی را تغییر می‌دهند؛ دوPASSعادی رفعAVنیستند.

**تنها قدم بعدی:** یک کنترل محدود وهم‌منبع lifecycle زیرCDB باغیرفعال‌سازی مستند هر دو PYTHONFAULTHANDLER وplugin faulthandler pytest و ثبت دقیق محیط/آخرینcheckpoint؛ باهمانOracleبدون تغییرمحصول. این مقایسه صرفاً اثر ابزار را می‌سنجد و حتیPASSآن رفعکرش محسوب نمی‌شود. آزمونRED→GREEN محصولی وبهینه‌سازی انجام نشد چون ریشه ثابت نشده است.

## خلاصه وضعیت پروژه و این گفت‌وگو
۸فاز،۸۵٪رسمی،فاز۶اولویت۵PARTIAL؛ PR34Open/Draft/Unmerged. این نوبت checkpointهای ریزتر وچهاراجرای واقعی به پایان رسیدند؛ سهPASS ویکNativeAVجدید،با مرزReviewپس‌از۲۷Commit وPCmodulepython312ثبت شد. faulthandler control وعلت ریشه‌ای بازند. main،PR33،Merge،ForcePush،Release،EXE،P6-6وفاز۷ تغییر نکردند. هیچGREENساختگی یااعلامرفعکرش انجام نشد.
