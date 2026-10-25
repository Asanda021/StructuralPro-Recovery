# پذیرش اجرایی Work — ۲۵ اکتبر ۲۰۲۶

کد مرجع c261a79fc4e8e54f085858b095161999bb308069، Tree 7c13c4a3ffd815de7dac6a721c8c856004ea78c7. PR25 Draft/Open/Unmerged؛ اولویت‌های۴،۵،۶ PARTIAL.

محیط مستقل Python3.12.14/SQLite3.53.1/Linux، نصب واقعی requirements و IfcOpenShell؛ نسخه‌ها در environment.json و installed.txt. QApplication/QTest واقعی offscreen موفق. نسخه‌های جدید از الزامات باز مخزن نصب شدند؛ با اجرای قدیم یکسان فرض نشوند.

نمونه خراب تاریخی فقط‌خواندنی بررسی شد؛ SHA ثابت561550b8d0bb42fb5bb3ec002222894414d2740c19f66d2cbb815728945793f6، integrity دارای حلقه صفحه۱۵. startup و backup جدید هر دو آن را رد کردند؛ هیچ بکاپ خروجی نماند. علت تاریخی UNRESOLVED.

اجرای هدفمند اولیه:26PASS/1FAIL/0ERROR/0SKIP در50.62ثانیه. آزمون اصلی tests/test_phase4_site_acceptance.py موفق، اما پروب دوم پایدار در مسیر workspace هنگام INSERT نسخه جدید با SQLite OperationalError: attempt to write a readonly database متوقف شد. این خطا هنوز به محصول یا محیط نسبت داده نشده؛ فایل شکست حفظ است. شواهد اصلی targeted.log/xml/exit. نتیجه retry جای این شکست را نمی‌گیرد.

رگرسیون جامع درحال اجراست؛ خروجی میانی PASS نهایی نیست. ناظر اولیه psutil به دلیل اختلاف PID قابل‌مشاهده فرایند فرزند و /proc شکست خورد؛ ناظر خارجی جداگانه آغاز شد. آزمون‌ها،آستانه0.5 وGC تغییر نکرده‌اند.
