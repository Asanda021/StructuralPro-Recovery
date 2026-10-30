# StructuralPro | تحویل فنی فاز ۶ به توسعه فاز ۷ (۳۱ اکتبر ۲۰۲۶)

## مبنای قطعی
- مخزن: `Asanda021/StructuralPro-Recovery`، PR [#34](https://github.com/Asanda021/StructuralPro-Recovery/pull/34)، کد و تست آزموده‌شده: `66022c2dd1476b37399d83480be108a0002cae96`.
- [اجرای رگرسیون جامع #41115073037](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41115073037): هفت Job موفق؛ Windows ۸٬۴۷۸ PASS، ۷ SKIP، ۰ FAIL/ERROR در سه شارد؛ Linux ۸٬۴۸۰ PASS، ۵ SKIP، ۰ FAIL/ERROR؛ آزمون مستقل verify-full-union نیز ۱۲ PASS. تعداد ۸٬۴۸۵ مورد در هر سیستم شامل SKIPهای محیطی است. شواهد SHA یکسان، JUnit/Manifest و union در artifact اجرای CI محفوظ‌اند.
- آزمون تخصصی همان SHA: Windows و Linux هرکدام ۳۵۲ PASS؛ DPI منطقی Windows چهار مقیاس ۱۰۰/۱۲۵/۱۵۰/۲۰۰ هرکدام ۱۸ PASS، ۷۲ اجرای آزمون نه ۷۲ سناریوی منحصربه‌فرد.
- اصلاح اخیر نوار ابزار ResponsiveFlowLayout در نماهای 2D/3D و تغییر آزمون عرض محدود روی همین SHA قرار دارد. هشدار قدیمی برش ابزار در تصاویر ۲۰۰٪ باعث اصلاح و بازآزمون شد؛ CI خودکار اکنون سبز است اما جای تأیید روی سخت‌افزار واقعی را نمی‌گیرد.

## تصمیم پذیرش بدون جعل نتیجه
| حوزه | وضعیت |
|---|---|
| P6-1 تا P6-5 | `AUTOMATED_TECHNICAL_SCOPE_ACCEPTED` در محدوده آزمون‌های مستند |
| G1 | `AUTOMATED_NATIVE_STABILITY_BOUNDED_ACCEPTED`؛ علت قطعی AV تاریخی اثبات نشده |
| G2 | `SOURCE_BACKED_VISUAL_SCOPE_ACCEPTED`؛ IFC2X3 بازسازی فقط-خواندنی و بدون اختیار QTO |
| G3 | `NONBLOCKING_NO_SEPARATE_CONTRACT` |
| G4 | `AUTOMATED_ACCEPTED / PHYSICAL_UAT_NOT_TESTED / OWNER_SIGNOFF_ABSENT` |
| G5 | `ONE_UNIFIED_WINDOWS_POLICY_ACCEPTED / NO_BINARY_BUILT` |
| کل فاز ۶ | `TECHNICAL_AUTOMATED_HANDOFF_READY; FORMAL_CLOSURE_PARTIAL_NO_GO` |

مطابق دستور جدید مالک برای حرکت پس از تکمیل فنی، **شروع پیاده‌سازی پیش‌نویس فاز ۷** در PR [#35](https://github.com/Asanda021/StructuralPro-Recovery/pull/35) انجام شد؛ این به معنی انتقال خودکار G4 به PASS یا صدور حکم PHASE6_CLOSED نیست. G4 باید روزی که ویندوز/نمایشگر فیزیکی فراهم شد با [چک‌لیست اصلی](../verification-20261030-g4-cloud/OWNER_UAT.fa.md) انجام و صریحاً تأیید یا رد شود. تا آن زمان برای این گیت `NOT_TESTED` ثبت می‌ماند.

## سیاست شاخه و محدودیت‌ها
- هیچ Merge، تغییر main، Force Push، EXE، Installer یا Release مجاز یا انجام نشده است.
- PR #34 همچنان Draft/Unmerged و PR #35 مستقل، انباشته بر شاخه PR #34 و Draft/Unmerged است.
- فاز ۷ تنها در دامنه گزارش مهندسی، نقشه ۲بعدی مستند، E7/E8/A3 و خروجی‌های RTL توسعه می‌یابد؛ فاز ۸ پذیرش نهایی مستقل و Office واقعی را پوشش می‌دهد. دقیقاً همان هشت فاز و پیشرفت ثبت‌شده ۸۵٪ بدون افزایش حدسی حفظ است.

## تصمیم مالک درباره زمان آزمون فیزیکی (۳۱ اکتبر ۲۰۲۶)

مالک صریحاً مقرر کرد **آزمون روی Windows واقعی پس از آماده‌شدن نسخه نهایی آزمایشی** انجام شود. این تصمیم، زمان اجرای همان چک‌لیست G4 مصوب را به مرحله پذیرش فیزیکی/نسخه آماده انتشار در **فاز ۸** موکول می‌کند؛ **تعهد جدید یا فاز تازه نیست**.

- از حیث **توسعه و پذیرش خودکار فنی در دامنه مصوب**، فاز ۶ برای تحویل به فاز ۷ بسته و تحویل داده شد؛ نیازی به اجرای مجدد بی‌دلیل رگرسیون سبز آن نیست.
- `G4_PHYSICAL_UAT = DEFERRED_BY_OWNER_TO_FINAL_WINDOWS_CANDIDATE`، `G4_TEST_RESULT = NOT_TESTED` و `OWNER_SIGNOFF = NOT_PROVIDED`؛ هیچ PASS فیزیکی یا امضای فرضی ثبت نمی‌شود.
- `PHASE7_DEVELOPMENT_AUTHORIZED = true` با این پیش‌شرط که PRهای وابسته Draft و Unmerged بمانند و قواعد ایمنی/منشأ/مالی تغییر نکنند.
- **انتشار نهایی فاز ۸** تا اجرای G4، آزمون Windows/Office/چاپ مصوب، تعیین تکلیف هر نقص مشاهده‌شده و تأیید مالک `NO-GO` می‌ماند.
- دریافت نسخه نهایی آزمایشی با ساخت یا انتشار رسمی یکسان نیست؛ ساخت EXE/Installer همچنان مجوز جداگانه لازم دارد. تصمیم حاضر مجوز Merge/main/EXE/Release نیست.

**حکم قابل اتکا:** `PHASE6_TECHNICAL_SCOPE = ACCEPTED_AUTOMATED`، `PHASE6_FORMAL_PHYSICAL_ACCEPTANCE = DEFERRED`، `PHASE7_WORK = AUTHORIZED_AND_STARTED`. عبارت «فاز ۶ صددرصد روی دستگاه مالک پذیرفته شد» ممنوع است.
