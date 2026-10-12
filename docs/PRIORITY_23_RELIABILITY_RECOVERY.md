# Priority 23 — Reliability / Recovery

## هدف
افزایش قابلیت اطمینان داده‌های پروژه و امکان بازیابی کنترل‌شده، بدون تغییر رفتار APIهای قبلی.

## قابلیت‌ها
- SQLite online backup با API رسمی backup
- integrity check
- export/import مستقل پروژه با فرمت نسخه‌دار
- SHA-256 برای کنترل صحت فایل export
- اعتبارسنجی سخت‌گیرانه backup قبل از import
- RecoveryError مشخص برای فایل خراب یا فرمت ناشناخته

## اصل ایمنی
Import فقط یک object معتبر را برمی‌گرداند؛ overwrite یا تغییر پروژه در لایه recovery به‌صورت خودکار انجام نمی‌شود. لایه Application می‌تواند بعد از تأیید کاربر آن را ذخیره کند.
