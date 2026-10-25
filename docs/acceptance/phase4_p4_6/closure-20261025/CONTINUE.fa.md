> تصمیم جدید ۲۵ اکتبر: حالت B؛ چرخه دو دور پایان یافت. اولویت‌های۴–۶ PARTIAL؛ آزمایش تکراری آغاز نشود. مرجع نهایی: docs/acceptance/phase4_p4_6/decision-20261025/DECISION.fa.md. تنها اقدام لازم، انتساب عامل جایگزینی به PID/برنامه در محیط دارای قابلیت مجاز است.

# ادامه مستقل StructuralPro — فاز چهارم

محیط: ChatGPT Work + GitHub + Python/SQLite/PySide6 واقعی. سهمیه قابل مشاهده نیست؛ درصدی حدس نزن. از ابتدا نساز.

مخزن: Asanda021/StructuralPro-Recovery
PR: 25؛ Open/Draft/Unmerged
شاخه: feature/phase4-priorities4-6-site-operations-20261024
ابتدا HEAD و Tree واقعی را بخوان. تحویل قدیمی d7ab9fc جای شواهد جدید قرار نگیرد.

کد آزموده‌شده: a1538284bc9322450923ef6778b4ee542000732c
Tree: 1e9af37bdbc14af3d7dfb0291c8ae1272e3946ba
جامع نهایی: 7994 PASS، صفر FAIL/ERROR، پنج SKIP PowerShell؛ 467.666 ثانیه، exit0. پس از این اجرا محصول تغییر نکرده است؛ بی‌دلیل جامع را تکرار نکن.

اسناد اصلی در docs/acceptance/phase4_p4_6/closure-20261025:
REPORT.fa.md، current-state.json، causal-timeline.json، sqlite-headers.json، full-final-state.json، backup-receipt.json، restore-receipt.json و audit-recoverability.json.

شاهد واقعی تازه:
در اجرای مستقل مشاهده‌شده روی7ff1fab، خطای1032 / SQLITE_READONLY_DBMOVED پیش ازROLLBACK ثبت شد. FD16 بهdevice27/inode266155 با46194688بایت و برچسبdeleted اشاره داشت؛ همان مسیر بهdevice27/inode266211 با43864064بایت اشاره می‌کرد. تصویر مسیر نسخه273 و دارای حلقهoverflow صفحه16 وactive/tailنابرابر است؛ SHA آن b5b0e48414dee5205de34a0cd6403fd5d8f9cd819a9a8b87c3e2f7c73eb57e00 است.281COMMIT داده موفق و سپسBEGIN/INSERTخطادار/حفظ شواهد/ROLLBACK ثبت شد. Journal واقعیdelete؛ هنگام خطا Journal/WAL/SHM غایب بودند.

علت مستقیم readonly همین اجرا، جایگزینی فایل باز است. عامل جایگزینی و علت دقیق فساد تاریخی251/323 هنوزUNRESOLVED هستند. این نتیجه به گذشته تعمیم داده نشود. نمونه‌های قدیمی بدون تغییر حفظ شدند. Store وRecovery تغییر نکردند؛ guardهای فعلی نمونه273 را هم بدون تغییر فایل رد کردند.

لاگ در sqlite-runs-frozen/audited-workspace و log-index.json است. بایت FD حذف‌شده در اولین رخداد تطبیق‌یافته ذخیره نشد؛ هویت/اندازه/قفل وکپی مسیر پیش ازROLLBACK موجودند. ابزار sqlite_worker.py اکنون روی خطای بعدی بایت FD را باpread و رویدادهایinotify هم حفظ می‌کند. اجرای بعدیnotify موفق بود و عامل را روشن نکرد. PTRACE ممنوع است؛ دور زده نشود. موتور/GC/آستانه0.5 حدسی تغییر نکنند.

ارائه گزارش اصلاح شد: خلاصهExcel وضعیت نبود خلاصه عددی و تعداد واقعی دارد؛ درصد کوتاه با≈ ومقدار اصلی در ممیزی؛ هش کوتاه باارجاع به64نویسه کامل داخل سند؛ CSV دقیق.12مورد جدید،42هدفمند، پروب پایدار،64بازخوانی،32چاپ آفلاین و کنترل بازیابی توکن‌های45خروجی موفق‌اند. داشبوردPDF3،بستهPDF5،بستهWord6صفحه؛ نمودارExcel یک صفحه کامل. پیوست ممیزی پیشرفت طولانی است؛ Office واقعی تأیید نشده.

بکاپ معتبر جدید:
https://drive.google.com/file/d/1lsD8T4KweVj1CUO1vnwQAWMWnoD1k3-7/view?usp=drivesdk
SHA:30bffdbc590b7847f5f9a01cb50dca3ee37a9795d5480adc3ff343a084fe7e8b
اندازه:54681523بایت؛310فایلManifest.
Snapshot:0c32a890205f24fe654930fafe5eff4aec13f0a0
Tree:ee6527a80f84d3e2fd908ee22cf35f303b9c38b3
بازدریافت دقیق،clone/fsck،SQLite/FK/326Revision/270مدرک و165آزمون بازیابیPASS؛ منابع اولیه پنهان و مسیرها فقط از دانلود بازسازی شدند. نمونه‌های خراب فقط diagnostics هستند؛ scenario سالم منبعrestore است. نسخه‌های خام خراب در Git نیستند؛ از این آرشیو دریافت شوند. بکاپ قبلی14Y_0KLncL_8AdpqdkuLu1g84_7V1kIRK محفوظ است.

کار باز:
1. عامل جایگزینی فایل باز را با شاهد مجاز شناسایی کن یا محدودیت محیط را دقیق اثبات و ثبت کن. داده فعال QA درtmp و نسخه بسته و تأییدشده درworkspace منتشر شود؛ مسیر محصولWindows تغییر نکند.
2. در رخداد بعدی ابتدا FD/فایل/Journal/log پیش ازROLLBACK حفظ شوند. اگر نقص محصول اثبات شد، RED→GREEN و حداقل اصلاح؛ سپس آزمون‌های متأثر، جامع لازم و بکاپ تازه. موفقیتretry جای علت را نگیرد.
3. تصمیم پذیرش ریسک به‌جای مالک ثبت نشود. هر سه اولویت4–6 فعلاًPARTIAL هستند. Windows/Office واقعی، پروژه مهندسی واقعی و تأیید مالک مستقل‌اند.

سناریوی پنج‌طبقه/15فعالیت/18و20روز/سوابق12.5،45،75 وشاخص تاریخی100/92.5/75/-25 ثابت بماند. Fail-Closed،Decimal،BOQ،Baseline،CAS،Revision وprovenance حفظ شوند. دقیقاً8فاز ویک نسخه کاملWindows؛ فاز5آغاز نشود وStructuralBot مستقل بماند. بدون تأیید صریح مالک هیچMerge/Release/EXE/ForcePush/main/PR23/PR24/Actions دستی پرهزینه انجام نشود. پایان گفتگو گزارش واقعی، خلاصه هشت فاز وپرامپت ادامه باHEAD جدید ثبت شود.
