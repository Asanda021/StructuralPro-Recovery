# ادامه اجرایی G4 — ۳۰ اکتبر ۲۰۲۶

**G4 AUTOMATED SCOPE ACCEPTED / PHYSICAL OWNER UAT PENDING**، در محدوده آزمون‌های قابل‌اجرای زیر. تصمیم فاز: **PHASE 6 PARTIAL / NO-GO**. پذیرش سخت‌افزار و امضای مالک انجام نشده؛ CLOSED ثبت نمی‌شود.

## مبنا و تغییرات

HEAD واقعی آغاز مأموریت `97b7e8a7939e1bff47bf627d50c6d7a317126fb0` تأیید شد. [PR #34](https://github.com/Asanda021/StructuralPro-Recovery/pull/34) Open، Draft و Unmerged است؛ mergeable=false مانع ادامه آزمون شاخه نشد و هیچ Merge انجام نشد.

Commit اجرایی این ادامه: [`2ffd9b144613695c2093cce4575021835a6d738f`](https://github.com/Asanda021/StructuralPro-Recovery/commit/2ffd9b144613695c2093cce4575021835a6d738f). فقط دو فایل اضافه شد:

- `.github/workflows/phase6-g4-remaining-cloud.yml`: یک Runner Windows 2022، سقف۲۰دقیقه، وابستگی‌های واقعی، LibreOffice رایگان و حفظ Artifact حتی هنگام شکست.
- `scripts/diagnostics/p6_g4_cloud_remaining.py`: اجرای آزمون‌های اصلی بدون تغییر آن‌ها؛ سقف۴۲۰ثانیه pytest و۹۰ثانیه برای هر رندر، JUnit، زمان، خروج، مصرف نمونه‌برداری‌شده و رندر خروجی‌ها.

Commit شواهد پس از این اجرا فقط همین پوشه گزارش و `closure-decision-20261029/GATES.json` را تغییر می‌دهد؛ SHA نهایی آن در ارجاع Commit و نظر PR ثبت می‌شود (از خودارجاع SHA داخل همان Commit استفاده نشده). هیچ فایل `app/core/tests` تغییر نکرد. آزمون اصلی پنج‌طبقه نیز دست‌نخورده است.

`SOURCE_EQUIVALENCE.json` برابری درخت‌های app/core/tests را با رگرسیون `683e2ad428d62e4980daa702438060621c845150` اثبات می‌کند؛ فایل‌های Shell/Dock و آزمون مربوط با منبع Native سه مقیاس قبلی نیز یکسان‌اند. بنابراین تکرار رگرسیون جامع یا DPIهای پذیرفته‌شده لازم نبود.

## محیط و زمان‌های معتبر

اجرای۱۲۵٪: Windows Server 2022 Datacenter `10.0.20348`، Xeon Platinum8573C با۲هسته/۴پردازنده منطقی، Microsoft Hyper-V Video، درایور `10.0.20348.1`، رزولوشن مشاهده‌شده۱۰۲۴×۷۶۸. `SESSIONNAME=null` است؛ نوع Session تعاملی/کنسولی از این مقدار اثبات نمی‌شود. این محیط GPU فیزیکی یا دستگاه مالک نیست. `QT_SCALE_FACTOR` مقیاس منطقی Qt است؛ DPI سیستم‌عامل/مانیتور واقعاً تغییر نکرده است.

اجرای تکمیلی: Windows-2022Server-10.0.20348، Python3.12.10، PySide6/Qt6.12.0، SQLite3.49.1، ifcopenshell0.9.0.post1، PyMuPDF2.0، openpyxl3.1.5، python-docx1.2.0، pytest9.2.0 و psutil7.2.2. LibreOffice26.2.6 با بسته choco واقعی نصب شد؛ دانلود و تطبیق Hash نصب در Log CI موجود است. نسخه‌های دقیق در `versions.json` حفظ‌اند.

زمان‌ها در فایل‌های خام UTC هستند. زمان فرایند pytest جدید: `08:36:30.915606` تا `08:36:54.117719 UTC` روز۳۰اکتبر، برابر۱۲:۰۶:۳۰ تا۱۲:۰۶:۵۴ تهران؛ مدت۲۳٫۲۰۳ثانیه. زمان خود Suite در JUnit جداست. زمان شروع/پایان فرایند۱۲۵٪ مستقل اندازه‌گیری نشده؛ timestamp و مدت JUnit معتبرند و از آن زمان فرایند اختراع نشده است.

## اجراهای واقعی و Artifact

| دامنه | Workflow / SHA | JUnit PASS/FAIL/ERROR/SKIP | مدت Suite | Artifact |
|---|---|---|---:|---|
| Native Qt۱۰۰٪، قبلی و بازبینی‌شده | [40933689980](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980)، `e012f0ac` | 11/0/0/0 |16.782s|[12924191585](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980/artifacts/12924191585)|
| Native Qt۱۲۵٪، بازدریافت‌شده | [41025947103](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41025947103)، `97b7e8a7` |11/0/0/0|16.038s|[12964320206](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41025947103/artifacts/12964320206)|
| Native Qt۱۵۰٪، قبلی و بازبینی‌شده |40933689980، `e012f0ac`|11/0/0/0|16.542s|[12923133912](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980/artifacts/12923133912)|
| Native Qt۲۰۰٪، قبلی و بازبینی‌شده |40933689980، `e012f0ac`|11/0/0/0|18.008s|[12924785017](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980/artifacts/12924785017)|
| گردش/خروجی/Worker/بازیابی تکمیلی |[41027220769](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41027220769)، `2ffd9b14`|43/0/0/0|21.79s در خلاصه pytest|[12963918207](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41027220769/artifacts/12963918207)|

برای همه ردیف‌ها Job موفق و JUnit اصلی معتبر است؛ نتیجه از رنگ سبز Job به‌تنهایی استنتاج نشده. خروج pytest تکمیلی۰، Timeout=false و هیچ شکست Native در این اجرا مشاهده نشد. CDB در این مأموریت تکرار نشده؛ شواهد تاریخی G1 حفظ است و رفع علت کرش ادعا نمی‌شود. مقیاس‌ها آزمایش آماری مستقلِ علت Native نیستند. تعداد۱۱ در چهار مقیاس با۴۳تست جدید هم‌پوشانی دامنه دارد؛ آن‌ها به آمار تست یکتای جامع اضافه نشده‌اند.

SHA256 آرشیو جدید: `22241408c0a5c1bd8eda7754acb5814ee04b03e6e5873abe94c835272464edf6`؛ آرشیو۱۲۵٪: `8090de6afb3203c99e01a732e7cd1fae88f47f83d4c059d31c268d9944178ffa`. هر دو پس از دانلود با digest GitHub برابر بودند. JUnit هر چهار DPI، JSON محیط، خروج اصلی و نسخه‌ها اینجا پایدارند. آرشیو `original-g4-window-export-evidence.tar.gz` شامل شواهد اصلی منتخب، فایل‌های خروجی و تصاویر است؛ شامل Dump یا CDB خام نیست. Hash فایل‌ها در `EVIDENCE_FILES.json` است. `test-temp/..._current` نام تکراری pytest است؛ نمونه `_0` فقط یک‌بار در بایگانی پذیرفته شده است.

## ماتریس G4 و مرز پذیرش

| مورد | وضعیت | شاهد و حدود |
|---|---|---|
| فارسی/RTL، Glyph، تم، Ribbon و۲۳Tab، باز/بسته‌کردن Ribbon، ذخیره تنظیمات |PASS_REAL_WINDOWS_AUTOMATED|۱۱تست در هر چهار مقیاس؛ `windows` برای فرایند اصلی و فرزند. تصویر۱۲۵و۲۰۰ خوانده شد؛ عدم کمبود Glyph با assert. این ادعای بررسی دستی همه صفحات نیست.|
| Dock واقعی، شناورشدن و بازیابی چینش؛ پاک‌شدن انتخاب/BOQ قبلی پس از تغییر پروژه یا Revision |PASS_REAL_WINDOWS_AUTOMATED|آزمون E5 در چهار مقیاس، پروژه و BOQ بدون تغییر ناخواسته.|
| گردش پروژه و هشدار داده ذخیره‌نشده |PASS_REAL_WINDOWS_AUTOMATED|۴۳تست جدید: کلیک واقعی Qt، No داده را حفظ و Yes خروج را مجاز می‌کند؛ ایجاد، ذخیره، بستن و بازگشایی SQLite.|
| IFC، طبقه/نوع/صفحه، بارگذاری QProcess و Worker، تعویض بسته و نگه‌داشت SHA/Revision |PASS_REAL_WINDOWS_AUTOMATED|آزمون integrated_batch_switch اصلی؛ IFC4 fixture مصنوعی صریح برای کنترل اجرا. مدل‌های مستقل G2 در پذیرش قبلی جدا هستند؛ این fixture جایگزین آن‌ها نیست.|
| 2D↔3D↔Tree↔BOQ |PASS_REAL_WINDOWS_AUTOMATED|انتخاب واقعی Qt روی ستون fixture دارای سابقه بازبینی موجود،۳ردیف BOQ و کنترل پاک‌سازی/Revision؛ هیچ مجوز جدید یا مقدار از Mesh ساخته نشد.|
| لغو/نتیجه دیررس Worker و تغییر فایل منبع |PASS_REAL_WINDOWS_AUTOMATED|background_loader،member_batches و تعویض صحنه؛ عدم پذیرش هندسه نیمه‌تمام/منبع تغییرکرده و حفظ Session. بخشی از تأخیر Worker عمداً در آزمون تزریق می‌شود؛ مدل سخت‌افزاری نیست.|
| PDF و کالیبراسیون |PASS_REAL_WINDOWS_AUTOMATED|vector evidence و رد مقیاس صفر در۴۳تست؛ مرور/Zoom/Pan/کلیک دو نقطه PDF در Suite جامع قبلی همان درخت کد. PDFهای آزمون تولیدشده‌اند، نقشه کارگاه مستقل تازه پذیرفته نشده است.|
| DWG Native از مبدل واقعی |BLOCKED_ENVIRONMENT|در این اجرا `STRUCTURALPRO_DWG_CONVERTER=null` و منبع DWG مجاز به همراه مبدل تأییدشده وارد نشده است؛ تست mock یا DXF به‌جای DWG پذیرفته نشد. این پذیرش DWG واقعی نیست و گیت تازه‌ای برای فاز۶ ایجاد نمی‌کند.|
| XLSX/DOCX/CSV بازخوانی و PDF رندر |PASS_REAL_WINDOWS_AUTOMATED|توضیح تفصیلی زیر؛ فقط خروجی‌های موجود، بدون شروع قابلیت فاز۷.|
| SQLite هم‌زمانی، بازگشایی، خطا، Backup/Restore |PASS_REAL_WINDOWS_AUTOMATED|concurrent_takeoff، Windows lock واقعی خطای۳۲ و حفظ Revision/Decimal؛ backup recovery و PRAGMA integrity_check=ok.|
| حافظه/CPU و عدم توقف در سناریوی محدود |PASS_REAL_WINDOWS_AUTOMATED|pytest۲۳٫۲۰۳ثانیه؛ اوج RSS نمونه‌برداری‌شده درخت فرایند۴۰۸۱۹۰۹۷۶بایت (~۳۸۹٫۳MiB)، CPU نمونه‌ای۱۱٫۶۲۵ثانیه؛ این soak طولانی، اثبات نبود leak یا Benchmark سخت‌افزار مالک نیست.|
| پنجره‌های متعدد/Native lifecycle طولانی‌تر |PASS_REAL_WINDOWS_AUTOMATED|شواهد محدود۹اجرای G1 قبلی حفظ شد؛ زنجیره تازه Faulthandler ساخته نشد.|
| GPU فیزیکی، چندمانیتور، DPI واقعی، unplug/replug وSleep/Resume |NOT_TESTED_PHYSICAL_HARDWARE|نمایشگر مجازی Hyper-V جانشین سخت‌افزار مالک نیست.|
| امضای مالک و قابلیت استفاده روی دستگاه واقعی |REQUIRES_OWNER_APPROVAL|انجام نشده؛ چک‌لیست کوتاه `OWNER_UAT.fa.md`.|
| Microsoft Office دسکتاپ و چاپ فیزیکی |BLOCKED_ENVIRONMENT|در این Runner اجرا نشده؛ در دامنه قبلی فاز۸ باقی است، شرط تازه بسته‌شدن فاز۶ نیست.|

هیچ FAIL_REPRODUCED جدیدی در اجرای نهایی ثبت نشد و اصلاح محصول لازم نشد؛ لذا RED→GREEN محصول در این ادامه موضوعیت ندارد. شکست‌ها و REDهای تاریخی حذف نشده‌اند. یک FutureWarning مربوط به نام قدیمی import `fitz` در Log۴۳تست هست؛ شکست یا Skip نیست.

## صحت و ظاهر خروجی‌ها

`recovery_ui_export_probe.py` اصلی از UI واقعی یک ردیف با مقدار۱٫۲ را ذخیره و با بازگشایی تطبیق داد؛ ثبت دوباره مهار شد و ورودی ناقص در BOQ ثبت نشد. خروجی طولانی، داده آزمون **مصنوعی و صریح** با۱۲۰ردیف و جمع مستقل `sum(1..120)/10=726` است؛ پروژه حقیقی تأییدشده مالک معرفی نشده است.

- CSV با utf-8-sig بازخوانی شد؛ صفرهای ابتدایی و متن فارسی حفظ شدند. قرارداد جداگانه تزریق Formula را مهار و رشته Decimal بلند را حفظ می‌کند.
- XLSX با openpyxl باز شد؛۱۲۰ردیف، واحدm2، جمع۷۲۶ و RTL دو Sheet کنترل شد. وجود فرمول دلخواه از داده آزمایشی حدس زده نشد؛ تست‌های manual گزارش دقت داده موجود را کنترل کردند.
- DOCX واقعی با ZIP/XML باز شد؛ متن، کد، `bidiVisual/bidi` و وضعیت فارسی کنترل شد.
- PDF اصلی۶صفحه، هر صفحه متن غیرخالی و عنوان/وضعیت فارسی و کد آغاز/پایان داشت و هر شش صفحه PNG واقعی تولید شد.
- LibreOffice واقعی DOCX را۹صفحه و XLSX را۷صفحه PDF کرد؛ خروج هر دو۰، Timeout=false، مدت۳٫۲۹۷و۱٫۰۴۷ثانیه. پس از دانلود، **تمام۱۲۰کد0001..0120 و جمع726.0 در متن هر دو PDF رندرشده** مستقل بررسی شد (`RENDER_READBACK_VERIFIED.json`). تصویر صفحه اول و آخر هر دو خوانده شد؛ متن فارسی و جدول نمونه خواناست. همه صفحات به‌صورت دستی تأیید نشده‌اند؛ رفتار ویرایش/ذخیره مجدد در Word/Excel مایکروسافت و چاپ فیزیکی ادعا نمی‌شود.

## رگرسیون و Gateها

[رگرسیون40949336798](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40949336798)، SHA `683e2ad428d62e4980daa702438060621c845150`: پنج Job موفق،۷۱۷ماژول،۸۴۶۳case یکتا در هر OS؛ Linux۸۴۵۸PASS/۵SKIP و Windows۸۴۵۶PASS/۷SKIP؛ صفرFAIL/ERROR/Timeout. سهShard بدون فقدان/تکرار/مورد اضافه طبق union معتبر؛ Hash آرشیو union بازدریافت‌شده `3d2f99959aa5dbfe76d2babc20cab23bfd2222aab1b42b29ca00c89938bc57b5` است. JSONهای inspected و union در این پوشه‌اند. SKIPها محیطی‌اند: Windows-only درLinux و oracle متن پیچیده/POSIX rename/identity/hardlink درWindows؛ در PASS محاسبه نشدند.۱۵ماژول Historical/Release Contract بیرون شمارش فعال‌اند؛ پذیرش مستقل قبلی۱۳۰PASS در هرOS به آمار۸۴۶۳ اضافه نمی‌شود و این ادامه آن‌ها را دوباره اجرا نکرد.

|Gate|وضعیت نهایی|
|---|---|
|G1|پذیرش خودکار سناریوی محدود Native حفظ؛ علت ریشه‌ای تاریخی قطعی نیست.|
|G2|پذیرش خودکار نمایش منابع مستند در حدود مصوب حفظ؛ IFC2X3 مرجع/terrain مجوز QTO یا مهندسی بازسازی نیست.|
|G3|بدون قرارداد پذیرش مستقل مصوب، مانع ساختگی اضافه نشد.|
|G4|دامنه خودکار قابل‌اجرای این ماتریس پذیرفته؛ موارد فیزیکی و امضای مالک باز.|
|G5|فقط یک نسخه جامع unified Windows؛ هیچ EXE/Installer/Release ساخته نشد. GGUF Placeholder عملیاتی نیست و مجوز تجاری AI غیرتجاری شرط تازه‌ای نیست.|

## خلاصه وضعیت پروژه و این چت

|فاز مصوب|وضعیت محفوظ|
|---|---|
|۱ مهندسی و متره|دامنه فنی پذیرفته‌شده پیشین حفظ؛ پذیرش تازه اعلام نشد.|
|۲ نقشه و BIM|دامنه فنی قبلی و محدودیت منبع/مبدل واقعی حفظ.|
|۳ BOQ و مالی|دامنه قبلی حفظ؛ منطق مالی تغییر نکرد.|
|۴ مدیریت پروژه|تکمیل فنی پیشین حفظ؛ ریسک و پذیرش فیزیکی مستقل است.|
|۵ داده/امنیت|دامنه قبلی حفظ؛ مدل واقعی AI از Placeholder جداست.|
|۶ رابط/نمایش زنده|PARTIAL / NO-GO؛ دامنه خودکار G4 پذیرفته، UAT فیزیکی/امضای مالک باز.|
|۷ گزارش مهندسی|شروع نشده؛ آزمون خروجی موجود مجوز آغاز فاز۷ نیست.|
|۸ پذیرش نهایی|شروع نشده؛ ساخت، انتشار و امضای نهایی مستقل است.|

دقیقاً۸فاز و۸۵٪رسمی حفظ شد. در این ادامه شواهد۱۲۵٪ و سه مقیاس قبلی بازبینی،۴۳آزمون Native تکمیلی و رندر واقعیLibreOffice انجام، اصل شواهد منتخب پایدار و GATES به تفکیک خودکار/فیزیکی به‌روز شد. PR باز/Draft/Unmerged است؛ نسخه نهایی Windows از نظر سیاست واحد است، آماده انتشار اعلام نمی‌شود. Merge، main، Force Push، EXE/Release و فاز۷ انجام نشد.

**تنها قدم بعدی:** اجرای چک‌لیست کوتاه UAT فیزیکی و ثبت تصمیم مالک، هنگامی که دستگاه واقعی Windows در دسترس باشد؛ تا آن زمان وضعیت معلق حفظ شود.
