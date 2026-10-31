# StructuralPro | فاز ۷، اولویت ۴: گزارش‌های تخصصی دفتر فنی و کنترل پروژه

**گزارش اجرایی ۳۱ اکتبر ۲۰۲۶** | [PR #38](https://github.com/Asanda021/StructuralPro-Recovery/pull/38)

## وابستگی گیت و دامنه ثابت

- اولویت ۲ فاز۷: پذیرش فنی خودکار در PR #36 ثبت شده است.
- اولویت ۳ فاز۷: بر اساس SHA آزموده‌شده `183df00fa0cc4bf20f3ba688006bfd11dd27eda2` در PR #37 **پذیرفته فنی خودکار**؛ [هدفمند #41141103131](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41141103131) هر سیستم ۱۴۱ PASS؛ [جامع #41141103045](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41141103045) Linux ۸۵۸۶/۵ و Windows ۸۵۸۴/۷، ۱۲ PASS union و صفر FAIL/ERROR/Timeout، ۸۵۹۱ کیس یکتا.
- براساس این گیت، اولویت ۴ در شاخه جداگانه `feature/phase7-p4-technical-office-reports-20261031` از HEAD مستند P3 آغاز شد؛ PR #38 Draft/Open/Unmerged.

## کار واقعی P4-A: گزارش اختلاف ریزمتره بین Revisionها

`core/reports/technical_office_revision.py`:
- دو نسخه باید مستقیماً از `ProjectStore.revisions()` دارای ACL و تاریخچه اصلی SQLite خوانده شوند؛ ورودی دو dict آزاد، منشأ Revision واقعی نیست.
- تطبیق `source_id + item_code + unit` با ریزمتره و BOQ توسط `custom_batch._source_rows` و اعتبارسنجی اصلی `audit_boq`، اصلاحیه‌های موجود و هش واقعی منبع نقشه؛ تکرار یا دستکاری Fail-Closed.
- مقدار قبل، بعد، اختلاف و وضعیت افزوده/حذف‌شده/تغییرکرده/بدون‌تغییر به صورت Decimal دقیق، به تفکیک واحد، کد، منبع و هویت عضو/طبقه.
- این مسیر فقط گزارش مقداری است: **اثر مالی `null` و NOT_DETERMINABLE_WITHOUT_APPROVED_PRICES**، هرگز عدد صفر فرض نمی‌شود. تعیین اثر مالی واقعی در ادامه باید از زنجیره برآورد و فهرست‌بهای تاییدشده عبور کند.
- صدور PDF/XLSX/DOCX/CSV توسط `ProjectReport.export` قبلی، Manifest شش‌هویتی شامل SHA فایل‌ها، staging، کنترل مجدد نسخه جاری و تاریخچه، بدون نوشتن SQLite/BOQ.

## کار واقعی P4-B: بسته یکپارچه گزارش‌ها

`core/reports/technical_office_dossier.py`:
- انتخاب صریح نوع گزارش از **سرویس‌های موجود** `project_controls_report` برای WBS/فعالیت‌ها/برنامه/پیشرفت/منحنی S و `site_report` برای منابع، مواد، پیش‌نویس خرید، گزارش روزانه، مانع، جلسه، مکاتبه و برنامه کوتاه‌مدت.
- **داده مورد نیاز باید واقعاً ثبت شده باشد**؛ در غیر این صورت کل درخواست بدون تولید بسته رد می‌شود. نبود Baseline یا پیشرفت تأییدشده قابل ترسیم نیست و به صفر یا منحنی حدسی تبدیل نمی‌شود.
- چهار قالب فایل اصلی برای هر گزارش، بازخوانی مستقل PDF/XLSX/DOCX/CSV، کنترل RTL، وجود نمودارها در گزارش‌های مرتبط و SHA پیوست‌های PNG معتبر در Manifest.
- کنترل optimistic digest و snapshot قبل و بعد و انتشار پوشه‌ای مرحله‌ای؛ بدون افزودن موتور موازی برنامه، متره یا مالی.
- Fixture پنج‌طبقه واقعیِ **مصنوعی آزمون** در `tests/test_phase7_p4_five_storey_site_golden.py` از اجرای اصلی `scripts/phase4_site_operations_probe.py` استفاده می‌کند، نه از داده یک کارفرمای واقعی.

## آزمون‌ها و وضعیت واقعی

- [اولین CI مستقل P4 #41170962075](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41170962075): Linux **۱۲۶ PASS**؛ Windows **۱۲۵ PASS و ۱ SKIP محیطی**؛ صفر FAIL/ERROR. آزمون واقعی SQLite History، Delta و چهار قالب موفق.
- [CI بسته گزارش #41171176049](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41171176049): Linux **۱۳۴ PASS**؛ Windows **۱۳۳ PASS/۱ SKIP محیطی**، صفر FAIL/ERROR. آزمون صدور WBS/پیشرفت/منحنی و SHA واقعی موفق.
- [CI پنج‌طبقه #41171344415](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41171344415) برای سناریوی گسترده کارگاهی اجرا شد، **نتیجه تا راستی‌آزمایی مستقل PENDING** است.
- [CI جامع P4 #41171397969](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41171397969) برای Linux و Windows ۳‌شارد و آزمون exact union آغاز شد؛ **نتیجه PENDING**، تا تکمیل ۷ Job و JUnit نمی‌توان PASS ثبت کرد.

## تعهدهای باقیمانده اولویت ۴

- آزمون نهایی پنج‌طبقه و رگرسیون جامع دقیق Commit نهایی، رفع REDها.
- اثر مالی اختلاف Revision صرفاً وقتی فهرست‌بها، نرخ و ضریب مصوب و تطبیق منبع بازاعتبارسنجی شده باشد؛ در غیر این صورت `NOT_DETERMINABLE` باقی بماند.
- تأیید صحت منابع و نسخه‌بندی در بسته جامع گزارش‌های رشته‌های بیشتر، کنترل چاپ/فونت Office، پیوند حداکثری نقشه و BOQ و عدم استفاده از نسخه‌های منقضی.
- آزمون واقعی Windows/MS Office/چاپ برای فاز ۸، نه PASS خیالی.

**وضعیت اولویت ۴: `PARTIAL / NO-GO_FOR_FULL_ACCEPTANCE` تا شواهد نهایی؛ مجوز Merge/Release ندارد.**

## خلاصه وضعیت کل پروژه و این چت
- فازهای ۱ تا ۵: پذیرش‌های فنی پیشین محفوظ.
- فاز ۶: تحویل فنی خودکار؛ G4 فیزیکی با تصمیم مالک به فاز ۸ موکول شده و هنوز NOT_TESTED.
- فاز ۷: P1 و P2 و P3 از نظر فنی خودکار پذیرفته؛ P4 در توسعه و آزمون، P5/P6 خارج مأموریت جاری.
- فاز ۸: هنوز آغاز نشده. نقشه‌راه کل ۸ فاز و پیشرفت رسمی ۸۵٪ بدون تغییر.
- PRهای #34 تا #38 Open/Draft/Unmerged؛ هیچ Merge/main/ForcePush/EXE/Installer/Release انجام نشده است.

## راستی‌آزمایی نهایی CI بر SHA عملکردی (۳۱ اکتبر ۲۰۲۶)

نتایج بالای فایل که «PENDING» گزارش شده‌اند، وضعیت تاریخی همان لحظه‌اند. اکنون شواهد نهایی مستقیم از GitHub Actions روی **SHA دقیق** `62882f15ebce7f21214b71091ceb6c88d795dfd2` بازخوانی و تأیید شد:

- [P4 هدفمند #41171489047](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41171489047): دو Job موفق؛ Linux **۱۳۵ PASS / ۰ SKIP** و Windows **۱۳۴ PASS / ۱ SKIP محیطی**؛ صفر FAIL/ERROR. آزمون‌های SQLite Historical Revision، Golden پنج‌طبقه، Office Dossier و نگهبان‌های P1–P3 برقرارند.
- [P4 جامع #41171488812](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41171488812): هر **۷ Job SUCCESS**؛ Linux **۸٬۶۰۵ PASS / ۵ SKIP**؛ Windows بومی سه شارد به ترتیب **۲٬۹۸۹ + ۲٬۷۲۳ + ۲٬۸۹۱ = ۸٬۶۰۳ PASS / ۷ SKIP**، صفر FAIL/ERROR/timeout.
- Job `verify-full-union`: **۱۲ PASS**، تطبیق فایل‌ها و SHA/JUnit، مجموعه **۸٬۶۱۰ تست یکتا در ۷۳۳ ماژول**. آزمون‌های skipped دارای دلایل محیطی ثبت‌شده‌اند؛ هیچ ادعای اجرای آن‌ها نیست.
- اجرای #41171397969 لغو و اجراهای RED قدیمی به‌عنوان موفقیت معرفی نشده‌اند. مبنا فقط runs بالا روی SHA مذکور است.

**حکم:** `P7_P4_IMPLEMENTED_TECHNICAL_SCOPE = AUTOMATED_ACCEPTED` برای مقایسه Revisionهای مقدارمحور، چهار خروجی واقعی، بسته WBS/کنترل پروژه/سایت و Golden پنج‌طبقه **در دامنه آزموده‌شده**. `P7_P4_OVERALL = PARTIAL` تا تعیین تکلیف موارد باز فهرست‌شده در این گزارش، به‌خصوص اثر مالی فقط با مبنای تأییدشده و پوشش جامع منبع‌ها و یکپارچه‌سازی. `PHYSICAL_MS_OFFICE_WINDOWS_UAT = NOT_TESTED_DEFERRED_PHASE8`.

پذیرش این گیت هیچ تغییری در تعداد **۸ فاز اصلی**، ۶ اولویت از پیش تعیین‌شده فاز۷ یا درصد رسمی **۸۵٪** ایجاد نمی‌کند. PR Draft/Open/Unmerged؛ بدون Merge، main، ForcePush، EXE و Release.

## تکمیل کنترل مشروط اثر مالی Revision (ادامه اولویت ۴، ۳۱ اکتبر ۲۰۲۶)

این بند جایگزین گیت موفق قبلی نمی‌شود. کد جدید **پس از** SHA `62882f1` است و پذیرش آن باید بر اساس Commit خودش ارزیابی شود.

- تغییر `core/reports/technical_office_revision.py`: قابلیت `include_verified_financial_impact` به‌صورت **اختیاری و پیش‌فرض false** اضافه شد. زنجیره اصلی گزارش مقدارمحور تغییر نکرده است.
- تنها در صورت داشتن فهرست‌بهای **تأییدشده، فرمت عددی exact v2، SHA منبع معتبر، سال/نسخه و currency برابر IRR/IRT در دو Revision واقعی SQLite، نرخ/ضریب ثابت و تفکیک بدون ابهام منبع BOQ**، تغییر مقدار در نرخ و ضریب ضرب می‌شود. مسیر `audit_boq(..., require_pricebook=True)` و `verify_reviewed_rates` موجود دوباره همه ردیف‌ها را اعتبارسنجی می‌کند.
- **بدون منبع قیمت یا واحد پول معتبر، اثر مالی NULL و وضعیت NOT_DETERMINABLE باقی می‌ماند**؛ اثر مالی موجود به معنی تأیید صورت‌وضعیت، نرخ جدید، تعدیل یا پرداخت نیست.
- مقدار مالی هر ردیف، بهای واحد مستند، ضریب و currency به ردیف گزارش و جمع مالی به Metadata و Manifest اضافه شد؛ PDF/DOCX/XLSX/CSV همان صادرکننده قبلی هستند.
- آزمون `tests/test_phase7_p4_approved_price_impact.py` از **ورود واقعی فایل CSV قیمت با بازبین مصنوعی، Revisionهای واقعی ProjectStore، اصلاح متره از ۳۰ به ۳۶ مترمربع و نرخ ۱۰۰ ریال برای اختلاف ۶۰۰ ریال** استفاده می‌کند. نبود currency، دستکاری منبع نرخ، ضریب، قیمت، مبلغ ردیف، خروجی چهارگانه و عدم تغییر SQLite ارزیابی می‌شوند.
- Commit عملیاتیِ این گام: `14b2bb015fbf3b0da49d4d64372d153e8c2ec8e8`.
- [CI هدفمند #41173598106](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41173598106): Linux **۱۴۴ PASS، صفر شکست**، Windows هنگام ثبت این سند **PENDING**.
- [CI جامع #41173598129](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41173598129): **PENDING**؛ تا شواهد ۷ Job و union، پذیرش نهایی این تغییر ثبت نمی‌شود.
- `P7_P4_NEW_FINANCIAL_GUARD = IMPLEMENTED_LINUX_TARGETED_PASS_WINDOWS_AND_BROAD_PENDING`؛ `P7_P4_OVERALL = PARTIAL`.
- قبل از بستن گیت نهایی، اگر تغییر دیگری در کد رخ داد، نتیجه آزمون‌ها باید مطابق SHA جدید بازبینی شود. پذیرش فیزیکی Windows/MS Office/چاپ همچنان فاز ۸ و NOT_TESTED است. بدون Merge/main/EXE/Release.

## تصمیم نهایی پذیرش فنی خودکار اولویت ۴ | ۳۱ اکتبر ۲۰۲۶

به استناد **کد محصول آزموده‌شده** `0cdee9f8a7e1dec70e4da818b27d307d38c014b4` (که نسبت به `14b2bb0` صرفاً مستند پذیرش قبلی به آن افزوده شد) نتیجه‌های مستقل CI دوباره راستی‌آزمایی شد:

- [هدفمند #41173776051](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41173776051): دو Job موفق، Linux **۱۴۴ PASS/۰ SKIP** و Windows Native **۱۴۳ PASS/۱ SKIP محیطی**؛ صفر FAIL/ERROR.
- [جامع #41173776017](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41173776017): **۷/۷ Job SUCCESS**، Linux **۸٬۶۱۴ PASS/۵ SKIP**، Windows سه شارد **۳٬۰۶۰ + ۲٬۷۲۶ + ۲٬۸۲۶ = ۸٬۶۱۲ PASS/۷ SKIP**، صفر FAIL/ERROR/Timeout. verify-full-union موفق؛ مجموعه **۸٬۶۱۹ تست یکتا در ۷۳۴ ماژول** و انطباق JUnit/SHA تأیید شد.
- کنترل P4 شامل دو Revision واقعی SQLite، بررسی PDF/DOCX/XLSX/CSV و تاریخچه و منبع، WBS/پیشرفت/منحنی/مصالح/خرید/صورت‌جلسه، Golden پنج‌طبقه مصنوعی و **اثر مالی فقط با فهرست‌بهای نسخه‌دار، دارای SHA و بازبینی‌شده با نرخ/ضریب ثابت و currency صریح** است. حالت فاقد مدارک، NULL باقی می‌ماند.
- مقدار مالی محاسبه‌شده، **اثر تغییر مقدار با نرخ ثابت** است، نه قیمت‌گذاری مجدد یا سند پرداخت/صورت‌وضعیت صادرشده. موارد بدون قیمت/مبنای تأییدشده به نتیجه مالی مجاز تبدیل نمی‌شوند.
- **تصمیم:** `P7_P4_AUTOMATED_TECHNICAL_SCOPE=ACCEPTED`؛ گیت توسعه اولویت ۵ باز است. بازرسی واقعی Windows/MS Office/چاپ/چندمانیتور/G4 همچنان `NOT_TESTED_DEFERRED_TO_PHASE8` است؛ نباید با CI یکسان فرض شود.
- `PR38=OPEN_DRAFT_UNMERGED`، `MERGE/MAIN/INSTALLER/EXE/RELEASE=BLOCKED`، تعداد فازهای مصوب **۸**، تعداد اولویت‌های فاز۷ **۶**، درصد رسمی کل پروژه **۸۵٪ بدون تغییر**.

**بندهای PENDING و PARTIAL بالای فایل شرح وضعیت تاریخی پیش از Run نهایی هستند؛ این تصمیم نهایی در دامنه فنی خودکار، جایگزین آن‌هاست.**
