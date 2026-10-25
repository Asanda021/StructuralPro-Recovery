# ادامه مستقل فاز چهارم — ۲۵ اکتبر ۲۰۲۶

مخزن Asanda021/StructuralPro-Recovery، PR25، شاخه feature/phase4-priorities4-6-site-operations-20261024. ابتدا HEAD و Tree واقعی GitHub را بخوان؛ Commitهای تازه را بررسی کن و کار قبلی را تکرار نکن. PR باید Open/Draft/Unmerged بماند.

نقطه کد آزموده‌شده: 58a160815eaa6fa34aaf05557ed2386ead72341c؛ Tree e3a12ea3ad1d8261a030f0763f475be39181b728. منطق محصول نسبت به c261a79 تغییر نکرد؛ دو Fixture قدیمی با قرارداد تاریخچه سازگار و کنترل‌ها تقویت شدند. جامع نهایی 7982 PASS، صفر FAIL/ERROR، پنج SKIP PowerShell، 457.589 ثانیه و exit0 است. بدون تغییر کد یا دلیل تازه این جامع را تکرار نکن.

مدارک اصلی در docs/acceptance/phase4_p4_6/work-20261025:
REPORT.fa.md، risk-register.fa.md، full-final-state.json، full-final.xml.gz، full-final.log، final-cad-measurements.json، readonly-failure-db.json، new-overflow-chain.json، scenario-audit.json، output-qa.fa.md، backup-receipt.json، restore-receipt.json و restored-tests.xml.

مانع باز واقعی: پروب workspace با readonly در INSERT شکست خورد و DB نسخه251 خراب شد؛ حلقه صفحه17، صفحه15 بدون استفاده، اختلاف57556بایت با Revision. SHA a7c784456188addb4aeac65e73c57bc538172926aa87e2c12aec2eba51cbd367. نمونه تاریخی323 نیز با SHA561550b8d0bb42fb5bb3ec002222894414d2740c19f66d2cbb815728945793f6 محفوظ است. علت هر دو UNRESOLVED. تشخیص startup/backup و بازیابی دستی موفق‌اند، اما رفع علت را ثابت نمی‌کنند. retryهای سالم و 652 مشاهده بدون اختلاف inode نباید جای شکست را بگیرند.

محیط Work: Python3.12.14، SQLite3.53.1، Qt6.12 offscreen، IfcOpenShell0.9، PyMuPDF2.0؛ installed.txt مرجع نسخه‌ها. محیط قبلی ممکن است پاک شود؛ موجودبودن venv را فرض نکن. requirements واقعی نصب شود؛ QTest واقعی اجرا شود. آستانه0.5، GC و Fail-Closed ثابت بمانند.

سناریوی تازه و صریحاً مصنوعی از همان کد مخزن موفق شد: پنج طبقه،15فعالیت،18/20روز،سوابق12.5/45/75 و شاخص تاریخ مبنا100/92.5/75/-25؛270مدرک هش‌دار،326Revision سالم. چهار فایل غایب قدیمی جعل نشدند؛ منشأ تازه مستقل است. 64خروجی جدید بازخوانی و32فایل Word/Excel آفلاین چاپ شدند. 15برگه خلاصه فقطسرستون، هش‌های بلند ودرصدهای پررقم محدودیت ارائه بازند.

بکاپ معتبر تازه Drive:
https://drive.google.com/file/d/14Y_0KLncL_8AdpqdkuLu1g84_7V1kIRK/view?usp=drivesdk
SHA6237e53d3906ceb26b50795271ccd555cf66896ce09a389654bb66602485b74b،42935572بایت؛Snapshotb1e2c4cf8876f57255ab9079850e8dd666c9d558،Treeefab85f787211b540f6c2c015f21da6cd1044588.254فایلManifest،clone/fsck،SQLite/FK/326Revision/270مدرک و135آزمون بازیابی PASS. اصلمنابع پنهان و مسیرها فقط از دانلود بازسازی شدند. بکاپ PARTIAL است. آرشیو اول با ID1dQOiKf56WuEBK9RdMyLCwr588Z5iPZmp نامعتبر و برچسب‌خورده است؛ هرگز restore نشود.

کار باقی‌مانده، فقط در همین دامنه:
1. علت تغییر صفحات/خطای readonly را با آزمایش کنترل‌شده تازه بررسی کن: مسیر tmp در برابر workspace، فرایند مستقل، commit/close/reopen، FD/inode، journal واقعی، کد extended خطای SQLite و مقایسه بایت فعال/Revision از اتصال تازه. PTRACE پیش‌تر ممنوع بود؛ دور زده نشود. همگام‌سازی یا کتابخانه را بدون شاهد علت معرفی نکن. فقط نقص بازتولیدشده را با RED→GREEN اصلاح کن.
2. محدودیت‌های واقعی ارائه را بدون دستکاری مقدار، تاریخچه، هش یا منشأ رفع کن؛ موتور گزارش موازی نساز. بعد از تغییر، خروجی‌های متأثر را دوباره رندر و بررسی کن.
3. اگر منطق اجرایی تغییر کرد، آزمون‌های متأثر و رگرسیون جامع لازم را با محافظ scripts/run_offline_tests.py اجرا و فوراً JUnit/HEAD/Tree را ثبت کن. پس از تغییر واقعی داده/کد، بکاپ تازه و بازدریافت/بازیابی لازم است؛ بکاپ معتبر فعلی بی‌دلیل تکرار نشود.
4. هر سه اولویت فعلاً PARTIAL. بدون رفع مانع بحرانی یا تصمیم مستند و مجاز پذیرش ریسک، COMPLETE نگو. Windows/Office واقعی، پذیرش مهندسی پروژه واقعی و تأیید مالک مستقل‌اند.

دقیقاً هشت فاز و یک نسخه کامل Windows. PR23/24/main و StructuralBot دست‌نخورده؛ فاز5 آغاز نشود. بدون تأیید صریح مالک هیچ Merge/Release/EXE/ForcePush/Actions دستی پرهزینه انجام نشود. پایان گفتگو گزارش واقعی، خلاصه هشت فاز و پرامپت ادامه با HEAD تازه بده.
