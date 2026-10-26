# فاز ۵ / اولویت ۳ — امنیت، هویت و ممیزی

تاریخ اجرا: ۲۶ اکتبر ۲۰۲۶. مبنا: Commit `f64d976e8396efac6471278185ac4ab063524853` و Tree `39beb947d6f13d145d65e4e91af7d1e1e0d8d0b0`.

## RED→GREEN واقعی

آزمون جدید روی Tree مبنا در مرحله collection با نبود `require_authorized` شکست خورد؛ خروجی و JUnit در `red.log` و `red.xml` حفظ شده‌اند. پس از نخستین پیاده‌سازی، دو آزمون زنجیره ممیزی نیز شکست خوردند، زیرا هش رویداد اشتباهاً شامل `previous_hash` افزوده‌شده بود. محاسبه هش به payload پایه منتقل شد و مجموعه نهایی سبز شد.

اصلاحات محدود به زیرساخت موجود هستند:

- `authorize` سازگار باقی ماند و `require_authorized` به‌عنوان مرز صریح Fail-Closed اضافه شد؛ نقش غیرمجاز اکنون exception می‌دهد و با نادیده‌گرفتن مقدار `False` قابل عبور نیست.
- `validate_project_file` مسیر واقعی، regular-file بودن، ممنوعیت symlink، محصوربودن زیر ریشه پروژه و SHA-256 کامل را کنترل می‌کند.
- `AuditTrail.record_controlled` شناسه عامل، نقش ثبت‌شده، پروژه، Revision قبل/بعد، مرجع عملیات و success/failure را ثبت و هر رویداد را به زنجیره SHA-256 متصل می‌کند.
- تلاش غیرمجاز به‌صورت failure و بدون Revision بعد ثبت می‌شود؛ جهش نامعتبر Revision رد می‌شود؛ دستکاری پسینی زنجیره کشف می‌شود.
- API قدیمی AuditTrail برای سازگاری داده‌های تاریخی تغییر قرارداد نداده است؛ رکوردهای قدیمیِ بدون مهر نمی‌توانند بی‌صدا ابتدای زنجیره کنترل‌شده معرفی شوند.

## ماتریس کنترل

| کنترل | مثبت | منفی | نتیجه Linux |
|---|---|---|---|
| نقش و پروژه | editor همان پروژه | viewer و project mismatch | PASS |
| فایل/پیوست | regular file داخل root با SHA درست | پروژه دیگر، symlink، SHA جعلی | PASS |
| تعارض نسخه | CAS و `BEGIN IMMEDIATE` موجود | نسخه/نویسنده هم‌زمان | PASS در آزمون‌های store/concurrency |
| هویت تکراری | کنترل‌های موجود project/workspace | duplicate entity/user | PASS در رگرسیون مرتبط |
| ممیزی | actor/role/revision/reference/success | denial/failure و جهش Revision | PASS |
| ضد‌دستکاری | زنجیره SHA-256 معتبر | تغییر entity در رویداد صادرشده | PASS |
| ورودی ابزار خارجی | اجرای subprocess با argv صریح و بدون shell از قبل موجود | نام/داده ورودی مجوز دیتابیس ایجاد نمی‌کند | ممیزی کد؛ احراز sandbox همه فرمت‌ها نیست |

## آزمون نهایی هدفمند

۵۹ PASS، صفر FAIL/ERROR/SKIP در ۱٫۴۰ ثانیه. این اجرا شامل امنیت جدید، قراردادهای امنیتی قبلی، AuditTrail قدیمی، تراکنش P5-1، بکاپ P5-2، CAS و SQLite backup حین نوشتن است.

- JUnit SHA-256: `b193cb985e99f1373d7b18aea51b7c7f7cb85e9f0242023ab0dbefa3ca18b248`
- log SHA-256: `d56b92cace19fe94138099661be0970e3b6b9b2b521bda741b3f6c14b74421d8`
- Python 3.12.14؛ SQLite 3.53.1؛ Linux 6.18.55 x86_64.

`tests/test_priority_9_qa.py` در checkout زنجیره‌ای PR #25 به‌علت وجود workflowهای فعال همان مبنا در collection fail-closed می‌شود و به شمار ۵۹ اضافه نشده است. این همان مانع شناخته‌شده مبناست، نه PASS و نه regression محصول P5-3.

## مرز پذیرش

کنترل‌های برنامه‌نویسی نقش، جداسازی فایل و ممیزی کنترل‌شده در Linux تکمیل شده‌اند؛ اما این نقش‌ها «احراز هویت واقعی کاربر Windows» نیستند و همه مسیرهای تاریخی UI هنوز principal اجباری ندارند. بنابراین P5-3 تا دروازه هویت/مجوز Windows و اتصال همه عملیات مهم UI به audit کنترل‌شده، `PARTIAL` باقی می‌ماند. Microsoft Office، پذیرش مهندسی واقعی و تأیید مالک نیز مستقل‌اند.
