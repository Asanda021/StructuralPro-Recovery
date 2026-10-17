# StructuralPro — گام ۵: آزمون یکپارچه هشت سیستم سقف (نتیجه واقعی، ناقص)

**تاریخ:** ۲۰۲۶-۱۰-۱۶
**مخزن/شاخه:** `Asanda021/StructuralPro-Recovery` / `fix/integrated-priorities-1-15-20261013`
**PR:** #18 Draft؛ بدون Merge/Actions/Build/Release.
**آخرین کد گام ۴:** `85bc70b2d2a37f541c33a1f88b07478aa709dca1`
**ابزار قابل‌تکرار مرحله ۵:** `scripts/verify_eight_roofs_step5.py`

## ۱. مبنای واقعی آزمون
دسترسی DNS محیط اجرای Chat به GitHub برقرار نبود. بنابراین فایل ZIP معتبر موجود در Library Dropbox دریافت و استخراج شد:
- `/StructuralPro/Backups/StructuralPro_HollowCore_Package3_20261015T220628Z_540a1320.zip`
- Commit داخل بکاپ: `540a132075aff8e253074a61104003b54373783c`؛ **قدیمی‌تر از کد یوبوت/کوبیاکس Chat**.
- SHA-256 واقعی ZIP: `4fd7b11bd53c675db062d8eea426822733076f4798c7c695883863b3e6ed26ee`.
- ZIP شامل ۱٬۷۲۰ ورودی بود؛ استخراج امن انجام شد.
- محیط: Python 3.13.5، pytest، openpyxl، python-docx، PyMuPDF موجود. `PySide6`، `arabic_reshaper` و `python-bidi` موجود نبود.

## ۲. شواهد آزمون واقعی
اجرای نخست: **۲۶ PASS**، سپس شکست خروجی PDF صرفاً به علت نبود `arabic_reshaper`. اجرای دوم: **۱۵۹ PASS**، سپس شکست صادرات XLSX به‌علت نبود `PySide6` برای تاریخ شمسی. این مشکلات محیطی را حذف یا پنهان نکردیم.

اجرای نهایی محدود روی همان ZIP:
```bash
PYTHONPATH=.:tests pytest -q \
  tests/test_roof_specialist_work.py \
  tests/test_waffle_specialist_work.py \
  tests/test_hollowcore_specialist_work.py \
  -k 'not report and not real_detail_amendment'
```
| دامنه | PASS | FAIL | ERROR | SKIPPED | DESELECTED | Exit |
|---|---:|---:|---:|---:|---:|---:|
| محاسبه/گردش غیرگزارشی شش سیستم روی بکاپ `540a1320` | ۱۵۹ | ۰ | ۰ | ۰ | ۱۱ | ۰ |
| کد جدید هشت سیستم روی HEAD PR #18 | اجرا نشده | — | — | — | — | — |
| Qt، Windows، چهار خروجی روی کد جدید | اجرا نشده | — | — | — | — | — |

`python -m compileall -q core app tests` برای **بکاپ قدیمی** با خروج صفر اجرا شد. این تأیید نحویِ آخرین HEAD نیست.

## ۳. گیت آفلاین قابل‌تکرار
`scripts/verify_eight_roofs_step5.py` به PR اضافه و محتوای Git blob آن با نسخه آزمایش‌شده محلی **دقیقاً یکسان** تأیید شد.

- `--mode legacy-core`: حالت محدود شش سقف، ۱۵۹ PASS و ۱۱ DESELECTED، `fully_accepted=false`. آزمون واقعاً اجرا شد.
- `--mode eight-roofs`: تا وقتی Git HEAD دقیقاً با SHA ورودی یکسان نباشد، هر هشت قرارداد/فایل آزمون وجود نداشته باشند یا وابستگی‌های Qt/PDF نصب نباشند، پیش از pytest با کد خروج **۲** و رسید خطا مسدود می‌شود.
- اجرای همین گیت کامل روی بکاپ قدیمی: **Exit 2**؛ این Fail-Closed عمدی است، نه PASS محصول.
- هر اجرا فایل‌های `receipt.json`، `pytest.xml` و `pytest.log` مخصوص خود را تولید می‌کند؛ گزارش آزمون قدیمی به اجراهای جدید نسبت داده نمی‌شود.

## ۴. کارهای ضروری برای بستن گام ۵
۱. دریافت/checkout آخرین SHA واقعی شاخه PR #18 روی میزبان دارای Git و وابستگی‌های `requirements.txt`. بدون اجرای GitHub Actions.
۲. اجرای گیت زیر از ریشه مخزن:
```bash
python scripts/verify_eight_roofs_step5.py --mode eight-roofs --source-ref "$(git rev-parse HEAD)" --output-dir ./step5_local_acceptance
```
در Windows PowerShell از `(git rev-parse HEAD)` برای SHA استفاده شود. در Linux/headless محیط Qt offscreen آماده شود.
۳. اجرای واقعی دو آزمون یوبوت و کوبیاکس، رفع هر FAIL/ERROR بدون حذف/تضعیف تست و سپس رگرسیون جامع کل مخزن.
۴. کنترل کلیک واقعی فرم‌ها، SQLite/بازگشایی/اصلاحیه/BOQ و بازکردن واقعی PDF، XLSX، DOCX و CSV برای هر هشت خانواده با دامنه‌های پذیرفته‌شده.
۵. بکاپ **جدید بر مبنای همان HEAD** با هش و دانلود/بازیابی SQLite/Git و حفظ نسخه‌های پیشین.
۶. آزمون Windows و Microsoft Office و نمونه نقشه/دیتایل واقعی، فقط در صورت فراهم‌بودن اجرا و مدرک.

## ۵. رأی پذیرش
- **شش سیستم قدیمی:** فقط ۱۵۹ آزمون غیرگزارشیِ اجراشده روی آرشیو قدیمی، موفق.
- **یوبوت و کوبیاکس:** کد و تست جدید روی GitHub موجود؛ **آزمون روی HEAD جدید اجرا نشده**.
- **هشت سقف یکپارچه:** **BLOCKED / NOT ACCEPTED**.
- **بکاپ و بازیابی آخرین HEAD:** ایجاد نشده.
- فاز ۱، فاز ۲ (نقشه) و فاز ۸ (Windows/قبولی مالک) جدا باقی می‌مانند؛ پذیرش نهایی ممنوع.

پیوست محلی `StructuralPro_Step5_Partial_Evidence_20261016.zip` شامل JUnit، رسیدهای اجرای محدود و مسدودشده، لاگ و ابزار متناظر است. **این ZIP بکاپ کد آخرین HEAD نیست.**

**تغییرات این گام:** فقط ابزار آزمون و سند حسابرسی؛ بدون دستکاری شش موتور قبلی، ۱۹۳ Workflow، StructuralBot یا main.
