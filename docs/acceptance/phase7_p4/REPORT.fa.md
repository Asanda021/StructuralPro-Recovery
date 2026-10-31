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
