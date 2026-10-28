## پذیرش گیت امنیتی E4: منبع IFC پیوندی، ۲۸ اکتبر

اصلاح کد/تست `76969a29d29588b4b0a1b1cbf43a81a319958fdf` فقط روی PR #34: مسیر تأییدشده IFC در `reviewed_member_source` برای symlink خود فایل و پوشه‌های والد به‌صورت fail-closed مسدود شد؛ دو آزمون منفی با شبیه‌سازی دقیق `Path.is_symlink` اضافه شدند، بدون نوشتن در BOQ. [CI مستقل #40654824158](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40654824158) روی **همین SHA** با نتیجه `completed/success` برای Linux offscreen و Windows native تأیید شد. هر محیط: **۴۶۸ PASS اصلی + ۱۳۰ تاریخی + ۲۶ امنیتی + ۸ DPI ۱۵۰٪ + ۸ DPI ۲۰۰٪**؛ در هر بسته صفر FAIL/ERROR/SKIP، یک هشدار `fitz` در بسته اصلی. DPI تکرار همان آزمون‌های Dock است؛ نباید تعداد بسته‌ها را تعداد سناریوی یکتا نامید. گزارش JUnit و هش‌ها در [پرونده گیت](verification-20261028-e4-ifc-link-guard/REPORT.fa.md) و Artifacts اجرا ثبت‌اند. **E4 در کل PARTIAL**، مسیرهای DWG و IFC تخصصی فاقد قرارداد همچنان BLOCKED، رگرسیون گسترده ۸۳۷۵تایی روی این SHA اجرا نشده، UAT فیزیکی Windows انجام نشده است. PR33/34 Draft/Unmerged، main بدون تغییر، هشت فاز و ۸۵٪ ثابت. Commit مستندات بعدی اجرای جدید کد محسوب نمی‌شود.

# نقطه ادامه معتبر — ۲۸ اکتبر ۲۰۲۶

## پذیرش E4: مسیر سند عمومی، ۲۸ اکتبر

روی PR #34 اصلاح اجرایی `caadb784dd199bdeceb6d3b2ab5b180bb2a8bba1` با محدودسازی مسیر سند عمومی به PDF/DXF و رد صریح DWG/IFC فاقد قرارداد مستقل ثبت شد. [CI موفق #40652984455](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40652984455) پس از اصلاح بودجه زمانی روی `2eb95e88f034558674591b26b7c35ccd4647ce03` برای **Linux و Windows هرکدام ۴۶۶ PASS اصلی، ۱۳۰ تاریخی، ۲۶ امنیتی و ۸+۸ DPI؛ صفر FAIL/ERROR/SKIP** ثبت کرد؛ یک هشدار fitz در بسته اصلی هر سیستم. [CI قبلی #40651721016](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40651721016) در Windows در سقف ۴۸۰ثانیه JUnit اصلی نداشت و FAIL ماند، نه PASS. [گزارش E4](verification-20261028-e4-safe-routing/REPORT.fa.md). E4 در کل **PARTIAL** است و DWG/IFC specialist بدون قرارداد، مالکیت مشترک E6، A2 و UAT فیزیکی همچنان مسدودند. تست گسترده ۸۳۷۵تایی روی کد قدیمی `7cbeac9b` بوده و نباید به SHA جدید نسبت داده شود. هشت فاز، ۸۵٪ و وضعیت Draft/Unmerged ثابت.

## وضعیت جدید رگرسیون گسترده (تأییدشده در GitHub Actions #40648107800)

**مبنای جاری بر گزارش‌های قدیمی پایین ارجح است:** کد `7cbeac9b245586bf83922bc4dbf2783de56214ad` روی Linux با `۸۳۷۰ PASS / ۰ FAIL / ۰ ERROR / ۵ SKIP` از `۸۳۷۵` تست جاری، `exit=0` و `timed_out=false` پذیرفته شد. دو شکست baseline تاریخ ۲۷ اکتبر (Shell و فونت) در همین چت اصلاح و در CI اختصاصی Linux/Windows نیز تأیید شدند. **پنج آزمون SKIP مختص Windows در CI #40651198197 به‌صورت هدفمند هر پنج PASS شدند؛** رگرسیون کامل Windows هنوز اجرا نشده؛ نتیجه قبلی `۸۳۵۱ PASS / ۲ FAIL` فقط شاهد snapshot قدیمی است. مرجع جدید: [گزارش رگرسیون ۲۸ اکتبر](verification-20261028-broad-recheck/RESULT.fa.md) و [CI موفق](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40648107800). مستندات پس از SHA آزموده‌شده تغییر می‌کنند و نباید با اجرای مجدد کد اشتباه شوند. سایر گیت‌های تخصصی، A2 و UAT انسانی همچنان `PARTIAL/BLOCKED`، وضعیت ۸۵٪ و ۸ فاز ثابت.

