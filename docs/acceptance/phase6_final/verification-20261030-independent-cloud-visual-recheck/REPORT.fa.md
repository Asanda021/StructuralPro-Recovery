# بازبینی مستقل CI و اسکرین‌شات Windows فاز ۶ | ۳۰ اکتبر ۲۰۲۶

## دامنه و محدودیت روش
این گزارش از خواندن مستقیم لاگ GitHub Actions، فهرست Jobها و Artifactها و بازکردن واقعی PNGهای بارگیری‌شده برای دو مقیاس ۱۲۵٪ و ۲۰۰٪ تهیه شد. این آزمون‌ها در Runner ابری `windows-2022` با `QT_QPA_PLATFORM=windows` اجرا شده‌اند؛ **نه** روی دستگاه فیزیکی مالک. دستگاه، مانیتور چندگانه، DPI واقعی Windows، GPU فیزیکی، disconnect/reconnect و sleep/resume در این بازبینی در دسترس نبودند و PASS ثبت نمی‌شوند. هیچ ادعای پذیرش یا امضای مالک مطرح نیست.

## هویت سورس و نتایج مشاهده‌شده
- HEAD کد بررسی‌شده: `3a288b8b821bcb6516f7eee0d5255c06174790b4` (قبل از ثبت این سند شواهد).
- [اجرای جامع / targeted](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41041489435): هفت Job همگی SUCCESS؛ اتحاد JUnit در Job verify-full-union: **۷۲۰ ماژول، ۸٬۴۸۲ case یکتا در هر سیستم**، Windows: **۸٬۴۷۵ PASS / ۷ SKIP / ۰ FAIL / ۰ ERROR**؛ Linux: **۸٬۴۷۷ PASS / ۵ SKIP / ۰ FAIL / ۰ ERROR**. هیچ timeout ثبت نشد؛ هر سه Windows shard و union بررسی شدند. targeted-contract Windows: **۳۴۹ PASS**.
- [اجرای Native Shell](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41041489949): برای هر یک از مقیاس‌های منطقی `1`، `1.25`، `1.5`، `2`، **۱۵ PASS و صفر FAIL**؛ همه از لاگ Job مستقل و با backend Windows تأیید شدند.
- [اجرای پذیرش E3–E6](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41041489479): SUCCESS روی همین SHA.
- [PR #34](https://github.com/Asanda021/StructuralPro-Recovery/pull/34): در زمان بررسی Open/Draft/Unmerged.

## ممیزی مستقیم تصاویر
دو Artifact واقعی GitHub بدون اتکا به شمارنده PASS بارگیری و PNGهای زیر مشاهده شد:
- [مقیاس ۱۲۵٪، Artifact #12970333181](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41041489949/artifacts/12970333181): `screenshots/p6-p1-win32-light.png`، `screenshots/p6-p1-win32-dark.png`، `docks/workspace.png`، `docks/model-dock.png`.
- [مقیاس ۲۰۰٪، Artifact #12970975411](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41041489949/artifacts/12970975411): همان چهار PNG و JUnit.

**مشاهده قطعی:** متن اصلی فارسی، تب‌ها، ریبون و تم روشن/تاریک در هر دو تصویر shell قابل رؤیت و عمدتاً خواناست. در دو تصویر `docks/workspace.png` و `docks/model-dock.png` مقیاس ۲۰۰٪، پهنای کنترل‌های پنل از ناحیهٔ قابل مشاهده بیشتر است؛ اسکرول افقی وجود دارد و برخی برچسب‌ها و کنترل‌های کناری در قاب فعلی کامل دیده نمی‌شوند. در نمای Shell نیز بخش کوچکی از متن/المان‌های کنار لبهٔ چپ محتوای اصلی بریده دیده می‌شود. این **مشاهده محدود به سایز پنجره و تنظیمات CI در همین PNGها**ست و اثبات نمی‌کند کنترل‌ها در پنجرهٔ بزرگ‌تر غیرقابل دسترسی‌اند یا کل محصول خراب است. با این حال «PASS صرفاً از روی JUnit» برای پذیرش بصری کامل ۲۰۰٪ کافی نیست.

**تأثیر:** `VISUAL_REVIEW_REQUIRED` برای تراکم و برش برچسب‌ها در پنل‌های 2D/3D در DPI بالا؛ نقص محاسبه/داده یا انتشار آسیب‌دیده مشاهده و ادعا نشده است. پیش از برچسب‌گذاری `UX_FULLY_ACCEPTED` باید چیدمان پنل‌ها از نظر عرض کم و دسترسی به تمامی کنترل‌ها آزمایش/اصلاح شود. گیت فیزیکی G4 همچنان معلق است.

## نتیجهٔ قابل دفاع
- `AUTOMATED_FUNCTIONAL_CI = PASS` برای سورس `3a288b8b...`.
- `NATIVE_WINDOWS_SHELL_LOGS = PASS` برای ۴ مقیاس منطقی؛ تصاویر واقعی بازخوانی شدند.
- `VISUAL_DPI_200 = OBSERVED_HORIZONTAL_OVERFLOW / REVIEW_REQUIRED`.
- `PHYSICAL_GPU_MULTIMONITOR_SLEEP_RESUME = NOT_TESTED`؛ هیچ تأیید ساختگی ثبت نشد.
- `OWNER_SIGNOFF = NOT_PROVIDED`.
- `PHASE6 = PARTIAL / NO-GO` طبق قرارداد پذیرش موجود؛ همچنان هشت فاز مصوب و پیشرفت رسمی ۸۵٪. هیچ تغییر به نرم‌افزار، تست‌ها، main، Merge، EXE یا Release در این بازبینی انجام نشد.

**نکته نسخه‌بندی:** سند `closure-decision-20261029/GATES.json` پیش از این بازبینی هنوز به رگرسیون `683e2ad...` ارجاع می‌داد. آمار جدید این گزارش منحصراً بر مبنای اجرای مستقیم روی `3a288b8...` است؛ بدون به‌روزکردن قرارداد مصوب یا تغییر تصمیم مالک.
