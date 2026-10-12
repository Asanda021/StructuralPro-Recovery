# تکمیل اجرایی بازیابی StructuralPro، ۱۲ اکتبر ۲۰۲۶

مخزن فعال Asanda021/StructuralPro-Recovery؛ main تغییر نکرد. مبنا PR #5 / 732d7c16104bf681a350b39e684d9db98da3881e. شاخه مستقل fix/recovery-test-policy-20261012. محیط Linux، Python 3.12.14 و pytest 9.1.1. از Checkout و venv معتبر قبلی استفاده شد؛ مخزن قدیمی دوباره clone نشد. دستور مأموریت از متن پیوست‌شده کاربر گرفته شد.

## نتایج واقعی
- بازتولید full قبل از اصلاح: 2102 passed / 55 failed / 7 skipped، exit 1.
- تاریخی مجزا: 130 passed / 0 failed / 0 skipped، exit 0؛ همان assertionها و negative mutations.
- هسته مهندسی هدفمند: 128 passed / 0 failed / 0 skipped، exit 0.
- رابط/هم‌زمانی جدید: پنج پردازش spawn، هر ۱۳ عملیات × پنج طبقه؛ ۶۵ اسمبلی، ۱۹۵ متره، ۱۳ BOQ فقط work. پس از close/reopen تک‌تک کمیت‌های work با مرجع مستقل هندسی بررسی شد؛ Source IDها یکتا و PRAGMA integrity_check=ok.
- نقص واقعی Audit: دو آزمون قبل از اصلاح failed (تعداد takeoff ذخیره‌شده از ۱ به ۰ می‌رسید)؛ با تازه‌خوانی و expected_digest اصلاح شد، تضاد هم‌زمان rollback و هشدار ایجاد می‌کند.
- فارسی‌سازی: دو آزمون قبل از اصلاح failed؛ نوع و هندسه ناقص شناخته‌شده به فارسی نمایش داده می‌شوند، کد engine همان column می‌ماند. وضعیت active/cancelled فقط هنگام export فارسی نمایش داده می‌شود؛ status داخلی و مقدار عددی تغییر نکردند.
- full پس از اصلاح Audit و سیاست، قبل از فارسی‌سازی: 2169 passed / 0 failed / 7 skipped؛ exit 0.
- full نهایی عادی پس از تمام اصلاحات: 2171 passed / 0 failed / 7 skipped؛ exit 0.
- UI واقعی Linux: دکمه Preview و Save، QMessageBox واقعی فارسی بدون mock، duplicate save، draft ناقص، close/reopen پروژه، audit event و RTL آزموده شدند. مقدار ستون با ورودی صریح 2×0.5×0.4×3=1.2 m3 است.
- چهار خروجی واقعی CSV/XLSX/DOCX/PDF برای ۱۲۰ ردیف صریح؛ مرجع مستقل sum(1..120)/10=726. XLSX مقدارها عددی و شناسه 0001 رشته است؛ DOCX table/paragraph RTL و متن فارسی بررسی شدند. PDF پنج صفحه دارد؛ هر پنج صفحه رندر و متن آنها استخراج شده، سربرگ جدول در تمام صفحات و کدهای اول/آخر کنترل شدند. نمایش glyph و جهت extraction متفاوت‌اند و Unicode NFKC برای بررسی متن منطقی استفاده شد.
- Windows gate واقعی: BLOCKED_NOT_WINDOWS، exit 2، missing_dependencies=[]؛ Linux/PDF/Qt به‌عنوان پذیرش Windows معرفی نشدند.

## رسیدگی به هر ۵۵ شکست
`FAILURE_55_RESOLUTION_20261012.json` فهرست دقیق و دسته‌بندی هر شکست را دارد. رفتار محصول به‌علت نبود مسیر Workflow شکست نخورده بود؛ این تست‌ها قرارداد امنیتی/انتشار/وابستگی/وجود فایل تاریخی را می‌خواندند. ۱۵ ماژول فقط مسیر آن قراردادها را به `tests.historical_contracts` تغییر می‌دهند؛ همان assertions روی فایل‌های واقعی قرنطینه‌شده در TemporaryDirectory خارج سورس اجرا می‌شوند. Fixture پس از پایان process پاک می‌شود. هیچ تست حذف یا skip جدید نشده است. افزایش PASS شامل ۵۵ آزمون قبلی و ۱۴ آزمون جدید است؛ ۷ skip همان محدودیت‌های IFC اختیاری (۲) و PowerShell موجود نیست (۵) هستند.

