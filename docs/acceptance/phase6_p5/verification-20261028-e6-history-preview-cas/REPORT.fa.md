# فاز ۶ | P6-5 | E6: محافظ CAS در پیش‌نمایش تاریخچه مالکیت IFC

**وضعیت این نقص محدود: تأییدشده با RED/GREEN واقعی دو‌سیستمی.**

## منشأ نقص و قرارداد اصلی
- فایل `app/ifc_lineage_controls.py` در `history_preview`، ابتدا `service.open_project(pid)` را فراخوانی می‌کرد و سپس برای محاسبه واگرد، **Digest جاری پس از خواندن** را به `expected_digest` می‌داد. اگر رکورد هنگام خواندن با SQLite واقعی تغییر می‌کرد، Snapshot قبلی با CAS تازه به مسیر پیش‌نمایش می‌رفت.
- همچنین تأیید قبلی بازبین و ردیف‌های قدیمی Preview قبل از شروع بازخوانی تازه ابطال نمی‌شدند. این مسئله مجوز مالی یا سهم مهندسی تازه نمی‌سازد، ولی **نمایش موفقیت کاذب برای Snapshot منقضی‌شده** ایجاد می‌کند.
- قرارداد canonical موجود در `core/takeoff/manual_formula_amendments.py` شامل `ifc_transfer_step_payload` و `assert_unchanged` است. اصلاح روی رابط کاربری و پیش از ساخت آرگومان‌ها انجام شد؛ engine و دفتر اصلی ویرایش نشده‌اند.

## RED واقعی روی نسخه قبل از اصلاح
- [CI RED شماره 40760620857](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40760620857)، source tests `aae52eb52292886295591e584b96a66dcb54881f` و workflow `60ba0e6eb8a732ebc654fcd643a6236ab0d5b787`.
- **Linux: ۳۸ PASS، ۲ FAIL**. **Windows: ۳۸ PASS، ۲ FAIL**؛ در هر دو مورد، متن اشتباه `عملیات گروهی انجام شد` پس از تغییر واقعی SQLite دیده شد. دو سناریو: بدون Preview قبلی و پس از Preview و تأیید صریح قبلی.
- [Artifact RED Linux #12848336229](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40760620857/artifacts/12848336229) و [Artifact RED Windows #12847543960](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40760620857/artifacts/12847543960). شکست‌ها حذف، Skip یا XFAIL نشده‌اند.

## اصلاح حداقلی
- [Commit اصلاح `4e6fdc26c4da545e29608f4c121f73e856aedc04`](https://github.com/Asanda021/StructuralPro-Recovery/commit/4e6fdc26c4da545e29608f4c121f73e856aedc04) فقط `app/ifc_lineage_controls.py` را تغییر می‌دهد.
- بلافاصله هنگام درخواست history_preview، `state`، checkbox تأیید و جدول پیش‌نمایش قبلی باطل می‌شوند.
- `token=service.store.current_digest(pid)` **پیش از** `service.open_project(pid)` خوانده می‌شود؛ پس از خواندن Snapshot دوباره همان Digest تأیید می‌شود. تغییر SQLite با پیام فارسی fail-closed از تولید Preview موفق جلوگیری می‌کند.
- همان `token` به `expected_digest` در تابع Preview اصلی انتقال می‌یابد؛ Snapshot قبلی با توکن جدید جایگزین نمی‌شود.
- هیچ مقدار، مالکیت، فرمول، قرارداد تقسیم سهم، BOQ، قیمت، منبع IFC یا Revision مهندسی تغییر نکرده است.

## GREEN واقعی بر source اصلاح‌شده
- [CI GREEN شماره 40760971622](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40760971622) روی workflow commit `93899f14f32297d3569d886d5a22cd2726b90746` و checkout pinned `4e6fdc26c4da545e29608f4c121f73e856aedc04`: هر دو job `completed/success`.
- **Linux: ۴۰ PASS، صفر FAIL/ERROR/SKIP** در ۴۸٫۶۳ ثانیه؛ [JUnit #12848680540](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40760971622/artifacts/12848680540).
- **Windows 2022 Qt native: ۴۰ PASS، صفر FAIL/ERROR/SKIP** در ۱۳۱٫۸۹ ثانیه؛ [JUnit #12848052922](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40760971622/artifacts/12848052922).
- دو مورد جدید همان پرونده RED قبلی هستند؛ ۴۰ testcase در هر OS تکرار می‌شوند و ۸۰ سناریوی مستقل محسوب نمی‌شوند. هیچ assertion حذف یا timeout افزایش داده نشد.

## گیت‌های مستقل و محدودیت
- [پذیرش جامع P6-5 #40760971671](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40760971671) روی Source جدید اجرا شده؛ در زمان ثبت، **Linux موفق و Windows در حال اجرا** است. فهرست اصلی workflow شامل ۵۱۵ testcase پیشین است و دو تست تازه این فایل در گیت تخصصی E6 به‌صورت مستقل اجرا شده‌اند؛ نباید ۵۱۵ قبلی را شامل این دو مورد دانست.
- علت SIGSEGV قبلی Linux با اجرای GDB [#40756726986](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40756726986) **بازتولید نشد**؛ `ROOT CAUSE UNDETERMINED` و شواهد شکست قدیمی محفوظ.
- E6 از نظر اشتراک فیزیکی واقعی بتن/میلگرد/پوشش، هندسه و inverse Crosswalk فاقد قرارداد مستقل مهندسی در موارد خاص هنوز **PARTIAL/BLOCKED** است. E4 مقصدهای بدون provenance، W1، A2 تجاری و UAT فیزیکی نیز بسته نشده‌اند.
- PR #33 و PR #34 باز، Draft، ادغام‌نشده؛ `main=9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` ثابت. هیچ Merge، Rebase، Force Push، Release، EXE، شروع P6-6 یا فاز ۷ انجام نشده است.

## خلاصه وضعیت پروژه و این چت
مورد خاص E6 تاریخچه و CAS پس از RED دو‌سیستمی و GREEN دو‌سیستمی **بسته شد**؛ پذیرش سراسری P6-5 همچنان PARTIAL، نقشه راه دقیقاً ۸ فاز و پیشرفت ثبت‌شده ۸۵٪ بدون تغییر است.
