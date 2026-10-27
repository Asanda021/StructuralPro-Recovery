## ادامه اجرایی نهایی این مأموریت — ۲۷ اکتبر ۲۰۲۶

کد/تست نهایی `0c8dae4ce1f182a7599932dc48b63455b933c6d5`؛ Tree `2d41d0e1abf92297482fe57ecf1e62c31d3fef01`. [CI 40541143258](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40541143258) SUCCESS: هر محیط Linux/Windows **۲۱۸ PASS اصلی + ۸ PASS scale2**، صفر FAIL/ERROR/SKIP و صفر warning pytest اصلی. هشت تست scale2 تکرار همان Dockها هستند. مبنای معتبر انتقال W1: f84b593 و CI40540215367، هر محیط۱۳۵PASS.

هفت اصلاح واقعی: recheck تأیید تیر، guard وابسته به پیشنهاد اصلی، تشخیص ابهام جست‌وجو، ناوبری طبقه واقعی، نمایش همه وابسته‌های گروهی، اتصال digest تا SQLite و رد تغییر مدرک قطعی حتی با مقدار برابر. گزارش کامل فایل‌ها، Oracle، RED/GREEN، شواهد، گیت‌ها و checkpoint: [verification-20261027-hardening/REPORT.fa.md](verification-20261027-hardening/REPORT.fa.md).

P6-4/P6-5 همچنان PARTIAL؛ مالکیت مشترک واقعی/Split-Merge، ماتریس کامل IFC/فرم‌ها، همه مقصدهای تخصصی، مدل تجاری و UAT فیزیکی بازند. Git auth در انتهای کار پس از Pushهای موفق محصول از کار افتاد؛ وضعیت انتشار Commit جدید شواهد باید جداگانه تأیید شود. main/Merge/ForcePush/Release/EXE/P6-6/فاز۷ انجام نشد؛۸فاز و۸۵٪ ثابت.

---

# آخرین checkpoint معتبر | ۲۷ اکتبر ۲۰۲۶

مخزن: Asanda021/StructuralPro-Recovery. PR #33 و PR #34 باز، Draft و Unmerged اند.

- PR33: آخرین commit کد/تست 0a955cd43d85941bd3c19c773485b6cb06061381؛ CI 40514369144: Linux ۱۱۵ PASS و Windows ۱۱۵ PASS، هرکدام ۱ هشدار fitz. مستندات PR33 مستقل پس از Commit کد به‌روز شده‌اند؛ HEAD را زنده بخوانید.
- PR34: Commit کد/تست 665e9989c29d58c690d83b2f73b407a24c61db34؛ Tree db33cb16fc8e888d5b79e1b04109c3801c19918a. CI 40515516006: در هر محیط Linux/Windows تعداد ۱۸۸ PASS اصلی + ۸ PASS scale2؛ صفر FAIL/ERROR/SKIP. این ۸، آزمون‌های تکراری در scale2 هستند.
- W1 lifecycle اکنون کد اجرایی دارد، نه فقط patch: clean Cancel/Close/Disable، dirty preservation/guard، Discard Yes/No، PDF SHA و اعتبار پروژه/طبقه/عضو پس از اتصال تست شده‌اند. ۵ فایل اصلی و فایل تست P6-4 به شاخه P6-5 منتقل شدند و E3–E6 حفظ شدند.
- SHA256SUMS شاهدهای قدیمی W1 در PR33 برای همه شش فایل تکمیل شد؛ لاگ‌ها و JUnitهای جدید در Artifactهای CI اصلی هستند.
- **باز:** کل پوشش IFC پیچیده، همه Save/Preview/Commit و تغییر منبع هنگام ویرایش در تمام خانواده‌ها؛ E4 مقصدهای تخصصی؛ E6 Shared Geometry Ownership/Split-Merge؛ UAT فیزیکی Windows و چندمانیتور؛ مدل واقعی دارای مجوز A2. هیچ ادعای پذیرفته‌شدن این گیت‌ها نشده است.
- verdict هر دو P6-4/P6-5: PARTIAL. P6-6 و فاز ۷ شروع نشده‌اند. هشت فاز و ۸۵٪ ثبت‌شده بدون تغییر. بدون Merge/main/Force Push/Release/EXE.

[CI W1](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40514369144) | [CI P6-5](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40515516006)

---

# checkpoint مستقل ۲۷ اکتبر۲۰۲۶

## checkpoint جاری این اجرا

