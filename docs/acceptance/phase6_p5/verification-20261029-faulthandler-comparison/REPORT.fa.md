# مقایسه کنترل‌شده Faulthandler زیر CDB — ۲۹ اکتبر ۲۰۲۶

**مقایسه محدود انجام شد؛ علت ریشه‌ای AV همچنان NOT PROVEN؛ رفع کرش OPEN؛ P6-5 PARTIAL.**

HEAD اولیه `9ecca92295ed3d2bea2774a3c0893ec92327e4d9`؛ Source آزموده `e11607d23b845e2f747e7561736fcd42365be05e`، Tree `699afa50a98112b6c3733e5e9d45960283937102`. HEAD نهایی،commitحاوی این گزارش است؛ app/core،داده‌ها و آزمون اصلی بدون تغییر مانده‌اند.

چهار فایل تشخیصی/CI تغییر کردند: `p6_native_cdb_trace.py` با انتخاب صریح حالت و حفظ پیش‌فرض enabled؛ `p6_faulthandler_probe.py` افزونه تشخیصی جدید برای کنترل وضعیت واقعی؛ `p6_lifecycle_checkpoint.py` برای assert وضعیت در هرcheckpoint؛ workflowجدید `phase6-faulthandler-comparison.yml` برای دوjobهم‌منبع ودوchildمستقل درهرحالت. کامپایلPythonمحلی انجام شد؛ نتیجهNativeازCIزیر است.

## قرارداد اجرا
[Run40848792075](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40848792075) هر دوjobcompleted/success. WindowsServer2022 build10.0.20348،Python3.12.10،PySide6/Qt6.12.0،SQLite3.49.1،pytest9.2.0،MicrosoftCDB. نسخه بسته‌ها وSQLiteدوenvironment.jsonبازدریافت‌شده برابرند. ماشین‌ها دوrunnerمستقل‌اند؛ برابریCPU/بارسیستم تضمین نشده است.

A: PYTHONFAULTHANDLER=1،افزونهpytestفعال،faulthandler_timeout=45؛پیکربندیقبلیحفظشد.
B: متغیرPYTHONFAULTHANDLERباenv.popحذفشد،نه مقدار0؛pytestبا`-p no:faulthandler`بدونگزینهtimeout45اجراشد. Probeداخلchildپیش/پسآزموندرهر۴اجراوضبطوassertشد: Aدارایenv/pluginوis_enabled=true،Bفاقدenv/pluginوis_enabled=falseوtimeout=null. درتمام۹۶۷checkpointهرchildنیزstateموردانتظارکنترلشد؛هیچstateمخالفیobservedنشد. فعال‌شدن بسیار کوتاه و خاموش‌شدن مجدد بین دو checkpoint را این ابزار نمی‌تواند مطلقاً رد کند.

## نتایج واقعی
|حالت/تکرار|Wallثانیه|CDBexit|JUnit|AV|آخرینcheckpoint|Commitتأییدشده|Timeout|
|---|---:|---:|---|---|---|---:|---|
|A۱|97.30|0|۱PASS،۰FAIL/ERROR/SKIP|مشاهده نشد|ALL_DONE،967،cycle4|70|false|
|A۲|97.24|0|۱PASS،۰FAIL/ERROR/SKIP|مشاهده نشد|ALL_DONE،967،cycle4|70|false|
|B۱|170.48|0|۱PASS،۰FAIL/ERROR/SKIP|مشاهده نشد|ALL_DONE،967،cycle4|70|false|
|B۲|163.66|0|۱PASS،۰FAIL/ERROR/SKIP|مشاهده نشد|ALL_DONE،967،cycle4|70|false|

هرچهارXMLاصلی مستقلاً parse وچهارprobe/summary/ژورنالترتیب‌دار باlastتطبیقشدند. NativePCmoduleوnearestsymbolدرهمهnullهستندچونAVتازهثبتنشد؛بههیچماژولیتقصیرنسبتداده‌نشد. OracleDecimalاصلی،BOQ۷۰ردیفیبا۷۰منبعیکتاوReopenبعدهرچرخهPASS؛integrityفیزیکیSQLiteدراینCIجداگانهاضافه/ثبتنشدهپسدرایندامنۀجداNOT VERIFIEDاست. هیچJUnitگمشدهیاساختگینداریم.

## شواهد پایدار
[Artifact A12886268087](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40848792075/artifacts/12886268087): ZIP SHA256 `8c2c7d426150e32447cb66643423791581954dae4787fc120f10cf00a14c63cd`.
[Artifact B12886283552](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40848792075/artifacts/12886283552): ZIP SHA256 `d782d983e517aef4974057de7efed3aa96ec0be392522aadd2dcd8c5c8d6f822`.
هردوZIPبازدریافتوهشبادigestسرویسبرابرشد. چهارJUnit،چهارprobe،دوsummary،دوenvironmentوچهارjournalفشردههمراهmanifestدرهمینپوشهپایدارند. dump،آدرسحافظه،اطلاعاتشخصیولاگخامCDBذخیرهنشد.

تغییرRunnerهمچنینworkflowقدیمی `40848792142` راخودکارفعالکرد؛اینRunجزءمقایسهA/Bنیست،درلحظهگزارشin_progressبودونتیجه‌اششمرده‌نشد. ابزاراتصالفرمانcancelنداشت؛workflowقدیم/گیتامنیتیبرایپنهان‌کردنآنحذفنشد. مقایسۀاصلیبههمان۲+۲childمحدودماند.

## تحلیل و قدم بعدی
درهر۴اجرایجدید،AVبازتولیدنشد. بنابراین شواهد نهتأثیرعلّیfaulthandlerراثابتومردودمی‌کندونهرفعکرشرانشانمی‌دهد. مدتBبیشتربودولیبه‌علتدوماشینوسربارCDB/fsyncوتعدادنمونهکم،معیاربهبود/افتقطعیعملکردنیست. شکستتاریخی40845502382باماژولPCpython312ونمادنزدیکPy_DumpTracebackThreadsهمچنانREDمعتبرمی‌ماند. محصولاصلاحنشدورگرسیونگستردهتکرارنشد.

**تنهاقدمبعدیپیشنهادی:** کنترل محدود هم‌منبع باfaulthandlerفعالولیtimerpytestبرابر0،برایجداکردناثرtimer45ثانیه‌ایازصرففعال‌بودنhandler؛بدونتغییرمحصولوبدونتفسیرPASSآنبه‌عنوانرفعAV. اینکنترلدرایننوبتاجرانشد.

## خلاصه وضعیت پروژه و این گفت‌وگو
مقایسهواقعیA/Bبا۴JUnitمعتبر،probeوcheckpointانجامشد؛علتریشه‌ایومانعپایداریWindowsبازاست. فاز۶/P6-5PARTIAL؛۸فازو۸۵٪رسمیثابت؛PR34Open/Draft/Unmerged. بدونMerge/ForcePush/main/Release/EXE/P6-6/فاز۷. گیت‌هایA2تجاریوE4/E6فاقدقراردادوUATمالکمستقل‌اند.
