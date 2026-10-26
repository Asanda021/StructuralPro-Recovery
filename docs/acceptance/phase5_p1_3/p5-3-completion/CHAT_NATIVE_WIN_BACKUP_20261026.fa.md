# تحویل مستقل Chat — Windows Native و بکاپ P5-3

**زمان بررسی:** ۲۶ اکتبر ۲۰۲۶ / ۴ آبان ۱۴۰۵، فاز پنجم نقشه‌راه هشت‌فازی StructuralPro. فقط PR #26؛ PRهای #23–#25، main، Release و Merge تغییر نکرده‌اند.

## ۱) Windows Native واقعی
[GitHub Actions #40297139578](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40297139578) با نتیجه `success` روی `windows-2022` و Python 3.12 اجرا شد.

**۱۲ PASS، یک SKIP، صفر FAIL/ERROR**. پوشش واقعی شامل Windows access-token/SID از سیستم‌عامل، principal واقعی در Store، ACL، Audit persistent، بازکردن پنجره PySide6 با `QT_QPA_PLATFORM=offscreen` و رفتار فایل SQLite زیر Windows است. فقط SID به‌صورت SHA-256 در شواهد چاپ شده؛ نام کاربری محیطی منبع اعتماد نیست. یک SKIP مربوط به تست مختص POSIX است، نه Windows.

اجرای اولیه [#40296907916](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40296907916) به علت اشتباه در **خود تست افزوده‌شده** (خواندن `SecurityPrincipal.subject_id` به‌جای `SecurityPrincipal.user_id`) قرمز شد؛ قرارداد تست اصلاح و اجرای دوم سبز گردید. این خطا نقص هویت محصول نبود.

**مرز:** اجرای `offscreen` تأیید UI در Win runner است، نه آزمون تعاملی مانیتور واقعی یا برنامه‌های Microsoft Office.

## ۲) بکاپ کد و دادهٔ پنج طبقه
[GitHub Actions #40297565961](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40297565961) با نتیجه `success` یک `git bundle` کامل از شاخه فاز پنجم ساخت، `git bundle verify`، clone مستقل، تطبیق HEAD و `git fsck` را موفق انجام داد.

- Commit بکاپ کد: `286f85d2390052466ceb989c213e53a6bd13e0fa` (محصول P5-3 بر پایه کد `93f936577b8dcd315410d8d6b283cb9c7aeede48`).
- GitHub source artifact ID `12639441743` با ZIP SHA-256 `c196b77cace119fb4456d854cfbe8fd38647bbdb3cc8572120775e1aa7d8f2ee`.
- بکاپ مرجع داده از Google Drive: ID `1TMm1YgEfugGXh1Pc0CrwFIrpMcjNAVbu`، SHA-256 `43118bb70185dc6b66fc39ae17abd1f78061259fc6f67b434c08f66954559e81`. این داده **مربوط به قبل از آخرین تغییرات P5-3** است، نه دیتابیس تازهٔ ممیزی.
- یک بستهٔ ترکیبی جدید در محیط گفت‌وگو ساخته و مستقل بررسی شد: `StructuralPro-Phase5-P5-1-3-Verified-Composite-20261026.tar.gz`، SHA-256 `8beed41127ea962967a669a8b2e5296b629d2cd677f42594d4c72193d125e212`، اندازه `28,335,663` بایت.
- در همان بسته SQLite قدیمی فقط‌خواندنی با `integrity_check=ok`، پروژه `P` و ۳۲۶ Revision؛ git bundle جدید با clone مستقل و `git fsck` بررسی شد.
- **بسته ترکیبی جدید در Google Drive بارگذاری و مستقل بازدریافت شد.** Drive ID: `18Rxgr40-s7tkY5Ux07koo0ITZHqfhJ9v`، [لینک فایل](https://drive.google.com/file/d/18Rxgr40-s7tkY5Ux07koo0ITZHqfhJ9v/view). SHA-256 رفت‌وبرگشت: `8beed41127ea962967a669a8b2e5296b629d2cd677f42594d4c72193d125e212`، بایت‌ها برابر. **این بسته کد فعلی P5-3 + دیتابیس معتبر P5-2 است، نه دیتابیس تازهٔ P5-3**. بکاپ قدیمی نیز حذف یا جایگزین نشده است.

## ۳) رگرسیون جامع
- نخستین workflow جامع در [#40297410384](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40297410384) قبل از اجرای تست‌ها به خاطر ۱۵ خطای جمع‌آوری مربوط به workflow policy قدیمی متوقف شد. شکست محصول نبود.
- برای اجرا، ۱۶ آزمون سیاست workflow که به `.github/workflows` فعال inherited از PR #25 اعتراض دارند، با وضعیت **BLOCKED** از مجموعهٔ اجرایی جدا شدند؛ نه حذف از مخزن و نه موفق قلمداد شدند. آن ۱۶ مورد هنوز نیازمند رفع تضاد سیاست/پذیرش مستقل‌اند.
- اجرای جامع مجدد: [#40297663838](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40297663838) **SUCCESS** در Linux Ubuntu 24.04 و Python 3.12 با محدودسازی شبکه توسط seccomp؛ **۷٬۹۰۹ PASS، ۰ FAIL، ۰ ERROR، ۴ SKIP، مدت ۳۸۱٫۹۵ ثانیه**. تعداد Testcaseهای اجراشده ۷٬۹۱۳ بود. ۱۶ ماژول سیاست قبلی با عنوان **BLOCKED (نه PASS و نه SKIP)** از مجموعهٔ اجرایی جدا شدند و علت در manifest اجرای آزمون ثبت شده است. Commit اجرای رگرسیون: `64ae0284ad33233febcbeeac0c6abdc12ea309ca`؛ در مقایسهٔ Commit بکاپ تا گزارش فقط workflow و سند افزوده شدند، بدون تغییر کد محصول.

## وضعیت پروژه/این چت
P5-1 و P5-2 در Linux COMPLETE؛ **دروازه‌های اجرایی P5-3 (هویت Windows، Qt و ACL، رگرسیون محصول و بکاپ بازیابی‌شده) در دامنه‌های صریح بالا اکنون PASS هستند**. ۱۶ ماژول سیاست workflow قدیمی به صورت BLOCKED محفوظ‌اند. تأیید Microsoft Office واقعی، پذیرش مهندسی پروژهٔ واقعی و موافقت مالک مستقل‌اند؛ از این رو پذیرش نهایی کل فاز ۵ هنوز صادر نشده و P5-3 را بدون تأیید مالک `ACCEPTED` نمی‌نامیم. فاز چهار PARTIAL و عامل تاریخی هنوز ناشناخته است. نقشه‌راه دقیقاً ۸ فاز و یک نسخه Windows ثابت مانده است.