محدوده فقط P6-4/P6-5 فاز۶؛ نقشه‌راه دقیقاً۸فاز و پیشرفت ثبت‌شده۸۵٪ ثابت. این فایل checkpointهای قدیمی را برای ادامه کار جایگزین می‌کند؛ تاریخچه در Git و گزارش‌های پذیرش قبلی محفوظ است.

## کد واقعی

- PR33: کد/تست `04e2e61151013a09f31e92aa943978b5de8bf188`؛ Tree `dc7078d441dd0d9e231ebc0d6f1c005178aee29f`؛ [CI40616456506](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40616456506). آخرین HEAD شواهد را از PR بخوانید؛ پس از این کد فقط مستندات تغییر می‌کنند.
- PR34: کد/تست/CI `ed0e28acc2fd4f3e2f22f674755a8f94ad9b4732`؛ Tree `2d5be7e281f7e1c4bf74412b4877383b6994ed87`؛ [CI40616837797](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40616837797). آخرین HEAD مستندات مستقل است.
- اجرای گسترده رسمی از کد `005a55f8eb757e544af79b31e1329369aeb845e0` است:۸۳۵۱PASS،۲FAIL قدیمی،۰ERROR،۱۰SKIP بومی Windows/PowerShell،۳warning،exit۱،بدونtimeout. کل مجموعه سبز نیست. محصول app/core/scripts/workflow در کد نهاییed0e28a دقیقاً همان است؛ فقط۱۲آزمون IFC اضافه و مستقلاً در package/CI اجرا شده‌اند. این۱۲در broadJUnit قبلی شمرده نشده‌اند. Collection نهایی۸۵۰۵،صفرerror؛ source-SHA256SUMS و final-source.json تطبیق را ثبت می‌کنند.
- main باید `9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` باقی بماند. PR33/34 باز و Draft و Unmerged؛ هیچ Merge/ForcePush/Release/EXE/P6-6/فاز۷ مجاز یا انجام‌شده نیست.

## کارهای انجام‌شده را تکرار نکنید

۱. E6 همان API Split/Merge و IFC_TRANSFER موجود را گسترش می‌دهد: رویداد append-only Undo/Redo، CAS/group_revision، همان بازبین مستقل و نقش مجاز زنده، ردیف قبل/بعد، منشأ، تراکنش واقعی و Reopen. Oracle طول۶=۲+۴، سطح۱٫۸، حجم۰٫۳۶ در Split/Merge؛ ۱/۵/۲۰ گروه مستقل و آزمون قدیمی۲۰عضو دو پوشش متفاوت‌اند. guard مستقیم Store و تغییر context Qt بسته شده‌اند. inverse Crosswalk مهاجرت‌کرده و migration هنگام undone بودن انتقال عمداً رد می‌شوند.

۲. W1 همه mutationهای سقف/معماری و نوع خانواده و post-Yes Delete را guard می‌کند. Beam Preview طبق قرارداد Draft ذخیره می‌کند؛ بعد از ذخیره مشروع خودش به guard منقضی بازنمی‌گردد. Commit فقط برای Draft دقیقاً یکسان از ذخیره ضمنی مجدد عبور می‌کند. IFC مصنوعی معتبر Beam/Column با GlobalId/SHA/Revision و اصل فرم و SQLite تست شده؛ solid_slab/IfcSlab و block_wall/IfcWall با review و refresh صریح crossview و commit و۱۲حالت منفی IFC واقعی Save/Review/Commit پس از تغییر bytes/Revision آزموده شده‌اند. متره دستی fixture را استخراج هندسی IFC یا ساختمان واقعی ننامید.

۳. E4 نشست canonical PDF/DXF را با ID/Revision/SHA/صفحه/آیتم‌های واقعی در Viewer اصلی باز می‌کند؛ DXF با واحد مستند و Find Handle واقعی آزموده شده. مقصد عمومی بدون قرارداد تخصصی به editor ساختگی تبدیل نشده است.

