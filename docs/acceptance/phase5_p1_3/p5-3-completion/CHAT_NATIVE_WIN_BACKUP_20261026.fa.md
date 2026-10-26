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
- **بسته ترکیبی هنوز در Drive آپلود نشده** و فقط از طریق فایل خروجی گفت‌وگو و Artifact گیت‌هاب قابل دریافت است؛ بکاپ مرجع دادهٔ پیشین در Drive محفوظ است. از آن به‌عنوان بکاپ دادهٔ «تازهٔ P5-3» یاد نشود.

## ۳) رگرسیون جامع
- نخستین workflow جامع در [#40297410384](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40297410384) قبل از اجرای تست‌ها به خاطر ۱۵ خطای جمع‌آوری مربوط به workflow policy قدیمی متوقف شد. شکست محصول نبود.
- برای اجرا، ۱۶ آزمون سیاست workflow که به `.github/workflows` فعال inherited از PR #25 اعتراض دارند، با وضعیت **BLOCKED** از مجموعهٔ اجرایی جدا شدند؛ نه حذف از مخزن و نه موفق قلمداد شدند. آن ۱۶ مورد هنوز نیازمند رفع تضاد سیاست/پذیرش مستقل‌اند.
- اجرای جامع مجدد: [#40297663838](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40297663838)؛ نتیجهٔ نهایی در گزارش تکمیلی باید از لاگ و JUnit خود Run نوشته شود، نه حدس.

## وضعیت پروژه/این چت
P5-1 و P5-2 در Linux COMPLETE؛ Windows native security gate فعلاً روی دامنهٔ آزمون‌شده موفق است. P5-3 تا نتیجه رگرسیون نهایی، Office واقعی، پذیرش مهندسی و تأیید مالک **PARTIAL**. فاز چهار نیز PARTIAL، عامل قدیمی جابه‌جایی SQLite نامعلوم. نقشه‌راه همچنان دقیقاً ۸ فاز و یک نسخه کامل Windows است.