PR34 شاخهfeature/phase6-p5-workspace-e3-e6-20261027؛ کدa1f4b583736c8b9d0d12119e86860211d60aa511،
Tree6cda96d5435b529b201681b36e7d8beb5027a0eb؛ HEADشواهد بعدی را ازGitHubبخوانید.
CI40473442169 هر محیط172PASS،صفرFAIL/ERROR/SKIP وبدونwarningfitz؛scale۲هرمحیط۸PASS.
PR33کدeb48e0553fcf1b5afa2a88c322df10f911d8a4ca،Tree9bb6061774e34a772854256aa58ba73ae64d6e63،CI40472322354هرمحیط۹۹PASS.
اصلاحاتW1بهPR34باpatchمنتقل شده‌اند؛ ForcePushیاMergeانجام نشده است.

تکرار نکنید: member_idستون/MEPبه فرم اصلی منتقل می‌شود؛ داده تیر بدون ویرایش در بازخوانی حفظ می‌شود؛
سه گردش ثبت واقعیW1/Oracle/Reopen باfixtureدستی موجود؛ تیر با پیامQtواقعیNo/Yes؛
پروفایلJSONخرابE3دیگر با ذخیره جدید پاک نمی‌شود؛ جست‌وجوی فرمول کلید/Revisionاصلی را نگه داشته و فرم واقعی همان ردیف را باز می‌کند؛
گزارش/قیمت/متره عمومی فاقدhandoffتخصصی فقط‌خواندنی‌اند؛ PyMuPDF جدید با آزمونFutureWarning=errorرفع هشدارشد.
E6دیوار بلوکی: خالص۱۰→۱۳،Undo۱۰،Redo۱۳،منبع کسر تکراری رد،Reopenبرابر،بدونBOQ؛split/merge/ownershipفاقدقراردادردمی‌شوند.

باقی و نخستین اقدامات:
۱. W1سه خانواده با نقشه باز وSHA/Revisionصریح و تمام سناریوهای منفی خانواده‌ای؛ در این اجراfixtureدستی مثبت بود.
۲. E4ماتریس جاری درگزارش: کلیکDXF/DWGوویرایشگرهای تخصصی باقی؛ مسیر جعلی/نگاشت اسمی نسازید.
۳. E6مالکیت مشترک بتن/میلگرد/پوشش ازسرویس structural_handoff_work موجود؛ هیچ تایید خودکار یاSplit/Mergeحدسی نسازید.
۴. E3/E5ماتریس کاملReopen/نمایشگرفیزیکی/DPI150%/Crashوپذیرش یکپارچه؛ CIجای دستگاه مالک نیست.
مدل واقعیA2تاوجودفایل/runtime/منشأ/مجوزمعتبرBLOCKED؛ P6-4/P6-5PARTIAL.
شواهدRED/GREEN/XML/Manifestدرverification-20261027-followup؛ بخش بالای گزارش پذیرش ملاک است.
فقط۸فاز،۸۵٪ثبت‌شده؛ بدونP6-6/فاز۷/main/Merge/Release/EXE/ForcePush.

---

## وضعیت جدید؛ این بخش ملاک ادامه است

PR34؛ شاخه feature/phase6-p5-workspace-e3-e6-20261027.
آخرین کد آزموده b30f90fe08e00ae4187031e116bea3dcbf65cf22؛ Tree c041edcb2059599d0050bd41c1b518a689b74db6.
HEAD واقعی را از GitHub بخوانید؛ Commit شواهد بعدی محصول را تغییر نمی‌دهد.
CI40466896839: Linux165PASS و Windows165PASS؛ صفرFAIL/ERROR/SKIP؛ scale۲ هشتPASS در هر محیط.
FutureWarning منسوخ‌شدن fitz ثبت شده است، نه شکست محصول. XML/تصاویر/RED و Manifest در verification-20261027.
گزارش جاری INITIAL_E3_E6_REPORT.fa.md را از بخش بالای آن بخوانید.

