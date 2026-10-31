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
