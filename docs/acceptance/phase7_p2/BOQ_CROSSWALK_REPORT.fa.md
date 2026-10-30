# StructuralPro | فاز ۷، اولویت ۲ | اتصال مستند نقشه دوبعدی به ریزمتره و BOQ

**۳۱ اکتبر ۲۰۲۶** | [PR #36](https://github.com/Asanda021/StructuralPro-Recovery/pull/36) | **PARTIAL**، بدون ادعای تأیید تمام اولویت ۲

## تحویل عملی

تابع فقط‌خواندنی `link_source_backed_2d_overlay_to_boq(...)` در همان `core/reports/source_backed_2d_overlay.py` قرار گرفت. این تابع از Snapshot واقعی `StructuralProApp.open_project`، نسخه `_meta.version`، نسخه نشست `drawing_sessions[].revision`، برداشت ثبت‌شده در `takeoffs` و ردیف واقعی `boq` استفاده می‌کند. مجوز ساخت مقدار، بازنویسی BOQ، تغییر نرخ یا امضای مهندسی ندارد.

- از `session_to_boq_rows` و `verified_measurement_identities` موجود برای تطبیق صفحه، SHA-256 فایل PDF/CAD، هندسه دارای کالیبراسیون و `measurement_identity` استفاده می‌شود.
- هر عضو و طبقه باید در ProjectStore ثبت شده باشد. هویت برداشت در دو رسید `params` و `provenance`، فرمول/واحد/مقدار ریزمتره و BOQ و منبع `drawing:{session_id}:{takeoff_id}` باید برابر باشند.
- فقط BOQ با دقیقاً **یک** منبع قابل اتصال است؛ برای BOQ تجمیعی خروجی نقشه‌دار مسدود می‌شود، نه اینکه مقدار کل BOQ به یک عضو نسبت داده شود.
- شناسه خروجی ردیف `boq-item-no:N` فقط در `project_version` همان Snapshot معتبر است؛ در Revision یا Reaggregation جدید دوباره بررسی لازم است.
- `boq_row_id` در Overlay اولیه NULL باقی می‌ماند و فقط پس از این تطبیق، مرجع نسخه‌دار نمایش داده می‌شود. `quantity_authority=false` و `financial_mutation=false` همواره ثابت است.
- `revision` ورودی گزارش برچسب ارائه است، نه امضای تأیید نقشه توسط مهندس. `session_revision` و `project_version` جدا ثبت می‌شوند.
- Snapshot باید **همان نسخه جاری** تحویلی ProjectStore باشد. خود تابع نسبت به تغییر هم‌زمان دیتابیس پس از دریافت Snapshot آگاهی مستقل ندارد؛ سیستم صادرکننده نهایی باید همان نسخه را پیش از انتشار دوباره بررسی کند.

## آزمون‌های منفی و مثبت

آزمون `tests/test_phase7_p2_persisted_boq_crosswalk.py` از پایگاه SQLite واقعی در Fixture موجود و PDF برداری استفاده می‌کند. حالات شامل ثبت/بازخوانی واقعی، یکتایی منبع، حفظ digest دیتابیس، دستکاری مقدار BOQ، منبع، نسخه، نوع مصالح، هندسه، شناسه، Receipt، ثبت‌نشدن، BOQ تجمیعی، نسخه قدیمی، شناسه عضو/طبقه مغایر و آزمون عدم‌تغییر داده است.

- [اجرای اولیه #41129804958](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41129804958): Linux **۱۰۳ PASS، ۱ FAIL**، علت صرفاً مقایسه Python `"16" == 16` در assertion، نه اختلاف عددی BOQ. Windows همان Commit نیز Failure شد. هیچ آزمونی حذف/Skip نشد.
- اصلاح Assertion به مقایسه `Decimal("16") == Decimal(str(16))` در Commit `7fe9aa5360df20a0ea27b73a056b06bbbe811e6b`.
- [اجرای اصلاح‌شده #41129993313](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41129993313): Linux **۱۰۴ PASS، صفر FAIL/ERROR/SKIP**، یک هشدار `fitz` قدیمی. **Windows تا تکمیل گزارش CI هنوز PENDING است**.

## وضعیت و گیت

`P7_P2_PERSISTED_B0Q_CROSSWALK = IMPLEMENTED`؛ `LINUX_TARGETED=PASS`، `WINDOWS_TARGETED=PENDING`، `P7_P2_ALL_ACCEPTANCE=OPEN`.

باقیمانده فاز۷، اولویت۲ مطابق نقشه‌راه مصوب: خروجی واقعی PDF/XLSX/DOCX دارای نقشه و CSV+SVG sidecar، صفحه‌بندی و نمای چندطبقه، آزمون Golden پنج‌طبقه، کیفیت چاپ/فونت، و تطبیق مستقل داده‌ها. این‌ها فاز جدید نیستند. آزمایش واقعی Windows/Office/چاپ و G4 فاز۶ طبق تصمیم مالک در فاز۸ تعیین تکلیف می‌شوند. هیچ Merge/main/EXE/Release انجام نشده است.
