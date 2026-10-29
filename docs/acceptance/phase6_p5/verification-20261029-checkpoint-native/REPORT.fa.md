# Checkpoint عملیاتی Native — ۲۹ اکتبر ۲۰۲۶

**مأموریت تشخیصی: COMPLETE در محدوده دو اجرای درخواست‌شده؛ رفع کرش محصول: OPEN؛ P6-5: PARTIAL.**

## کد و دامنه
HEAD اولیه `620dec1664e00705aad56a8b2b7f0d795613576a`؛ کد تشخیص آزموده‌شده `2d41667121c3b2e1adbd57c904a80bedabfc36b5`؛ Tree کد `4eadacbf3a18391ca50519d4435bc4c2c5c2039b`.
تغییر صرفاً دو فایل جدید: `scripts/diagnostics/p6_native_checkpoints.py` و `.github/workflows/phase6-native-checkpoints.yml`. مقایسه GitHub تأیید کرد هیچ فایل app/core یا آزمون مرجع تغییر نکرد. HEAD تحویل، commit حاوی این گزارش است؛ نتیجه آزمون فقط به SHA کد بالا مربوط است.

ممیزی Runner موجود، oracleهای isolation، CDB control/trace و مرزهای سرویس/فرم/Store انجام شد. توابع پایدار `atomic_json` و `append_jsonl` موجود، با flush/fsync و replace فایل last، مجدداً استفاده شدند. نویسنده checkpoint با چهار رویداد و بازخوانی/ترتیب محلی آزموده شد؛ این آزمون محلی جای Qt ویندوز نیست. Runner فقط در فرایند تشخیصی، فراخوانی متدهای اصلی سرویس را می‌پوشاند و همان ورودی/خروجی و exception را حفظ می‌کند. انتخاب ردیف همان QTest اصلی است. تست و داده ۱۴ عملیات/۷۰ ردیف موجود، بدون دستکاری اجرا شدند؛ fixture اصلی مصنوعی است، نه نقشه واقعی مالک.

## اجرای بدون Debugger
[Run 40839501658](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40839501658): هر دو job SUCCESS؛ Windows Server 2022، Python 3.12، Qt با `windows`، فرایند تازه برای هر تکرار؛ بدون CDB/GDB. فقط دو تکرار انجام شد.

|تکرار|مدت subprocess، ثانیه|Exit|JUnit|آخرین checkpoint|فراخوانی ناتمام|Access Violation|SQLite|BOQ|
|---|---:|---:|---|---|---|---|---|---|
|۱|103.2316713|0|۱PASS،۰FAIL/ERROR/SKIP|CASE_DONE،sequence1361|هیچ|مشاهده نشد|معتبر|معتبر طبق oracle اصلی|
|۲|87.9840191|0|۱PASS،۰FAIL/ERROR/SKIP|CASE_DONE،sequence1361|هیچ|مشاهده نشد|معتبر|معتبر طبق oracle اصلی|

در هر اجرا: READ_ENTER/EXIT هر کدام۴۶۸، REVIEW_ENTER/EXIT هر کدام۷۰، COMMIT_ENTER/EXIT هر کدام۷۰، ROW_SELECTED برابر۱۴۱، و CASE_START/SQLITE_VERIFY/BOQ_VERIFY/CASE_DONE هر کدام۱. تمام۷۰ شماره ردیف و۱۴ شماره عملیات در انتخاب‌ها وجود دارند. ترتیب sequence و monotonic و برابری last.json با آخرین خط journal مستقلاً بازخوانی شد. شماره۰ در مراحل آماده‌سازی یعنی هنوز انتخاب عملیاتی مشخص نشده؛ عدد فرضی به آن مراحل نسبت داده نشد. READها مرز سرویس‌اند و شامل بازخوانی‌های فرم و assertهای آزمون هستند؛ با کلیک دکمه Read یکی فرض نشوند.

SQLITE_VERIFY پس از پایان و بازگشایی آزمون از یک اتصال مستقل فقط‌خواندنی، `PRAGMA integrity_check=ok` را کنترل کرد. BOQ_VERIFY بعد از PASS آزمون اصلی صادر شد: Oracle Decimal اصلی،۷۰takeoff/BOQ با۷۰source یکتا،جمع۱۴خانواده در۵طبقه،گزارشPDF/XLSX،statusهای committed و Reopen اصلی برقرار بودند. اعتبار BOQ یک oracle جدید و موازی نیست. در حین هر مرحله، assertهای همان آزمون اصلی برقرارند؛ integrity فیزیکی بین تک‌تک Commitها اضافه نشده است.

## شواهد
[Artifact تکرار۱،12881768355](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40839501658/artifacts/12881768355)، ZIP SHA256 `3f408fa273e044b10ef444d981a1ccf8915cdfa1a4cf3d6fecf8b8dfe2ed7022`.
[Artifact تکرار۲،12882147579](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40839501658/artifacts/12882147579)، ZIP SHA256 `16b2934fa186e83b7513a2a057f20c28a3ede59ce448ac726a969fefccddacf0`.
هر ZIP بازدریافت و هش آن با digest سرویس تطبیق داده شد؛ حاوی events.jsonl کامل، last.json،summary.json،pytest.log وJUnit واقعی است. summary/JUnit/log/last در همین پوشه نیز پایدار شده‌اند؛ manifest.json وevent-validation.json هش‌ها و شمارش را نگه می‌دارند.

## محدودیت و تصمیم
هیچ `0xC0000005` جدیدی مشاهده نشد؛ **علت کرش تاریخی اثبات نشده و رفع نشده است**. در این اجرا ماژول Native خطاکننده وجود ندارد که استخراج شود. موفقیت کنترل CDB قبلی یا Python stack جای Native exception همان اجرای بدون debugger نیست. wrapper و flush/fsync زمان‌بندی و هزینه I/O را تغییر می‌دهند؛ این دو نمونه، تضمین نبود کرش نیستند. زمان یکنواخت فقط داخل هر فرایند مقایسه شود. checkpoint هیچ فرمول، مقدار مهندسی،شناسه واقعی عضو،اطلاعات شخصی یا SQL خام را ثبت نمی‌کند؛ متادیتای عددی عملیاتی تنها خروجی آن است.

گام بعدی مشخص: فقط در صورت تکرار کرش در اجرای عادی، همان journal/summary را به‌عنوان ورودی تحلیل آخرین ENTER بدون EXIT و آخرین مرحله تکمیل‌شده استفاده کنید؛ در صورت نیاز capture Native جدا با قرارداد CDB کالیبره‌شده انجام شود. هیچ بهینه‌سازی حدسی deepcopy/SQLite/Qt یا تغییر محصول در این مأموریت انجام نشد.

۸فاز،۸۵٪رسمی،فاز۶اولویت۵PARTIAL؛ PR34 Open/Draft/Unmerged؛ main،PR33،Merge،ForcePush،Release،EXE،P6-6 و فاز۷ دست‌نخورده. A2 تجاری،گیت‌هایE4/E6فاقدقرارداد وUATمالک مستقل باقی‌اند.
