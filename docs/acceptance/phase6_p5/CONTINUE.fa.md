## آخرین SHA: مسیر قابل‌حمل Qt در Windows

CIهدفمند40675825529 روی5daf:۱۶PASS و۱FAIL فقط در آزمون جدید به‌خاطر نمایش `/` در Qt در برابر `\` در Windows؛ مقایسه Path با حفظ هویت دقیق فایل اصلاح شد. کد جدید3d1ac2d7a6be62b09e2daf17472632e022efcf06 و workflow cbe1d9f؛ CIهای [هدفمندWindows](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40676193303)، [پذیرش](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40676193299)، [گسترده](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40676193128) جاری؛ JUnit و report کامل Windows هنوز PARTIAL. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## انتخابگر سقف و آزمون‌های نهایی — ۲۸ اکتبر ۲۰۲۶

Windows هدفمند40675283022 پس از تغییر QFileDialog محصول رویcce78eb:۱۶PASS/۰FAIL/ERROR/SKIP؛ [artifact](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675283022/artifacts/12810615998). RED جدید ثابت کرد تایمر انتخاب فایل قبل از نمایش QFileDialog می‌تواند فرم والد را رد کند؛ test-only گارد هویت/والد/Open و انتظار محدود روی5daf8fb افزوده شد و بسته محلی۲۹PASS است. [CIهدفمند40675825529](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675825529)، [پذیرش40675825474](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675825474)، [گسترده40675825520](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675825520) جاری؛ وضعیت کل PARTIAL. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## ریشه QFileDialog Windows و اصلاح محصول

CIهدفمند40674791106 روی a41:۱۰PASS/۱FAIL؛ علت اول `fileNameEdit` در QFileDialog بومی Windows وجود ندارد، `setFocus` به None می‌رسد. [شاهد](verification-20261028-windows-qt-timeout/roof-native-first-failure.txt). محصولcce78eb در فایل سقف فقط `DontUseNativeDialog` را برای انتخاب JSON دیتایل اعمال می‌کند؛ Qt واقعی/QTest و BOQ دست نخورده، local۲۴PASS. [CIهدفمند40675283022](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675283022) و [پذیرش40675283032](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675283032) جاری، broad cce هنوز باید بعد از آن راه‌اندازی شود. rerun محلی broad a41:۸۳۷۵PASS/۰FAIL/۱۰SKIP،SIGSEGV اول همچنان ثبت. وضعیت کل PARTIAL.

---

## سه شکست و native crash بعدی در Windows

Broad40672896854 رویa41cd18: Linux۸۳۸۰PASS/۵SKIP، Windows سه FAIL در تست سقف planar و سپس0xC0000409 روی تست اصلاحیه هندسی، بدون JUnit. اجرای هدفمند Windows [40674791106](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40674791106) برای ثبت اولین خطای واقعی جاری؛ همان pair در Linux۱۶PASS. هیچ‌یک از شکست‌های broad پنهان نیست؛ گیت PARTIAL. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## پذیرش و گسترده Linux روی a41cd18

CI40672896825 هر سیستم۴۸۳PASS،۰FAIL/ERROR/SKIP؛ CI40672896854 Linux۸۳۸۰PASS،۵SKIP،۰FAIL،بدونtimeout. Windows گسترده هنوز جاری؛ broadمحلی قبلی SIGSEGV و retry مستقل پنج‌طبقه۱PASS جداگانه ثبت شده‌اند. وضعیت کل PARTIAL. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## بازآزمایی پنج‌طبقه

آزمون پنج‌طبقه که broadمحلیa41 را با SIGSEGV قطع کرد، به‌تنهایی ۱PASS/۷۵٫۹۶ثانیه شد؛ SIGSEGV broad همچنان ثبت و علت نامشخص است. CI پذیرش/گسترده a41 جاری‌اند؛ وضعیت کل PARTIAL.

---

## توقف Linux محلی روی a41cd18

broadمحلی روی آزمون پنج‌طبقه manual_formula در۳۴٪ با SIGSEGV / exit -11،بدونtimeout و بدونJUnit متوقف شد. علت معلوم نیست؛ بازآزمایی مستقل و CI40672896825/40672896854 جاری‌اند. این اجرا PASS نیست. [log/JSON](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## شکست دوم Windows و checkpoint سقف — ۲۸ اکتبر ۲۰۲۶

CIگسترده40670626852 رویfcf847 در Windows با **0xC0000409،timeout=false،JUnit مفقود** پایان یافت؛ Linux۸۳۷۸PASS/۵SKIP. آخرین سطر عمومی به تست واقعی Qt سقف PDF می‌رسد. RED نشان داد تایمر۴۰ms می‌تواند قبل از نمایش modal اجرا شود؛ انتظار محدود و شناسایی RoofDetailEditor در تست اصلاح شد، بدون انتساب قطعی crash به مسابقه. روی کدa41cd18 رگرسیون مشترک شمع/سقف۲۱PASS محلی؛ [CIپذیرش40672896825](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896825) و [CIگسترده40672896854](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896854) جاری‌اند. وضعیت کل PARTIAL تا JUnit واقعی Windows. [گزارش/شواهد](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## CI گسترده Linux نهایی

Run40670626852 کدfcf847: Linux۸۳۷۸PASS،۰FAIL،۵SKIP،exit۰،بدونtimeout؛ Windows هنوز جاری و گیت کلی PARTIAL. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## پذیرش نهایی fcf847 — ۲۸ اکتبر ۲۰۲۶

CI40669898079 روی Linux و Windows هرکدام۴۷۴PASS،۰FAIL/ERROR/SKIP،۱warningfitz؛ historical۱۳۰،security۲۶ و DPI۱۵۰/۲۰۰ هرکدام۸تکرارPASS. broad Linux محلی۸۳۷۳PASS/۰FAIL/۱۰SKIP؛ [CI گسترده40670626852](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852) هنوز جاری است، بنابراین PARTIAL. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## رگرسیون محلی نهایی — ۲۸ اکتبر ۲۰۲۶

SHA fcf847: broad Linux از worktree تمیز **۸۳۷۳PASS،۰FAIL/ERROR،۱۰SKIP،۳warning،exit۰،بدونtimeout**؛ JUnit واقعی در [شواهد](verification-20261028-windows-qt-timeout/qtfix-final-linux.xml). CI پذیرش هر سیستم۴۷۴PASS؛ Windows broad در [40670626852](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852) هنوز جاری و گیت کل PARTIAL است.

---

## پذیرش نهایی fcf847 — ۲۸ اکتبر ۲۰۲۶

[CI40669898079](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898079): Linux و Windows native هرکدام۴۷۴PASS،۰FAIL/ERROR/SKIP،۱warningfitz. historical۱۳۰،security۲۶ و DPI۱۵۰/۲۰۰ هریک۸تکرار در هر سیستم PASS. [گسترده40670626852](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852) هنوز درحال‌اجرا؛ گیت کل تا نتیجه واقعی آن PARTIAL. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## آخرین اجرای گسترده و تشخیص — ۲۸ اکتبر ۲۰۲۶

کد/آزمون fcf8472493e842fe707740d2baf166468bf11cdf؛ CI پذیرش [40669898079](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898079)، CI گسترده جدید [40670626852](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852). آخرین workflow0a7decf بخش واقعی انتهایی log را تنها در شکست به notice منتقل می‌کند؛ timeoutهای قبلی ثابت‌اند. نتیجه Windows تا JUnit/JSON واقعی PARTIAL است. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md).

---

## آخرین checkpoint کنترل watchdog — ۲۸ اکتبر ۲۰۲۶

کد fcf8472493e842fe707740d2baf166468bf11cdf؛ workflow a0cd4c7. RED واقعی: کلیک QTest بلعیده شد و watchdog قدیم نمی‌توانست بسته‌نشدن modal را گزارش دهد؛ اصلاح فعال‌ماندن تایمر تا بازگشت پنجره،۱۰تست هدفمندPASS. [گزارش](verification-20261028-windows-qt-timeout/REPORT.fa.md). [CI پذیرش40669898079](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898079) و [CI گسترده40669898071](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898071) pending؛ نتیجه قبلی74cc صرفاً snapshot است. Windows گسترده، JUnit و نتیجه نهایی هنوز PARTIAL.

---

## Windows Qt timeout — checkpoint جاری ۲۸ اکتبر ۲۰۲۶

کد/تست `74cc37d68c35a0a113643e7538d9dce3378e3597`، workflow `b423fcf178a16a1242599ed2d7b898d910f482ce`. پنجره خطای واقعی BoredPileErrorMessage از stack قبلی شناسایی شد؛ بازپخش تأخیر کنترل‌شده نشان داد singleShot(10) پیش از نمایش QMessageBox می‌تواند از دست برود، ولی علت انحصاری رخداد Windows ثابت نشده است. انتظار دارای deadline، کنترل والد/شناسه/عنوان/دکمه و کلیک واقعی Qt برای هشدار و خروج بدون ذخیره پیاده شده و۹تست محلی PASS دارند. [گزارش و RED/GREEN](verification-20261028-windows-qt-timeout/REPORT.fa.md).

[CI پذیرش40668037315](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40668037315) و [CI گسترده40668037298](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40668037298) برای SHA جدید در حال اجرا هستند؛ بدون نتیجه نهایی Windows و JUnit، گیت PARTIAL است. هیچ timeout افزایش نیافت، test حذف یا skip نشد، محصول و assertionهای داده محفوظ‌اند. PRها Draft/Unmerged؛ main ثابت،۸فاز و۸۵٪ بدون تغییر.

---

## بررسی مستقل timeout ویندوز — ۲۸ اکتبر ۲۰۲۶

**PARTIAL:** Run 40661082617 روی source 6990c9259eb23de25cad96a641f57413f6306609 در Windows با exit 124 و timeout 1500 ثانیه و JUnit مفقود شکست خورد. Artifact 12805470944 بازدریافت شد و SHA256 آن f4ce9616c0e88bc0cbfa22e869a39adb177fa0ec3e428323e15a02c2cb9a6875 با لاگ برابر است. Stack در QMessageBox.exec در app/bored_pile_detail_editor.py خط ۱۴۱ و test_bored_pile_draft_amendment_real_qt.py حوالی خط ۶۶ است. آزمون از singleShot(10) برای بستن هشدار و تأیید خروج استفاده می‌کند؛ زمان‌بندی عامل محتمل است اما stack به‌تنهایی علت قطعی را اثبات نمی‌کند. در این بررسی کد تغییر نکرد و RED/GREEN و Windows CI جدید اجرا نشد. محیط مجازی قبلی در محیط تازه موجود نبود. اقدام بعد: بازتولید کنترل‌شده در Windows native با ثبت نوع پنجره، زمان و رویداد تایمر و سپس اصلاح مبتنی بر شواهد، آزمون هدفمند و broad هر دو سیستم. CI محدود قبلی 40659709412 بر روی 6990c925 هر دو سیستم موفق بوده و جای broad Windows را نمی‌گیرد. بدون Merge/Force Push/main/Release/EXE/P6-6؛ ۸ فاز و ۸۵٪ ثابت.

---

## آخرین شاهد رگرسیون کامل اصلاح مودال، Run #40661082617
- **Source SHA آزموده‌شده:** `6990c9259eb23de25cad96a641f57413f6306609`، workflow trigger `e85fcfbdf990e82d89f28e95a1185821af369c7a`؛ قفل source در Checkout و assert فعال است.
- **Linux completed/success** در [Run #40661082617](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40661082617)؛ JUnit/JSON واقعی: **۸۳۸۰ collected، ۸۳۷۵ PASS، ۰ FAIL، ۵ SKIP مختص Windows**؛ `pytest_exit_code=0`، `timed_out=false`، `overall_green=true`.
- Artifact اصلی `p6-broad-current-linux-6990c9259eb2`، ID `12804826259`، حاوی XML/JSON/Log؛ در زمان کنترل موجود و منقضی‌نشده. SHA256 ZIP برابر `b4fbd77b41079ddf5a4e864d14ca61dfb9b6b3f85a016a1f63cfba919fe6219a` در لاگ رسمی.
- **Windows native در لحظه ثبت همچنان in_progress و JUnit نهایی ندارد**؛ PASS، تعداد آزمون و گیت دو‌سیستمی از آن ادعا نشود. نتیجه شکست/timeout قدیمی Run #40656152367 مربوط به کد `76969a29...` است و پاک یا بازنویسی نمی‌شود.
- CI محدود اصلاح روی `6990c925...` با **۴۷۰ PASS هر محیط** در Run #40659709412 موفق شده، اما جای رگرسیون گسترده Windows و UAT فیزیکی را نمی‌گیرد.
- P6-4/P6-5 هنوز PARTIAL؛ قرارداد تخصصی DWG/IFC، E6 مالکیت مشترک، A2 تجاری و UAT واقعی Windows بازند. ۸ فاز و ۸۵٪ رسمی ثابت؛ PR33/34 باز و Draft؛ main بدون تغییر، بدون Merge/ForcePush/Release/EXE.

## پس از اصلاح مودال واقعی: CI محدود دو‌سیستمی موفق
- **کد و تست اصلاح‌شده:** `6990c9259eb23de25cad96a641f57413f6306609`؛ پیام خطای شمع `QMessageBox` واقعی با `DontUseNativeDialog` و `RTL`، آزمون صریح `QTest` با polling کنترل‌شده، بدون حذف/Skip.
- [CI #40659709412](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40659709412): **completed/success** هر دو Job `ubuntu-24.04` و `windows-2022`. هر کدام ۴۷۰ PASS اصلی، ۱۳۰ historical، ۲۶ security، ۸+۸ DPI؛ صفر FAIL/ERROR/SKIP در تمام بسته‌ها. یک هشدار غیرمسدودکننده `fitz` در بسته اصلی. DPI همان آزمون‌های Dock تکراری است.
- JUnit اصلی Linux SHA256 `cb79ed4251c22dc907ea7dc4fbf8b461dd8bbc9245ad912bfdcd2d950e0f9a13` و Windows SHA256 `f55d8295fa57fd0669afd6df36b80444901ba28ffa97fd404ca23dfbf4a4dca5`؛ Artifactها Linux `12803327667` و Windows `12804475174` از همین Run.
- **رگرسیون گسترده روی کد اصلاح‌شده هنوز نهایی نیست**: [Run #40661082617](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40661082617) روی workflow commit `e85fcfbdf990e82d89f28e95a1185821af369c7a`، کد دقیق `6990c925...` را در Linux و Windows native با همان محدودیت ۱۲۰۰/۱۵۰۰ ثانیه آزمون می‌کند. فقط بعد از JUnit/نتیجه دو Job می‌توان PASS/FAIL قطعی داد.
- شکست Run #40656152367 روی کد قدیمی `76969a29...` حفظ و به PASS تبدیل نمی‌شود. UAT فیزیکی Windows، E4 تخصصی بدون قرارداد، E6 مالکیت مشترک، IFC MEP و A2 همچنان بازند؛ نقشه راه ۸ فاز و ۸۵٪ ثابت.

## گیت جدید واقعی ۲۸ اکتبر: رگرسیون گسترده روی E4
Linux روی `76969a29...`: ۸۳۸۰ collected، ۸۳۷۵ PASS، ۵ SKIP مخصوص Windows، صفر FAIL، بدون timeout؛ Artifact `12802725582`، [Run #40656152367](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40656152367). **Windows همان Run پس از ۱۵۰۰ ثانیه FAILED/timeout و JUnit مفقود**؛ روی آزمون واقعی مودال شمع در حدود ۹٪ متوقف شد. آزمون‌ها حذف/Skip نشده‌اند. اصلاح `6990c925...` در [CI اختصاصی #40659709412](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40659709412) شروع شده و تا نتیجه معتبر، NOT VERIFIED است. [گزارش جزئیات](verification-20261028-broad-e4/RESULT.fa.md). PR33/34 Draft، main بدون تغییر، ۸ فاز و ۸۵٪ ثبت‌شده ثابت؛ بدون Merge/Release.

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
