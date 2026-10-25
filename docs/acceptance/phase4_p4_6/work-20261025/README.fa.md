# پذیرش اجرایی Work — ۲۵ اکتبر ۲۰۲۶

کد مرجع c261a79fc4e8e54f085858b095161999bb308069، Tree 7c13c4a3ffd815de7dac6a721c8c856004ea78c7. PR25 Draft/Open/Unmerged؛ اولویت‌های۴،۵،۶ PARTIAL.

محیط مستقل Python3.12.14/SQLite3.53.1/Linux، نصب واقعی requirements و IfcOpenShell؛ نسخه‌ها در environment.json و installed.txt. QApplication/QTest واقعی offscreen موفق. نسخه‌های جدید از الزامات باز مخزن نصب شدند؛ با اجرای قدیم یکسان فرض نشوند.

نمونه خراب تاریخی فقط‌خواندنی بررسی شد؛ SHA ثابت561550b8d0bb42fb5bb3ec002222894414d2740c19f66d2cbb815728945793f6، integrity دارای حلقه صفحه۱۵. startup و backup جدید هر دو آن را رد کردند؛ هیچ بکاپ خروجی نماند. علت تاریخی UNRESOLVED.

اجرای هدفمند اولیه:26PASS/1FAIL/0ERROR/0SKIP در50.62ثانیه. آزمون اصلی tests/test_phase4_site_acceptance.py موفق، اما پروب دوم پایدار در مسیر workspace هنگام INSERT نسخه جدید با SQLite OperationalError: attempt to write a readonly database متوقف شد. این خطا هنوز به محصول یا محیط نسبت داده نشده؛ فایل شکست حفظ است. شواهد اصلی targeted.log/xml/exit. نتیجه retry جای این شکست را نمی‌گیرد.

رگرسیون جامع درحال اجراست؛ خروجی میانی PASS نهایی نیست. ناظر اولیه psutil به دلیل اختلاف PID قابل‌مشاهده فرایند فرزند و /proc شکست خورد؛ ناظر خارجی جداگانه آغاز شد. آزمون‌ها،آستانه0.5 وGC تغییر نکرده‌اند.

## نتیجه جامع کامل و مانع تازه
جامع c261a79:7980PASS/2FAIL/0ERROR/5SKIP از7987testcase،447.062ثانیهJUnit،exit1. JUnit کامل درfull.xml.gz و هش درfull-state.json. stdout خام در36٪ متوقف شده؛ بازسازی یا نتیجه‌سازی نشده است. CAD10k/50k/100k وIFC اصلیPASS، آستانه0.5 ثابت.
دوFAIL: test_reopen_multiple_amendments_then_save_draft_preserves_boq وtest_invalid_registry_and_corrupt_project_are_rejected_without_write. هر دوFixture فقطprojects.payload راباSQL تغییر می‌دهند؛ محافظ جدید مغایرت با آخرینRevision را به‌درستی رویstartup رد کرده است. هیچ محافظی برای سبزشدن تضعیف نشود.

**خرابی جدید واقعی:** فایل اجرایreadonly،37175296بایت،SHAa7c784456188addb4aeac65e73c57bc538172926aa87e2c12aec2eba51cbd367؛ نسخه251؛integrity ارجاع تکراری صفحه17/صفحه15بدون استفاده؛active باrevision نابرابر. این تکرار فیزیکی درمحیط تازه است، نه صرفاً خطای دسترسی. علتUNRESOLVED ومانع بحرانی پذیرش. نمونه اصلی محفوظ؛ readonly-failure-db.json.

پروب اصلی در/tmp:1PASS27.79s،326revision سالم،64خروجی جدید؛ اجرای دارای مشاهدهworkspace:1PASS31.30s،652snapshotبدونinode mismatch؛323ذخیره تشخیصیworkspace:1PASS13.85s. این‌ها تشخیصی/هم‌پوشان‌اند، به جامع اضافه نشوند. موفقیتretry خطای اول را رفع‌شده ثابت نمی‌کند.