۴. QA،۱۵خطای collection را با stage امن جدا می‌کند، نه حذف guard. تعداد۱۹۳YAML و bytes/manifest اولیه ثابت؛ هیچ workflow تاریخی اجرا نشده. historical مستقل۱۳۰آزمون دارد. runner لاگ زنده و JUnit واقعی را نگه می‌دارد؛ timeout/interruption،PASS یا XML ساختگی نیست. دو آزمون bulk قدیمی اکنون Yes بومی را واقعاً کلیک می‌کنند و Oracle اصلی را حفظ کرده‌اند. handoff فقط modal فعال واقعی را می‌بندد، نه پنجره مخفی قبلی.

## موارد باز واقعی

- E6: inverse بازبینی‌شده Crosswalk؛ مالکیت مشترک چند عضو/میلگرد/پوشش و چند وابستگی متقاطع بدون سند سهم معتبر BLOCKED. نسبت و مقدار نسازید.
- W1: IFC MEP فاقد نگاشت مهندسی؛ دیگر زیرگونه‌ها، تمام مسیرها و نقشه مالک NOT VERIFIED. پشتیبانی generic parser مجوز انتقال مهندسی نیست.
- E4: handoff مستقیم Beam/Column/MEP/سقف/معماری از نتیجه عمومی جست‌وجو، DWG با منشأ تبدیل و اسناد/گزارش فاقد قرارداد هویت هنوز BLOCKED/read-only.
- QA گسترده: دو شکست مستقل روی baseline4bdb نیز بازتولید شده‌اند: انتظار قدیمی نبود هر QTreeWidget در Shell، و raw font Noto Sans Arabic بدون حروف لاتین. آن‌ها حذف/Skip/سبز نشده‌اند؛ [BASELINE-FAILURES.fa.md](verification-20261027-three-gates/BASELINE-FAILURES.fa.md). نتیجه نهایی broad:۸۳۵۱PASS/۲FAIL/۰ERROR/۱۰SKIP است؛ هیچ FAIL/SKIP حذف یا PASS نشده است.
- Windows فیزیکی: دو‌مانیتور، Sleep/Resume، GPU/درایور مشتری و تأیید مهندسی مالک NOT VERIFIED؛ [چک‌لیست](verification-20261027-three-gates/WINDOWS_UAT.fa.md).
- A2 تجاری بدون وزن/Runtime/منشأ/مجوز معتبر BLOCKED؛ دانلود مدل انجام نشد.

## مرجع ادامه و شواهد

[گزارش فارسی جاری](verification-20261027-three-gates/REPORT.fa.md)، ci-measured.json، current-active-modal.json/XML، historical-final.xml، پوشه qa و SHA256SUMS مبنا هستند. نتایج incomplete قبلی را با اجرای نهایی جمع نزنید؛ تکرار DPI همان۸تست است. ادامه باید از آخرین HEAD زنده PR آغاز شود و کد/Tree هر نتیجه دقیقاً تطبیق داده شود. تغییر اسناد پس از SHA آزموده‌شده نباید به‌عنوان اجرای مجدد کد معرفی شود.

## آخرین پذیرش مستقل

PR33 کد04e2e61 در CI40616456506 روی Linux/Windows هرکدام۲۵۷PASS و صفرFAIL/ERROR/SKIP،۱warningfitz. PR34 نتیجه آخرین CI40616837797 را از ci-measured.json همین snapshot بخوانید؛ هر مرحله و سیستم مستقل است. تاریخی۱۳۰ و security۲۶ و DPI۱٫۵/۲ هرکدام۸تکرارند؛ اعداد تکراری را جمع سناریوهای یکتا ننامید. گزارش فارسی و چک‌لیست Windows به همین SHAها به‌روز هستند.

نتیجه قطعی CI40616837797 رویed0e28a:SUCCESS هر دو سیستم؛ هرکدام۴۶۱اصلی +۱۳۰تاریخی +۲۶security +۸DPI۱۵۰٪ +۸DPI۲۰۰٪،۰FAIL/ERROR/SKIP؛۱warningاصلیfitz و۰درمرحله‌های دیگر. این نتیجه کل broad را سبز نمی‌کند؛ broad۸۳۵۱/۲/۰/۱۰ و۳warning باقی است.
