# فاز ۵ / اولویت ۲ — بکاپ و بازیابی مستقل

تاریخ اجرا: ۲۵ اکتبر ۲۰۲۶. مبنای کد P5-1: Commit `7293b89e0b0753192d8e26c52b3d87e52cde7a02` و Tree `8881d416cbedd4a9869e6711bdb18eefcb9d4196`.

## نقص‌های اثبات‌شده و RED→GREEN

۱. Manifest بسته فقط format/version/project_id/SHA داشت. آزمون RED مقدار version را ۱ به‌جای ۲ دید. format v2 اکنون schema، Revision و وضعیت آن، UTC، producer، سلامت، فایل‌ها، اندازه و SHA-256 را نگه می‌دارد؛ خواندن v1 قدیمی حفظ شده است.

۲. `tmp.replace(path)` در رقابت انتشار، فایل ایجادشده توسط فرایند دیگر را overwrite کرد؛ تست RED با `DID NOT RAISE` شکست خورد. انتشار JSON و package اکنون با hard-link هم‌مسیر و no-replace اتمیک است و temp در خطا پاک می‌شود.

۳. تغییر جعلی schema در Manifest با payload تطبیق داده نمی‌شد؛ تست RED بدون خطا عبور کرد. restore اکنون schema و Revision Manifest را با payload تطبیق می‌دهد و backup قدیمی‌تر از `minimum_revision` را رد می‌کند.

۴. بسته اسناد منشأ را حمل نمی‌کرد و تست RED با `unexpected keyword argument attachments` شکست خورد. همان BackupManager اکنون فقط اعضای امن `sources/` و `attachments/` را می‌پذیرد، همه را با size/SHA در Manifest ثبت می‌کند، ZIP دارای عضو اضافه/تکراری/symlink/مسیر traversal را رد می‌کند و فقط در staging تازه استخراج می‌کند.

## آزمون و بازیابی

- مجموعه هدفمند backup/recovery و سازگاری قبلی: **۳۲ PASS، صفر FAIL/ERROR/SKIP** در ۱٫۱۴ ثانیه.
- JUnit SHA-256: `01c50e6b0aa80ae5311e2a18832dac7016f78c88a3cdcf35fb97155f59db1cf1`.
- package پنج‌طبقه: `five-storey.spbackup`، SHA-256 `5ffa57f58af34f3442e917b0c09623ac89f0b15bf0ac3d748b34291cd9528cf4`.
- restore با مسیر اصلی عمداً unavailable انجام شد. نتیجه: ۵ طبقه، ۱۵ فعالیت، ۱۸/۲۰ روز، پیشرفت ۱۲٫۵/۴۵/۷۵، ۵ ردیف BOQ، ۴ منبع، ۲ گزارش روزانه، ۳ رکورد مالی، ۴ سند منشأ و ۵ فایل restored.
- SQLite کامل: ۳۲۶ Revision، active Revision 326، `integrity_check=ok` و project/revision counts برابر ۱/۳۲۶.

## Google Drive و بازدریافت

SQLite کامل ۵۸٬۹۳۷٬۳۴۴ بایتی با ID `1wWdyqr5i7046nX6e-RU_dGnk0DQxV5LS` ذخیره شد. فایل از Drive دوباره دانلود و فقط همان فایل باز شد؛ SHA-256 رفت و برگشت هر دو `1712cff0d83d8798ce644e4663ec9464585d47922bba25b6a44abc835a8103cd`، integrity سالم و Revision 326/326 بود. `drive-receipt.json` مدرک ماشین‌خوان است.

اجرای نخست verifier پیش از عملیات به‌علت نبود `PYTHONPATH` شکست خورد و در `restore-attempt1-env-error.*` حفظ شده است. اجرای دوم با کد صفر در `restore.*` ثبت شد؛ شکست محیطی به PASS تبدیل نشده است.

## مرز پذیرش

بکاپ/restore غیر ویندوزی و مستقل برای سناریوی مصنوعی معتبر است. این شواهد تضمین مطلق عدم ازدست‌رفتن داده، Windows Native، Microsoft Office، پذیرش مهندسی پروژه واقعی یا تأیید مالک نیست.