## سیاست فعلی و پوشش معادل/افزوده
`current_policy` نبود مسیر فعال Actions، نوع عادی فایل‌های قرنطینه، تعداد ۱۹۳، Symlink مستقیم و والد را بررسی می‌کند. مانیفست `recovery/workflow_sha256.json` با bytes همان فایل‌های بررسی‌شده PR #5 ساخته شده است؛ تغییر مجوز، محرک یا هر byte فایل اختلاف هش می‌دهد. مانیفست یک سند review محلی است، نه امضای cryptographic یا اثبات تنظیمات واقعی GitHub. آزمون‌های منفی permission/trigger/extra/symlink/parent link/active/missing manifest اضافه‌اند.

## اجرای دو حالت
```text
python scripts/run_quarantined_workflow_qa.py --mode current --json current.json --log current.log
python scripts/run_quarantined_workflow_qa.py --mode historical --json historical.json --log historical.log
```
current سیاست مخزن و مجموعه کامل معمولی را اجرا می‌کند. historical همان ۱۵ ماژول قرارداد را اجرا می‌کند؛ هر دو قبل از آزمون source policy را بررسی می‌کنند، هیچ YAML اجرا نمی‌کنند و منبع اصلی همیشه صفر Workflow فعال دارد.

## بررسی PR و Windows
`PR_READINESS_20261012_FA.md` شامل SHA، مبنا، تمام فایل‌های تغییرکرده، خطر و وضعیت هر پنج PR است. پشت‌سرهم بودن chain با GitHub compare تأیید شد. Snapshot انتهایی زنجیره در Worktree جدا تست شد؛ Merge انجام نشده است.
`WINDOWS_RECOVERY_ACCEPTANCE_20261012_FA.md` و `scripts/run_recovery_acceptance.ps1` بسته سورس آماده Windows هستند. Word/Excel واقعی Windows، پنجره روی Desktop واقعی، تأیید کامل فرم نازک‌کاری و تأیید بصری مالک هنوز BLOCKED_ENVIRONMENT/PENDING هستند.

## بکاپ و محدودیت‌ها
ZIP تازه شامل سورس، مانیفست SHA-256 و شواهد مستقل خارج از GitHub در محیط کاری تهیه می‌شود؛ بعد از استخراج تازه همه هش‌ها و آزمون‌های هدفمند بررسی می‌شوند. Git تاریخچه این محیط shallow است؛ تاریخچه تاریخی کامل بازسازی نشده. Bundle به‌عنوان full-history backup ادعا نمی‌شود.
برای آپلود Dropbox از مالک مسیر مقصد خواسته شد؛ بدون مسیر مشخص انتقال ادعا نمی‌شود. بسته و checksum محلی حفظ می‌شوند و یک مسیر دریافت GitHub جدا نیز می‌تواند ارائه شود. هیچ بکاپ قبلی حذف نمی‌شود.

## باقی‌مانده به‌ترتیب
1. اجرای بسته روی Windows واقعی و بازکردن PDF/DOCX/XLSX در Office هدف، بازبینی تمام تصاویر توسط مالک.
2. تأیید چندپردازشی و فرم نازک‌کاری روی Windows و ثبت لاگ/نسخه‌ها.
3. دریافت مسیر Dropbox و انتقال بکاپ مستقل؛ اعلام موفقیت فقط پس از نتیجه واقعی upload.
4. بررسی مالک درباره ترتیب ادغام زنجیره و PR جدید. هیچ Merge بدون تأیید جدید مالک.

هیچ Actions/Build/EXE/Installer/Release/Force Push/حذف شاخه/تغییر main انجام نشده است. موتور متره موازی یا مقدار مهندسی حدسی ساخته نشده است.
