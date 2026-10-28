# P6-5 | E4: محافظ نسخه زنده در ناوبری واقعی Qt

**تاریخ:** ۲۸ اکتبر ۲۰۲۶ | **مخزن:** `Asanda021/StructuralPro-Recovery` | **شاخه:** `feature/phase6-p5-workspace-e3-e6-20261027` | **PR:** #34 Draft/Open/Unmerged

## مبنای نقص و قرارداد
- اسناد پایه E4: `docs/acceptance/phase6_p5/verification-20261027-three-gates/e4/REPORT.md` و `docs/acceptance/phase6_p5/verification-20261027-three-gates/REPORT.fa.md`؛ پروژه باید با هویت ثبت‌شده، SHA/Revision و نسخه جاری SQLite بازبینی شود. هیچ ناوبری نباید از Snapshot منقضی‌شده رکورد به مقصد برسد.
- در کد قبلی `app/project_search_panel.py`، `run_search` نسخه را **بعد از** گرفتن snapshot پروژه می‌خواند؛ جهش در زمان ساخت نتیجه می‌توانست snapshot قدیمی را با digest جدید جفت کند.
- `open_record` پیش از خواندن مجدد snapshot نسخه را کنترل می‌کرد، اما بعد از `search_project` و قبل از اجرای `on_navigate` کنترل دوباره نداشت. اگر تغییر پروژه نام/داده رکورد انتخابی را عوض نکند، شرط equality همچنان مثبت می‌شود و مقصد stale فراخوانی می‌گردد.
- `open_model` پس از تأیید `open_record(navigate=False)` نیز تا callback تخصصی IFC گیت مجدد نداشت؛ مسیرهای رابط می‌توانند در همین فاصله منقضی شوند.

## اصلاح پیاده‌سازی و تست
- **Commit کد و تست:** [`c10b9291cb443431287d656fcf00c4b26e71e196`](https://github.com/Asanda021/StructuralPro-Recovery/commit/c10b9291cb443431287d656fcf00c4b26e71e196). فقط فایل‌های `app/project_search_panel.py` و `tests/test_phase6_p5_e4_snapshot_race.py`.
- `run_search`: Digest پیش از `open_project` ثبت می‌شود و پس از `search_project` دوباره کنترل می‌شود. تغییر بین خواندن و انتشار نتایج **fail-closed** است.
- `open_record`: پس از re-search و قبل از ساخت نمایش رکورد/ناوبری، Digest دوباره کنترل می‌شود؛ در mismatch انتخاب پاک و callback فراخوانی نمی‌شود.
- `open_model`: بلافاصله قبل از ارسال شناسه به `on_open_model`، Digest با snapshot معتبر مقایسه می‌شود. در mismatch مدل باز نشده و پیام فارسی خطا ثبت می‌شود.
- سه آزمون Qt با SQLite واقعی، بدون Fake Model و بدون تغییر مالی: تغییر وسط `search_project`، تغییر پس از پیدا شدن همان رکورد حین کلیک، و تغییر بعد از `open_record` ولی پیش از callback IFC. هر سه از `add_project_floor` واقعی برای ایجاد تغییر نسخه استفاده می‌کنند؛ آزمون‌ها تأیید می‌کنند callback stale اجرا نشود و BOQ دست‌نخورده بماند.
- هیچ گیت DWG/IFC provenance دور زده نشده، هندسه/مقدار/قیمت ساخته نشده، SKIP/XFAIL یا خاموش‌کردن تست وجود ندارد.

## آزمون و CI
- **Workflow:** [`8138fe730819db694df4fdd3146e4f994a3d4a81`](https://github.com/Asanda021/StructuralPro-Recovery/commit/8138fe730819db694df4fdd3146e4f994a3d4a81) در `.github/workflows/phase6-p5-e4-cas-navigation.yml`، checkout کد را روی `c10b9291cb443431287d656fcf00c4b26e71e196` قفل می‌کند و نیت اجرای Windows Server 2022 Qt native و Ubuntu 24.04 Qt offscreen را دارد.
- [CI هدفمند E4 #40705393682](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40705393682): در لحظه تهیه گزارش **in_progress**؛ مجموعه E4 snapshot + search + UI + drawing sessions، JUnit و artifact جدا برای هر OS. این گزارش قبل از دریافت نتیجه **PASS ادعا نمی‌کند**.
- [CI پذیرش وسیع P6-5 #40705265304](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40705265304): در حال اجرا، پوشش E3–E6/تاریخی/امنیت/DPI. نتیجه کل بسته مستقل از گیت هدفمند است.
- **مرجع CI گسترده پیش از این تغییر**: [#40683854260](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40683854260)، کامل و success روی source `48a85f5d7ae4a88fe8f092a7e0c27be792bf9b9d`: Linux ۸۳۹۵ PASS و ۵ SKIP؛ Windows سه shard با مجموع ۸۳۹۳ PASS و ۷ SKIP؛ ۰ FAIL، Union تمام ۸۴۰۰ case / ۷۰۳ ماژول بدون کمبود یا تکرار. این پوشش را **به SHA جدید تعمیم نمی‌دهیم**.

## گیت‌های باقیمانده
- E4 گیت‌های تخصصی فاقد منشأ DWG conversion و مقصدهای تخصصی Beam/Column/MEP/Roof/report همچنان BLOCKED، مگر قرارداد هویت واقعی فراهم گردد.
- E6 مالکیت مشترک چندعضوی و Crosswalk معکوس بدون قرارداد مهندسی واقعی، W1/IFC MEP و A2 مدل تجاری واقعی، همچنان PARTIAL/BLOCKED.
- P6-6 هنوز شروع نشده. UAT فیزیکی Windows/چندمانیتور متعلق به گیت مستقل خود است.
- **محافظت مخزن:** PR #33 و PR #34 Draft/Open/Unmerged، `main` در زمان پیش‌ثبت `9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95`؛ بدون Merge، Force Push، EXE، Release، تغییر فازهای ثابت ۸گانه یا درصد ثبت‌شده ۸۵٪.

**وضعیت این چت:** نقص CAS/TOCTOU واقعی ناوبری بررسی و اصلاح شد، سه آزمون واقعی افزوده و دو CI به‌طور مستقل راه افتاده‌اند؛ پذیرش نهایی در انتظار شواهد اجرایی همان source است.