تکرار نکنید: Viewerهای اصلی2D/3D اکنونDock واقعی‌اند؛ انتخاب/بستن/بازکردن/شناورسازی حفظ می‌شود؛
بازیابی چیدمان پس از بازسازی کنترلر، پاک‌کردن BOQ در restore ناموفق، محدوده صفحه و scale۲ آزموده‌اند.
نقشه جدید3Dقبلی را می‌بندد. تغییرپروژه/نسخه نماهای قبلی را می‌بندد. موتور جدید وجود ندارد.
E4: PDF باSHA/Revision معتبر، IFC با بازبینی اصلی، BOQ و انتخاب دقیقWBS/فعالیت در فرم اصلی آزموده‌اند.
project_wbs وproject_schedule_tasks canonical هر دو جست‌وجو می‌شوند.
E6: ABORT واقعیSQLite هنگام درجRevision، rollback کل گروه/تاریخچه و reopen بدون تغییر تأیید شد؛
۲۱۸رگرسیون محلی موتورهای مالکیت موجود موفق‌اند، ولی اتصال همه اشتراک‌های هندسی به ویرایش گروهی باز است.

PR33 کد f3eaec938f402142c921e669f345004b3050c73a، Tree4d0bfbfcdfa85db2a697d3f28d92ce4dfd329e95؛
CI40466288771 هر محیط96PASS. اصلاح مسیر تیر و تشخیص ویرایش کاذب سقف و هشت گردش تأیید/ثبت
ازW1 به فرم اصلی، بدون نوشتن BOQ پیش از تأیید صریح، بهPR34 منتقل و دوباره آزموده شدند.

باقی‌مانده: W1 گردش ثبت نهایی تیر/ستون/MEP؛ همه ناوبری‌های تخصصیE4؛ اتصال مالکیت مشترک معتبر
برای همه خانواده‌های گروهیE6 وSplit/Merge؛ آزمون فیزیکی چندمانیتور/DPI/sleep؛ پذیرش یکپارچه جامع.
برایE6 از structural_handoff_work و موتورهای مالکیت موجود استفاده شود، موتور موازی ساخته نشود.
مدل واقعیA2 تا وجودGGUF/mmproj/runtime/مجوز معتبرBLOCKED بماند؛ دانلود بی‌مجوز یاMock پذیرفته نیست.
P6-4/P6-5 PARTIAL؛ گیت‌های خودکار مشخص‌شدهPASS هستند، نه همه معیارها.
فقط۸فاز،۸۵٪ثبت‌شده، بدونP6-6/main/Merge/Release/EXE/ForcePush.

---
## checkpoint تاریخی قبل از این اجرا

مخزن Asanda021/StructuralPro-Recovery؛ PR34؛ شاخه feature/phase6-p5-workspace-e3-e6-20261027.
آخرین کد آزموده‌شده: c808d8c777dfea2e00e0fd6acde2ffaefed291e6.
Tree کد: 3df89f1b4f507ba2c3daeed6b26f3b5b44986850.
CI40462462651: Linux131PASS، WindowsNative131PASS، صفرFAIL/ERROR/SKIP.
Commit پس از آن فقط گزارش/این فایل را تغییر می‌دهد؛ HEAD واقعی را ابتدا بخوانید.

اصلاحات این نوبت را تکرار نکنید: E5 داده BOQ قبلی را در شکست refresh پاک می‌کند؛
E4 مجموعه اصلی project_schedule_tasks را جست‌وجو می‌کند. هر دو RED→GREEN مستقل دارند.

PR33 بدون تغییر:241dd15e3e5c3c572f94237da5146ceb04dc9dbf؛ کدd8e6a8d9a513be798237eb601e819fdd90e81ba9؛
CI40398093821 دو Job success و سابقه۶۹PASS هر محیط. مدل واقعی A2 همچنانBLOCKED است.

گیت‌های باز: گردش مودال کامل خانواده‌هایW1، مدل معتبر و مجوزA2، ناوبری تمام اسناد تخصصیE4،
پنل‌های واقعی کامل2D/3D/گزارشE5 و حفظ انتخاب هنگامDock، پوشش مالکیت مشترک هندسیE6 و
پذیرش یکپارچه بین‌اولویتی. نتایج موجود این گیت‌ها را بسته اثبات نمی‌کنند.
E3 دارای پروفایل و آزمون موجود است؛ تکمیل همه معیارهای فایل خراب/قدیمی و طبقات بالاتر باید
با تطبیق آزمون‌ها بررسی شود. آزمون فیزیکی چندمانیتور/انسانیWindows مستقل باز است.

P6-4 وP6-5 همچنانPARTIAL؛ اولویت۶ آغاز نشود. هیچMerge/Release/EXE/ForcePush/main انجام نشود.
فقط۸فاز؛ درصد قطعی ثبت‌شده۸۵٪. از همینHEAD و سرویس‌های موجود ادامه بدهید.
