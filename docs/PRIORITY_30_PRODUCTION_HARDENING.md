# Priority 30 — Production Hardening

این مرحله یک acceptance layer برای release surfaces محلی ایجاد می‌کند.

## Checks
- VERSION معتبر
- حضور packaging surface اصلی
- اسکن candidateهای secret در source/packaging
- fail-closed در صورت ناقص بودن هر بخش

## اصلاح واقعی
مسیر ROOT در core/platform/release_security.py اصلاح شد تا از core/platform به ریشه واقعی repository برسد. در نتیجه اسکن امنیتی اکنون core، app، packaging و .github را از ریشه صحیح بررسی می‌کند.

## محدودیت
این gate جایگزین code-signing، Windows hardware acceptance، بررسی حقوقی dependencyها یا secret scanning سرویس CI نیست؛ فقط یک کنترل deterministic داخل پروژه است.
