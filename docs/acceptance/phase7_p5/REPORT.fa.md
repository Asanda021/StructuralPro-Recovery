# StructuralPro | فاز ۷، اولویت ۵ (E8) | آغاز کنترل مغایرت مستند منابع

**۳۱ اکتبر ۲۰۲۶** | [Draft PR #39](https://github.com/Asanda021/StructuralPro-Recovery/pull/39)

## پیش‌شرط بسته‌شده
اولویت ۴ در PR #38 با کد آزموده‌شده `0cdee9f8a7e1dec70e4da818b27d307d38c014b4`، [CI هدفمند #41173776051](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41173776051) و [رگرسیون جامع #41173776017](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41173776017) تأیید فنی خودکار گرفت. Linux ۸۶۱۴ PASS/۵ SKIP، Windows ۸۶۱۲ PASS/۷ SKIP؛ ۷/۷ Job سبز، ۸۶۱۹ تست یکتا در ۷۳۴ ماژول. G4 واقعی و Office/چاپ فاز۸ هنوز NOT_TESTED.

## نخستین تحویل محدود E8
`core/reports/source_discrepancy_gate.py`:
- پیش‌ارزیابی فقط‌خواندنی ناحیه‌های دارای **هندسه و منشأ PDF/CAD واقعی** از یک نشست SQLite ذخیره‌شده اما هنوز منتقل‌نشده به BOQ.
- استفاده مستقیم از `session_to_boq_rows`، `verified_measurement_identities` و `custom_batch._source_rows` برای تطبیق SHA واقعی، کالیبراسیون، مورد انتخاب‌شده، هویت عضو و طبقه، کد عملیات و واحد، منبع و BOQ اصلی؛ بدون موتور هندسه یا قیمت دوم.
- وقتی عضو/طبقه/کد/واحد در دو منبع مستقلاً مستند تکرار شود: اگر کمیت یکسان باشد `POTENTIAL_DUPLICATE_MEMBER_SOURCE` و اگر متفاوت باشد `MEMBER_SOURCE_QUANTITY_DISCREPANCY`. هر دو حالت نیاز به **بازبینی مستقل مهندس** دارند. این تنها «احتمال تعارض» است، نه اثبات هندسه تکراری یا تغییر طراحی.
- در صورت تعارض، گیت `require_no_pending_source_discrepancies` به‌صورت Fail-Closed رد می‌کند. حتی با نبود تعارض، `final_commit_authority=false` و `approved_for_engineering_release=false` باقی می‌ماند؛ ثبت واقعی تابع کنترل اصلی BOQ و تأیید مالک است.
- تغییر SHA، نسخه کهنه، نشست ناموجود/غیرمعتبر، برداشت تکراری/قبلاً ثبت‌شده، ناقص‌بودن مدرک هندسه و تغییر هم‌زمان پروژه همگی رد می‌شوند؛ کنترل SHA هنگام پایان نیز تکرار می‌شود.
- هنوز این گیت به تمام مسیرهای ثبت قطعی BOQ، IFC و تشخیص هندسه مرزی چندرشته‌ای متصل نیست؛ **اولویت ۵ کل: PARTIAL**.

## آزمون واقعی و RED/GREEN
`tests/test_phase7_p5_source_discrepancy_gate.py` با PDF برداری مصنوعیِ صریح و نشست‌های **واقعاً ذخیره‌شده در SQLite** مقدار برابر، مقدار متفاوت، دو عضو مستقل، نسخه قدیمی، منبع مخدوش و شناسه نامعتبر را بررسی می‌کند.
- [اجرای اولیه #41181455558](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41181455558): Linux **۹۰ PASS / ۱ FAIL**؛ خطا فقط عبارت regex آزمون (`بازبینی`) نسبت به متن واقعی پیام بازبینی مهندس بود. رفتار fail-closed کد در این خطا درست عمل کرده است. این اجرا به‌عنوان PASS نهایی حساب نشود.
- اصلاح متن آزمون در Commit `8a1718923af49446ce2ddc31b0a441f6e64901d6`؛ CI Windows/Linux تازه پس از اعمال آن باید سنجیده شود. هیچ آزمونی حذف/Skip نشده است.
- `P7_P5_INITIAL_SCOPE=IMPLEMENTED`، `P7_P5_LATEST_CI=PENDING` تا اتمام دو Job روی SHA جدید. رگرسیون جامع و پذیرش کل اولویت۵ انجام نشده است.

## خلاصه وضعیت پروژه و همین چت
- فازهای ۱ تا ۵: سوابق فنی محفوظ. فاز ۶: تحویل فنی خودکار؛ پذیرش فیزیکی در فاز۸ معوق.
- فاز ۷: اولویت‌های ۱ تا ۴ پذیرش فنی خودکار؛ **اولویت ۵ آغاز و در حال آزمون**؛ اولویت ۶ هنوز آغاز نشده.
- فاز ۸: آزمون نهایی و تأیید مالک هنوز آغاز نشده.
- ۸ فاز اصلی و ۶ اولویت مصوب فاز۷ ثابت؛ پیشرفت رسمی کل نرم‌افزار ۸۵٪ بدون تغییر.
- PRهای اخیر همگی Draft/Open/Unmerged، بدون Merge، main، ForcePush، EXE و Release.


## نتیجه اجرای اصلاح‌شده E8 بر SHA آزموده‌شده

- [CI #41181550663](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41181550663) روی Commit `8a1718923af49446ce2ddc31b0a441f6e64901d6`: Linux **۹۱ PASS، صفر FAIL/ERROR/SKIP**، یک هشدار قدیمی fitz. Windows **PENDING** تا تأیید مستقل نتیجه Job. هیچ PASS فرضی ثبت نشود.
- آزمون‌ها ۹۱ مورد شامل منشأ واقعی PDF/SQLite، تشخیص احتمال دوباره‌شماری عضو، اختلاف مقدار، عدم جعل تأیید، مغایرت SHA/Revision و قراردادهای قبلی هستند.
- `P7_P5_INITIAL_SCOPED_CI=LINUX_PASS_WINDOWS_PENDING` و `P7_P5_OVERALL=PARTIAL`. پیش از اجازه هر مسیر commit واقعی، E8 باید داخل همان گیت اصلی پیوند داده و CI جامع جداگانه انجام شود.


## نتیجه نهایی آزمون هدفمند بر کد E8

[CI #41181550663](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41181550663)، دقیقاً روی Commit `8a1718923af49446ce2ddc31b0a441f6e64901d6`: **Linux ۹۱ PASS، Windows Native ۹۱ PASS**؛ هر دو Job SUCCESS؛ صفر FAIL/ERROR/SKIP، یک هشدار قدیمی fitz در هر سیستم. هیچ آزمون حذف یا Skip نشده است.

**حکم فنی محدوده فعلی:** `P7_P5_SOURCE_PREFLIGHT_TARGETED=ACCEPTED`. اما `P7_P5_OVERALL=PARTIAL` زیرا اتصال اجباری به تمام نقاط واقعی ثبت متره و BOQ و پوشش IFC/Revision چندمنبعی و CI جامع کد P5 باقی‌اند. موفقیت Preflight هرگز مجوز ثبت نهایی یا تأیید مهندسی نیست. آزمایش Office/Windows سخت‌افزاری همچنان فاز۸ و NOT_TESTED است.


## اتصال اجباری به مسیرهای واقعی ثبت BOQ و گیت هدفمند نهایی

- کد `core/platform/application.py` اکنون قبل از `validate_commit_rows`، `rebuild_project_boq` و `store.save` از کنترل E8 برای **برداشت area دارای مدرک هندسی** در هر دو تابع `commit_drawing_takeoff_to_boq` و `commit_ai_takeoff_proposal` استفاده می‌کند. کنترل‌های موجود `assert_new_measurements` برای هندسه تکراری، هم‌پوشانی، مالکیت مقدار و CAD حذف یا دور زده نشده‌اند.
- آزمون‌های `tests/test_phase7_p5_real_commit_integration.py` با PDF برداری مصنوعی، نشست واقعی SQLite و دو عضو حقیقی ProjectStore اجرا شدند. موارد مسدودی، عدم‌تغییر digest، ثبت مجاز یک عضو مستقل با حفظ هر دو `source_id` حتی در BOQ تجمیعی، و عدم عبور تأیید صریح AI از کنترل اختلاف را پوشش می‌دهند.
- [CI هدفمند #41182121023](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41182121023) روی **SHA دقیق `1c558d282e243761323911fbf2f35ed7c5b36129`**: Linux **۹۷ PASS**، Windows Native **۹۷ PASS**؛ هر دو Job موفق؛ صفر FAIL/ERROR/SKIP؛ یک هشدار قبلی fitz در هر سیستم.
- [رگرسیون جامع همان SHA #41182123771](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41182123771): هنگام نگارش این سند **PENDING**؛ پذیرش کامل P5 منوط به اتمام موفق تمام Jobها، union و تعیین تکلیف شکاف‌های IFC/AI/Revision چندمنبعی است.
- `P7_P5_REAL_MANUAL_AI_B0Q_TARGETED=ACCEPTED`؛ `P7_P5_BROAD=PENDING`؛ `P7_P5_OVERALL=PARTIAL`. عبور گیت به معنای تأیید مهندسی یا اجازه خودکار پرداخت نیست.

### تصحیح وضعیت پیشرفت و فاز ۶
فاز ۶ در دامنه توسعه و CI خودکار **COMPLETE / 100%** است؛ فقط آزمون حضوری Windows/G4 طبق تصمیم مالک به فاز ۸ منتقل شده، نه اینکه فاز ۶ دوباره باز شده باشد. با وزن برابر هشت فاز و شش اولویت در فاز۷ و با شمارش فقط گیت‌های کاملاً پذیرفته‌شده، پیشرفت فعلی **۸۳٫۳٪** است. جدول دقیق و نسبت با رقم تخمینی قدیمی ۸۵٪ در [سند روش محاسبه](../PROJECT_PROGRESS_METHOD_20261031.fa.md) ثبت شده؛ درصد بدون دلیل افزایش نمی‌یابد.


## تصمیم نهایی گیت اولویت ۵ | ۳۱ اکتبر ۲۰۲۶

**کد آزموده‌شده:** `f9d218de918b2b5a21cb818265a18a8a4aa8ee58`.

[رگرسیون نهایی #41189198386](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41189198386) دقیقاً روی همین کد پایان یافته است:
- **۷/۷ Job SUCCESS**، از جمله `verify-full-union` و راستی‌آزمایی JUnit/SHA.
- قراردادهای هدفمند Linux و Windows: هر کدام **۴۸۰ PASS**.
- مجموعه جامع Linux: **۸٬۶۴۴ PASS / ۵ SKIP**، ۸٬۶۴۹ مورد.
- Windows سه شارد: **۲٬۸۰۳ + ۳٬۱۶۱ + ۲٬۶۷۸ = ۸٬۶۴۲ PASS / ۷ SKIP**، ۸٬۶۴۹ مورد.
- **صفر FAIL/ERROR/Timeout**؛ ۷۳۸ ماژول فعلی در شاردهای Windows ثبت و تطبیق شدند.
- [گیت هدفمند IFC و منبع #41188689683](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41188689683) نیز قبلاً دو Job موفق ۱۵۱ PASS داشته؛ آزمون‌های جدید اتصال به Commit دستی/AI، ممیزی اصلی IFC/DXF، و دو Crosswalk مستقل در اجرای جامع نهایی موجودند.

### دامنه پذیرش E8
۱. بازخوانی نشست‌های واقعی SQLite، منبع PDF/CAD و SHA، هویت هندسی، واحد و Revision؛ رد تغییر هم‌زمان و مدرک ناقص.
۲. تشخیص تکرار برداشت و اختلاف مقدار منابع هم‌عضو؛ در موارد نیازمند حل تخصصی، `REVIEW_REQUIRED`، بدون حدس، حذف مقدار یا آشتی خودکار.
۳. محافظت از مسیر ثبت BOQ دستی و پیشنهاد AI تأییدشده، **قبل از ذخیره در ProjectStore**؛ رد خطا بدون تغییر digest.
۴. بازاعتبارسنجی سوابق AI قدیمی از DrawingTakeoffSession اصلی، بدون اعتماد به متن آزاد AI.
۵. ممیزی Crosswalk تأییدشده IFC↔CAD/PDF، فایل‌های اصل، رسید هش، نقش بازبین مستقل و شناسه واقعی عضو/طبقه؛ اتصال آن به هر دو Commit اصلی و مسدودکردن دو ادعای مستقل برای مالک فیزیکی یکسان.
۶. استفاده از موتورهای موجود `assert_new_measurements`، `physical_quantity_guard`، `validate_commit_rows` و `rebuild_project_boq` برای گونه‌های خارج از محدوده E8 سطحی؛ هیچ موتور موازی یا آفرینش خودکار کمیت IFC افزوده نشده است.
۷. Crosswalk و IFC به‌تنهایی **مجوز متره، پرداخت یا تأیید مهندسی نیستند**. Split/Merge، انتقال مالکیت و اصلاحیه فقط با کنترل‌های مستقل موجود و مدارک تخصصی مجازند.

**حکم:** `P7_P5_AUTOMATED_TECHNICAL_SCOPE=COMPLETE_ACCEPTED`. گیت اولویت ۵ فاز ۷ برای عبور به **اولویت ۶ همان فاز** باز است. این حکم جایگزین وضعیت‌های `PENDING/PARTIAL` تاریخیِ بخش‌های قبلی سند است؛ آن موارد گزارش‌های زمانی مراحل پیشین بودند. سایر قابلیت‌ها، مستندات محصول و پوشش عمومی فراتر از محدوده مصوب P5 با این حکم خودکار پذیرفته نمی‌شوند.

**مرزها:** `WINDOWS_PHYSICAL_HARDWARE_MS_OFFICE_PRINT_G4=NOT_TESTED_DEFERRED_PHASE8`؛ `PR39=DRAFT_OPEN_UNMERGED`؛ بدون Merge/main/ForcePush/EXE/Installer/Release.

### پیشرفت ثابت و قابل محاسبه
فازهای ۱ تا ۶ از لحاظ فنی ۱۰۰٪؛ در فاز ۷ پنج اولویت از شش اولویت پذیرفته‌شده؛ فاز ۸ هنوز آغاز نشده. با **هشت فاز هم‌وزن** و شش اولویت هم‌وزن داخل فاز ۷:
`(6 + 5/6) / 8 × 100 = 85.416666…% ≈ 85.4%`.
تعداد فازها **۸** و تعداد اولویت‌های فاز۷ **۶** ثابت است. اولویت ۶ هنوز آغاز نشده.

### خلاصه وضعیت پروژه و این چت
- فازهای ۱ تا ۶: کامل از نظر توسعه/آزمون فنی؛ پذیرش فیزیکی در فاز۸.
- فاز ۷: اولویت‌های ۱ تا **۵ کامل فنی خودکار**؛ اولویت۶ شروع نشده.
- فاز۸: شروع نشده؛ گیت نصب، Office و چاپ واقعی باز.
- درصد فعلی بر اساس فرمول تثبیت‌شده: **۸۵٫۴٪**.
- PR #39 باز و Draft؛ هیچ ادغام یا انتشار انجام نشده است.
