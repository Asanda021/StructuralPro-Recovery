# StructuralPro | فاز ۸ / P2 | اجرای بومی C API برای خطای ۶۸

**حکم فعلی: PARTIAL / NO-GO.** این بسته برای اجرای تشخیصی در محیط دارای LibreDWG واقعی است. این بسته به‌تنهایی منشأ خطای ۶۴ را تعیین نمی‌کند. هیچ داده CAD اختصاصی برای GitHub مجاز نیست.

## آنچه در ۴ آبان ۱۴۰۵ واقعاً انجام شد

- DWG اصلی از بسته خصوصی استخراج و امضای AC1018، اندازه ۳٬۴۶۴٬۰۹۹ بایت و SHA-256 آن با شواهد قبلی تطبیق شد.
- در محیط کنونی هیچ فایل اجرایی `dwgread` یا `dwg2dxf` و هیچ `libredwg.so` نصب نبود؛ DNS هم برای نصب یا ساخت نسخه `a835758` در دسترس نبود.
- لاگ پیشین C API فقط `dwg_read_file_error=68 objects=101504` را ثبت کرده است؛ `dwgread.stderr.log` فقط `SUCCESS` دارد. لاگ سطح شیء برای تعیین عامل `VALUEOUTOFBOUNDS` موجود نیست.
- ابزار تشخیصی با اجرای **مستقیم** `dwg_read_file()` در یک برنامه C ساخته شد. ابزار همراه آن: SHA منبع، SHA برنامه و کتابخانه، تطبیق لینک‌کننده واقعی، پنجره خصوصی ثبت stderr و جلوگیری از پذیرش مالی را کنترل می‌کند.
- آزمون‌ها صرفاً مصنوعی‌اند؛ از هیچ باینری LibreDWG واقعی یا DWG خصوصی در CI استفاده نمی‌کنند.

## طرز استفاده در محیط آفلاینِ دارای LibreDWG پین‌شده

1. سورس LibreDWG دقیقاً در Commit `a835758` را از منبعی قابل اعتماد تهیه کرده و هویت کامل Commit را ثبت کنید. زمان build از `--enable-trace` استفاده کنید. مسیر نرم‌افزار اصلی باید محلی باشد و هیچ داده‌ای به GitHub ارسال نشود.
2. نمونه ساخت در Linux پس از نصب کتابخانه و header همان build:

```sh
cc -O2 -DSTRUCTURALPRO_LIBREDWG_COMMIT='"a835758"' \
  tools/structuralpro_libredwg_capi_probe.c \
  $(pkg-config --cflags --libs libredwg) \
  -o /ABSOLUTE/PRIVATE/BIN/structuralpro_libredwg_capi_probe
```

3. یک پوشه خصوصی با سطح دسترسی `0700` و فایل پیکربندی JSON با `0600` بسازید. چهار کلید آن فقط `source_sha256`, `helper_sha256`, `library_sha256`, `libredwg_commit` است. هش‌ها باید از فایل واقعی و باینری واقعی به دست آیند. **هرگز از SHA یا Handle خصوصی در آرگومان command line، artifact عمومی یا GitHub استفاده نکنید.**
4. با `PYTHONPATH=.` و در محیط Linux فراخوانی کنید:

```sh
python -m tools.audit_phase8_p2_libredwg_native_capi \
  /ABSOLUTE/PRIVATE/ORIGINAL.dwg \
  /ABSOLUTE/PRIVATE/config.json \
  /ABSOLUTE/PRIVATE/BIN/structuralpro_libredwg_capi_probe \
  /ABSOLUTE/PRIVATE/LIB/libredwg.so.ACTUAL \
  /ABSOLUTE/PRIVATE/RESULTS
```

مسیر `RESULTS` باید از پیش وجود داشته باشد و سطح دسترسی `0700` داشته باشد. خروجی، فایل JSON گزارش و stderr کامل است؛ هر دو فقط در پوشه خصوصی ذخیره می‌شوند. در Windows تا کنترل مستقل DACL، ابزار عمدتاً `NO-GO` برمی‌گرداند.

## گیت‌های فنی

- `exit=0` برنامه کمکی به معنی صفر بودن error mask نیست؛ مقدار مستقیم `dwg_read_file` جداگانه در خروجی ماشینی ثبت می‌شود.
- اگر شواهد قبلی ۶۸ بودند و اجرای جدید ۶۸ نبود، **تفاوت نسخه/ساخت/محیط باید بررسی شود**؛ هیچ کدام را به‌طور خودکار خطا یا سالم اعلام نکنید.
- حتی اگر `mask=68` دوباره ثبت شود، محل بیتی که `VALUEOUTOFBOUNDS` را ایجاد کرده باید از trace معتبر و در صورت نیاز ابزار instrumentation محل setting پرچم در کد منبع استخراج شود؛ متن همسایه به‌تنهایی علت قطعی نیست.
- پس از یافتن محل واقعی ۶۴، بررسی جداگانه ۴، MAP/AEC، شناسه مالکیت، واحد، SHX و هر ۱۴۳ ردیف مالی باقی است.

**بازبینی Claude:** الان لازم نیست. فقط در صورت تغییر منطق decoder و نگاشت proprietary object به جای صرفاً trace، بازبینی مستقل پیشنهاد می‌شود.

**سیاست:** PR #47 Draft، بدون Merge، هیچ فایل DWG/DXF یا SHA خصوصی در مخزن؛ مالی ۰ ردیف پذیرفته شده؛ درصد ۸۹٫۶٪ بدون تغییر.