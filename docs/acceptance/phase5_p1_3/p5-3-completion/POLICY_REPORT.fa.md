# گزارش مرحله دوم تکمیل P5-3 — مسیرهای UI، پیوست و سیاست حساس

## REDهای ثبت‌شده

- Editor می‌توانست از مسیر عمومی قدیمی برای تغییر برخی مجموعه‌های مالی غیرledger اقدام کند.
- Viewer می‌توانست `ProjectStore.backup` را مستقیم فراخوانی کند.
- دستکاری ستون persistent Audit پس از حذف trigger، هنگام بازگشایی Store تشخیص داده نمی‌شد.
- مسیر اسناد UI فقط path/name ذخیره می‌کرد و SHA-256 یا کنترل symlink/مالکیت پروژه نداشت.

## اصلاح حداقلی

- فیلدهای مالی، صورت‌وضعیت، review/approved در تغییر مستقیم فقط برای Owner/Admin باز هستند؛
  commandهای معتبر review/approve/apply سیاست نقش جدا دارند.
- Backup کامل فقط برای Owner/Admin همه پروژه‌هاست و رویداد موفق شامل SHA-256/size است.
- زنجیره، head، count، پوشش همه پروژه‌ها و ستون‌های denormalized Audit در startup بررسی می‌شوند.
- مسیر واقعی ثبت سند به سرویس provenance منتقل شد: regular/no-symlink، SHA-256، شناسه پروژه و
  principal ثبت‌کننده؛ تغییر و حذف فایل در بازخوانی آشکار می‌شود.
- انتساب نقش صفحه همکاری اکنون از `grant_role` ممیزی‌شده می‌گذرد؛ ComboBox به‌تنهایی نقش نمی‌دهد.

## GREEN

بسته هدفمند نهایی مرحله: **۱۱۶ PASS، صفر FAIL/ERROR، یک SKIP Windows Native** در ۹٫۰۹ ثانیه.
JUnit: `policy-ui-targeted.xml`.

آزمون وابستگی Backup پس از تغییر مرز مجوز نیز جداگانه ۱۷ PASS داشت. اجرای اولیه همسایه UI
بدون `QT_QPA_PLATFORM=offscreen` پیش از collection با abort Qt پایان یافت؛ اجرای صحیح با
پیکربندی headless مصوب ۳۱ PASS داشت و شکست محصول محسوب نشد.

