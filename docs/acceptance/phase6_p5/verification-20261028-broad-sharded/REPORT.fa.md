# P6-5 | ریشه‌یابی Timeout گسترده Windows و رگرسیون بدون افت پوشش

**تاریخ:** ۲۸ اکتبر ۲۰۲۶ | **وضعیت گیت اصلی:** PARTIAL (اجراهای جدید هنوز کامل نشده‌اند)

## ۱. نتیجه قطعی شکست پیشین
- [CI #40676687299](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40676687299)، روی کد `facbe18af8f051e52cac250410b72f688655f7a9`، **completed/failure**.
- Linux: **۸۳۸۶ collected، ۸۳۸۱ PASS، ۵ SKIP مخصوص Windows، صفر FAIL**، exit 0، بدون timeout.
- Windows native: **`pytest_exit_code=124`، `timed_out=true` پس از ۱۵۰۰ ثانیه، JUnit نهایی ندارد**؛ artifact `12812591996` (JSON/Log اصلی) و SHA-256 ZIP `bf67cdbe855616b43f4b82c4ab0f568c51b3046f47bbce0ef1501181319988c2`.
- آخرین نقطه اجرای گزارش‌شده در حدود ۷۴٪: `tests/test_phase6_p5_e6_ifc_transfer_history.py::test_independent_ifc_groups_preserve_total_and_other_owners_on_undo[20]`. پس از ۶۰ ثانیه faulthandler، stack در `core/projects/store.py:508 save` و `core/drawings/ifc_pipeline.py:168 review_identity` ثبت شده است.
- این شواهد **علت قطعی قفل SQLite را اثبات نمی‌کند**؛ اجرای کامل Windows قبل از این پرونده از سقف یک subprocess فراتر رفته است. همان آزمون [20] در بسته محدود دو‌سیستمی قبلی [#40676687306](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40676687306) همراه با ۴۹۱ آزمون اصلی موفق بود.
- شکست و Artifact اصلی محفوظ‌اند و به PASS تبدیل نمی‌شوند.

## ۲. اصلاح زیرساخت آزمون بدون کاهش پوشش
- `cb401a255e0e4763014da184de3c82aab4ba7f52`: `run_quarantined_workflow_qa.py` از `--shard-count` و `--shard-index` پشتیبانی می‌کند؛ همه فایل‌های `tests/test_*.py` فعال با ترتیب ثابت و برش‌های بدون همپوشانی تقسیم می‌شوند. ۱۵ ماژول تاریخی طبق سیاست قرنطینه قبلی جدا می‌مانند، نه اینکه از پوشش جاری تازه حذف شوند.
- `cfa33bf7ab439b2336889868d17f948378d6761b`: صحت گروه‌بندی و کنترل Union شواهد XML/JSON واقعی اضافه شد؛ خروجی‌های Windows باید با مجموعه JUnit کامل Linux از همان SHA تطبیق داشته باشند. کمبود، تکرار، FAIL، Timeout، نبود JUnit، عدم تطبیق SHA Manifest و اختلاف شمارش، همگی **گیت را قرمز می‌کنند**.
- `1b9bbc8dba0a6e0bfbc41930818b8b6d4b61f1ab`: Workflow اصلی رگرسیون گسترده، روی کد قفل‌شده `cfa33bf...`، یک Linux کامل و **سه Windows native shard موازی** با سقف ۱۵۰۰ ثانیه برای هر بخش اجرا می‌کند. `verify-full-union` فقط پس از موفقیت همه Jobs، تمام JUnitها را با هم می‌سنجد. هیچ آزمون به دلیل تقسیم حذف/Skip/XFail نشده و حد زمانی هر shard افزایش نیافته است.
- [CI جدید #40681114708](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40681114708) در لحظه ثبت شروع شده و نتیجه نهایی ندارد؛ `PASS` جامع یا حل قطعی مشکل ادعا نمی‌شود.

## ۳. گیت E4 و موارد مسدود مهندسی
- اصلاح ناوبری تک‌مقصدی E4 روی `69dcdd09aa8963bc694638ea912417b263540608` در [CI #40679324114](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40679324114) **Windows و Linux success**؛ تست جدید ۴۹۲مین آزمون اصلی است. این فقط پذیرش تخصصی است نه broad فعلی.
- E4: DWG بدون provenance تبدیل و IFC فاقد crosswalk مستقل همچنان fail-closed.
- E6: مالکیت مشترک بتن/میلگرد/پوشش و Crosswalk معکوس بدون سند مستقل، عمداً BLOCKED؛ Split/Merge و Undo/Redo فقط در دامنه بازبینی‌شده دارای قرارداد معتبر اجرا می‌شوند.
- W1/IFC MEP و A2 مدل GGUF تجاری بدون مجوز/داده معتبر هنوز PARTIAL/BLOCKED؛ P6-6 آغاز نشده، و UAT فیزیکی Windows گیت انسانی مجزا است.

## ۴. شرط پایان
پس از اتمام CI جدید، JUnit و گزارش JSON هر سه Windows و Linux بررسی شود. تنها پس از `verify-full-union SUCCESS` می‌توان **گیت رگرسیون گسترده همین SHA** را بست؛ در غیر این صورت خطای shard/تست باید با شاهد رفع و تکرار شود. این موفقیت به‌تنهایی E4/E6/W1/A2 یا فاز ۶ را کامل نمی‌کند.

**حفاظت:** PR #33/#34 باز و Draft و بدون Merge؛ main بدون تغییر؛ بدون Force Push، EXE، Release یا فاز جدید. نقشه راه ۸ فاز و پیشرفت رسمی ثبت‌شده کل پروژه ۸۵٪ بدون تغییر.

**خلاصه چت:** این نوبت با نتیجه منفی Windows broad در ۷۴٪ آغاز شد؛ برای حذف timeout تک‌فرآیندی بدون تقلیل آزمون، روش تقسیم/تطبیق کامل چند Runner پیاده و CI واقعاً راه‌اندازی شد. نتیجه نهایی دو‌سیستمی هنوز تعیین‌کننده است.
