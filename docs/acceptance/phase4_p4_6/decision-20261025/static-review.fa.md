# بررسی مسیرهای عملیات فایل

مبنا: HEAD958273c36ad6f90dee41e2616aadad7613fbac25، Tree9b19457d34c5e0eb2f2ebcce3f1d6f283254ca76. محصول با a153828 یکسان است.

جست‌وجوی گسترده در core/app/scripts/tests و تمام QA فاز۴ برای projects.db، rename/replace/remove/unlink/rmtree/copy/link انجام شد؛ فهرست خام و شماره خطوط در expanded-file-operations.txt، product-file-operations.txt و qa-file-operations.txt ثبت است. نتایج replace روی رشته‌ها نیز عمداً در فهرست خام هستند؛ عملیات فایل محسوب نشده‌اند.

- core/platform/application.py:68 مسیر داده دریافت‌شده را به ProjectStore می‌دهد؛ مسیر پیش‌فرض Windows تغییر نکرد.
- core/projects/store.py: اتصال SQLite، BEGIN IMMEDIATE، دو INSERT و COMMIT/ROLLBACK؛ close اتصال را می‌بندد. هیچ unlink/rename/replace پایگاه ندارد. INSERT OR REPLACE عملیات ردیف SQL است، نه جایگزینی فایل.
- core/projects/backup.py: rename فایل tmp به JSON یا spbackup و prune فقط glob فایل‌های JSON بکاپ است؛ projects.db هدف نیست.
- core/recovery/recovery.py: منبع فقط‌خواندنی، مقصد متفاوت و جدید، backup API، اعتبارسنجی، hardlink بدون overwrite و حذف فقط فایل موقت. در زنجیره پروب اصلی backup_database فراخوانی نمی‌شود.
- scripts/phase4_sqlite_rescue.py: خروجی مستقل بدون overwrite و حذف فقط فایل موقت؛ در زنجیره پروب اصلی فراخوانی نمی‌شود.
- زنجیره scripts/phase4_site_operations_probe.py → phase4_project_controls_probe.py → phase3_financial_probe.py پوشه می‌سازد و چند بار اتصال را می‌بندد/باز می‌کند؛ حذف یا جابه‌جایی پایگاه در این زنجیره یافت نشد. رندرها و خروجی‌ها فایل‌های مستقل‌اند.
- QA restore_backup.py (نسخه‌های verification/work/closure) پوشه original را عمداً به held منتقل و مسیر را از آرشیو بازسازی می‌کند. این عملیات فقط در اجرای مستقل بازیابی است، نه پروب منجمد شکست‌خورده؛ دلیل وقوع آن در زمان خطای قبلی نداریم.
- QA build_backup.py از scenario کپی می‌کند و ZIP بسته را با link منتشر می‌کند؛ نام مقصد ZIP است، نه پایگاه فعال.
- QA run_sqlite.py پس از پایان subprocess شواهد را کپی می‌کند. sqlite_worker.py رویدادها/کپی شواهد خطا را می‌نویسد؛ منبع را rename/remove نمی‌کند.
- test_dbmoved_calibration.py عمداً fixture جداگانه را جابه‌جا می‌کند؛ در اجرای پروب اصلی جمع‌آوری یا فراخوانی نمی‌شود.
- ابزارهای CAD/pricebook فایل خروجی یا موقت خود را پاک می‌کنند؛ در این سناریو هدف projects.db ندارند. آزمون‌ها عمدتاً fixture اختصاصی خود را دارند و در دو دور جدید فقط targeted_round.py جمع‌آوری می‌شود.

این بررسی عامل را اثبات نمی‌کند و همه کد native/فرایندهای بیرونی را پوشش نمی‌دهد. دور اول sys.addaudithook برای عملیات فایل Python در خود فرایند، همراه observer موجود با inotify و FD ثبت می‌کند. در CapEff مقدار صفر، NoNewPrivs=1 و Seccomp=2 ثبت شد. PTRACE قبلاً ممنوع بوده و استفاده نشد. inotify رویداد و cookie تغییرنام را دارد، نه PID عامل؛ audit hook نیز فقط Python همین فرایند را می‌بیند. بنابراین نتیجه موفق نمی‌تواند عامل بیرونی یا علت فساد تاریخی را اثبات یا رد کند.
