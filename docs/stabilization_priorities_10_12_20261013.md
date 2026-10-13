# StructuralPro — تثبیت و یکپارچه‌سازی گروه اول (اولویت‌های ۱۰، ۱۱، ۱۲)

تاریخ بررسی: ۲۰۲۶-۱۰-۱۳  
مخزن: \`Asanda021/StructuralPro-Recovery\`  
شاخه: \`fix/stabilize-integrate-test-core-20261013\`  
مبنا: \`audit/items-priorities-1-9-20261013\` — PR #15  
**وضعیت: اصلاحات واقعی به شاخه مستقل ثبت شده؛ تأیید جامع مخزن هنوز انجام نشده است.**

## ۱۰. تثبیت منبع و بررسی تعارض شاخه‌ها

بر اساس compare واقعی GitHub:
- \`main → PR #11\`: ۴۸ commit جلو، صفر عقب
- \`PR #11 → PR #13\`: ۲۰ commit جلو، صفر عقب
- \`PR #13 → PR #14\`: ۱۳ commit جلو، صفر عقب
- \`PR #14 → PR #15\`: ۲۲ commit جلو، صفر عقب
- \`PR #15 → این شاخه\`: زنجیره خطی، مقادیر جدید باید با compare روی آخرین SHA بازبینی شوند.

**شاخه‌ها همه روی یک خط تاریخچه‌اند؛ ادعای ادغام نهایی با \`main\` نمی‌شود.** شاخه مادر اصلی تغییر نکرده؛ Build، Installer، Release و فعال‌سازی GitHub Actions ممنوع است. هیچ Workflow فعال در tree مشاهده نشد.

هسته سالم از مخزن اصلی بازیابی‌شده حفظ شده و بازنویسی کلی انجام نشده است. کد تغییرات روی مسیر جداگانه است تا جزئیات تیر، ستون/پی و سایر AEC مخلوط نشوند و بتوان آزمون مجزا گرفت.

## ۱۱. کنترل کیفیت با شواهد واقعی

در محیط محلی \`/mnt/data/structuralpro_patch\` دستور pytest زیر **واقعاً اجرا** شده است:

\`\`\`bash
PYTHONPATH=. pytest -q \
  tests/test_sqlite_backup_integrity_local.py \
  tests/test_structural_guard_integration_local.py \
  tests/test_store_boq_real_local.py \
  tests/test_commit_guards_local.py \
  tests/test_beam_detail_workflow.py \
  tests/test_beam_detail_match.py \
  tests/test_beam_detail_vector_fixtures.py \
  tests/test_beam_rebar_hints.py \
  tests/test_stirrup_zones.py
\`\`\`

**نتیجه تأییدشده: ۱۲۷ PASS / صفر FAIL / صفر SKIP، حدود ۰٫۴۱ ثانیه.**

شفافیت الزامی:
- در این محیط، \`ProjectStore\`, \`core/takeoff/boq.py\`, \`core/recovery/recovery.py\`, \`core/platform/revisions.py\` از روی کدهای واقعی GitHub با هش blob یکسان استفاده شده‌اند؛ آزمون SQLite، تراکنش، کش و Backup واقعی انجام شده است.
- برخی وابستگی‌های \`TakeoffEngine\` و Drawing و نیز کد کامل \`StructuralProApp\` در مجموعه محلی به‌صورت ایزوله/جایگزین هستند؛ **۱۲۷ PASS اثبات عبور آزمون‌های full repo نیست**.
- فایل‌های \`tests/test_stabilize_integrate_priorities_10_12.py\`, \`tests/test_stabilize_cross_workflow.py\`, \`tests/test_stabilize_backup_integrity.py\`, \`tests/test_stabilize_application_service.py\` در GitHub ثبت شده‌اند، ولی **اجرای pytest روی همه فایل‌های جدید و روی همه آزمون‌های مخزن واقعی هنوز احراز نشده**. نتیجه CI سبز به نام این شاخه وجود ندارد.
- PySide6 محلی نصب نیست. مطابق دستور مالک آزمون Windows UI و خروجی اجرایی به آینده موکول شده‌اند.
- اتصال مستقیم از ماشین آزمون به GitHub در دسترس نبود؛ بنابراین mirror کامل منبع ۱۶۰۰ فایل به محیط محلی انتقال داده نشده است.

## ۱۲. یکپارچه‌سازی موتور متره و قفل‌های مشترک

**کد جدید:**
- \`core/takeoff/commit_guards.py\`:
  - \`require_source_unused\` — منبع یکتای برداشت بین سه رجیستری بازبینی تیر، سازه و AEC و takeoffهای قطعی.
  - \`validate_commit_rows\` — کنترل کامل ردیف، واحد، مقدار مثبت/متناهی، شناسه source_id، جلوگیری از کسر تکراری \`intersections\` و \`deduction.id\` حفره‌های سقف.
  - \`rebuild_project_boq\` — تبدیل مشترک همه ردیف‌های takeoff به BOQ؛ حفظ قیمت‌نامه، ضریب، پرت و شناسه مأخذ.
  - \`require_reset_of_changed_approvals\` — هر بار جزئیات، هندسه یا مصالح قبلاً تأییدشده تغییر کنند، بازبینی قبلی نامعتبر شود.
- \`core/takeoff/explicit_inputs.py\` — اجرای **Fail-Closed** برای تعداد واقعی، لایه‌های سقف و ضریب مصرف/پرت صریح در ورودی‌های قدیمی و ویرایش آن‌ها. این گیت جلوی مقادیر پیش‌فرضِ نامستند را در مسیر عمومی سرویس می‌گیرد. فرمول‌های legacy همچنان برای سازگاری داخلی موجودند و هر مسیر دیگری که مستقیماً آن‌ها را صدا بزند نیازمند بازبینی جداگانه است.

**پیوند به جریان‌های اصلی:**
- \`BeamDetailWorkflow\` تیر؛ \`ReviewedStructuralWorkflow\` ستون/شناژ/پی؛ \`ReviewedAECWorkflow\` ۶۱ قرارداد رشته‌ای: هر سه از گیت مشترک استفاده می‌کنند.
- \`StructuralProApp\`: \`add_takeoff\`, \`add_assembly_takeoff\`, \`revise_takeoff\`, \`commit_drawing_takeoff_to_boq\`, \`commit_ai_takeoff_proposal\`: منبع و بازبینی، گیت مقدار، تبدیل BOQ یکپارچه و ذخیره CAS.
- \`recalculate_estimate\` و \`save_project_management\`: ذخیره با کنترل نسخه؛ برآورد مالی بدون قیمت/کد تأییدپذیر یا با ضریب نامتناهی مسدود است.
- برای Assembly، تمام اجزا یک بار با شناسه‌های مستقل در یک ذخیره ثبت می‌شوند؛ ردیف در میانه عملیات به‌صورت نیمه‌کاره در SQLite باقی نمی‌ماند.
- ویرایش عمومی ردیف‌های «از قبل تأییدشده/نقشه/Assembly» ممنوع؛ باید از مسیر بازبینی تخصصی استفاده شود.

**SQLite**
- \`ProjectStore.save\` اکنون \`BEGIN IMMEDIATE\` را پیش از کنترل digest اجرا و در صورت خطا rollback می‌کند.
- payload فایل فقط داده مهندسی پروژه است؛ \`_meta\` دیتابیس به‌عنوان فیلد مهندسی ذخیره نمی‌شود.
- خواندن cache با version SQLite اعتبارسنجی می‌شود تا ویرایش اتصال دیگر مخفی نماند.
- مقادیر NaN/Infinity اجازه ورود به JSON پروژه ندارند.

**BOQ**
- ردیف‌های دارای \`price_code\` یا شرح متفاوت هرگز فقط به دلیل کد عملیات یکسان ادغام نمی‌شوند.
- \`quantity=None\` یا Boolean مجاز نیست. هیچ قیمت یا پرت مهندسی از پیش‌فرض ساخته نمی‌شود.

## معیار واقعی بستن گروه اول

| الزام | نتیجه |
|---|---|
| کشف زنجیره بازیابی و اطمینان از نبود divergence در PRها | **انجام‌شده در GitHub**؛ merge به main هنوز ممنوع |
| اتصال موتورهای بازبینی‌شده به گیت مشترک | **کد اصلاح شد** |
| کنترل مسیرهای اصلی legacy manual/Assembly/drawing/AI | **کد اصلاح شد**؛ آزمون مخزن کامل باقی است |
| SQLite تراکنشی، Revision و cache | **کد اصلاح شد**؛ سناریوهای واقعی محلی PASS |
| بازسازی BOQ و منع ردیف/منبع تکراری | **کد اصلاح شد**؛ سناریوهای محلی PASS |
| اعتبارسنجی مبلغ و مقدار گزارش | **گیت‌ها تقویت شدند**؛ آزمون جامع و گزارش فارسی باقی است |
| pytest کامل روی وابستگی‌های واقعی مخزن و آزمون سرویس اصلی | **هنوز احراز نشده**؛ نباید PASS اعلام شود |
| Windows UI، Installer، Build، Release، GitHub Actions | **عمداً اجرا نشده** بنا بر دستور مالک |

**نتیجه:** گروه اول از حالت برنامه به اصلاحات واقعی رسیده و نقاط بحرانی پوشش داده شده‌اند؛ اما «هیچ ایرادی باقی نمانده» بدون اجرای آزمون‌های تازه در مخزن کامل و داده واقعی، قابل اثبات نیست. به جای صدور گواهی صحت غیرواقعی، تمام گیت‌های باقی‌مانده مستند شده‌اند.
