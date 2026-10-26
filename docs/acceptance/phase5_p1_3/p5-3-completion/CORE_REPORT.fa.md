# گزارش مرحله اول تکمیل P5-3 — هویت، ACL و Audit اتمیک

تاریخ اجرا: ۲۰۲۶-۱۰-۲۶ (Linux/Non-Windows)

## RED

- نخستین اجرای `tests/test_phase5_p3_trusted_identity_store.py` در زمان جمع‌آوری با
  `ModuleNotFoundError: core.platform.identity` شکست خورد؛ مرز هویت سیستم‌عامل وجود نداشت.
- پس از افزودن مرز اولیه، بسته سازگاری SQLite دو شکست واقعی نشان داد:
  `begin_write` برای پروژه ناموجود به‌جای `KeyError` خطای مجوز می‌داد و پایگاه سالم قدیمی
  بدون ACL قابل بازشدن نبود.
- تست UI تازه نیز پیش از تزریق provider با
  `TypeError: StructuralProApp.__init__() got an unexpected keyword argument 'identity_provider'`
  شکست خورد.

## GREEN

فرمان نهایی هدفمند:

```text
python scripts/run_offline_tests.py \
  tests/test_priority_68_store_concurrency.py \
  tests/test_phase4_sqlite_dbmoved_safety.py \
  tests/test_phase4_sqlite_open_integrity.py \
  tests/test_phase4_sqlite_parent_directory_safety.py \
  tests/test_phase4_sqlite_startup_replacement.py \
  tests/test_financial_sqlite_concurrency_guard.py \
  tests/test_phase5_transaction_safety.py \
  tests/test_phase5_security_audit.py \
  tests/test_phase5_p3_trusted_identity_store.py \
  tests/test_phase5_p3_ui_authorization.py \
  tests/test_phase4_workspace.py -q \
  --junitxml=docs/acceptance/phase5_p1_3/p5-3-completion/core-targeted.xml
```

نتیجه: **۶۲ PASS، صفر FAIL/ERROR، یک SKIP** در ۴٫۰۰ ثانیه. SKIP فقط آزمون
Windows Native دریافت SID از access token است و در Linux به‌درستی اجرا نشده است.

## نتیجه فنی این مرحله

- Windows: هویت از process/thread access token و SID خوانده می‌شود؛ متغیر محیطی و متن UI
  منبع احراز هویت نیستند.
- POSIX: هویت از effective UID کرنل خوانده می‌شود؛ این نتیجه Windows Native نیست.
- ACL پروژه داخل همان SQLite موجود ذخیره می‌شود و موتور ذخیره‌سازی دوم ایجاد نشده است.
- پروژه تازه، هویت جاری را Owner می‌کند. مهاجرت legacy فقط وقتی انجام می‌شود که مالک فایل
  در سیستم‌عامل با principal جاری یکسان باشد.
- تغییر پروژه و Audit موفق در یک تراکنش‌اند؛ شکست درج Audit تغییر پروژه و Revision را
  Rollback می‌کند.
- رویدادها زنجیره SHA-256، head/count پایدار و trigger منع UPDATE/DELETE دارند.
- مسیر واقعی `ProjectControlsWorkspace` با QTest ثابت کرد واردکردن رشته `owner` در فیلد actor
  برای Viewer مجوز ایجاد نمی‌کند.

محدودیت: Administrator محلی یا مهاجمی که بتواند کل فایل برنامه/SQLite را جایگزین کند خارج از
مرز اعتماد محلی است. SID نیز احراز هویت مستقل ابری یا چندعاملی نیست؛ هویت نشست Windows است.

