## Qt-owned QFileDialog در Windows و گارد انتخاب فایل

پس از تغییر حداقلی محصول cce78eb، [CIهدفمندWindows40675283022](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675283022) روی همان دو فایل سقف/اصلاحیه **۱۶PASS،۰FAIL/ERROR/SKIP**؛ [artifact/JUnitواقعی](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675283022/artifacts/12810615998)، [metadata](roof-native-cce-success.json). این نتیجه بازآزمایی مستقیم خطای fileNameEdit قبلی است، نه اجرای کل broad.

یک RED کنترل‌شده دیگر نشان داد callback انتخاب فایل اگر قبل از QFileDialog واقعی اجرا شود، فرم والد RoofDetailEditor را به‌اشتباه reject می‌کرد ([JUnit RED](qtfix-file-race-red.xml)). در تست، انتظار محدود برای QFileDialog با والد/عنوان دقیق و دکمه Open واقعی، ورود نام فایل با QTest و بستن صریح خطا جایگزین آن شد. QMessageBoxهای خطای سقف نیز با timer محدود و بررسی والد/عنوان/destination button کنترل می‌شوند، بدون mock یا کلیک روی پنجره نادرست. QTest واقعی، XML/SQLite و assertionهای موجود حفظ‌اند. [بسته مشترک نهایی۲۹PASS،۱warning](qtfix-full-target-green.xml).

کد/تست نهایی `5daf8fbc1c71446afb806d665feb9ab6959367df`، workflow `a99d1a9`؛ [CIهدفمند Windows40675825529](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675825529)، [CIپذیرش40675825474](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675825474)، [CIگسترده40675825520](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675825520) جاری‌اند. هر سه باید مستقل ارزیابی شوند؛ نه Windows broad و نه علت نهایی0xC0000409 تا نتیجه واقعی جدید PASS نامیده نمی‌شوند. سقف۱۵۰۰ثانیه تغییر نکرده است.

---

## ریشه شکست واقعی QFileDialog و بازآزمایی

CIهدفمند [40674791106](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40674791106) روی Windows،JUnitواقعی **۱۰PASS/۱FAIL/۰ERROR/۰SKIP** و هشc44368e8... تولید کرد. خطای ثبت‌شده `AttributeError: NoneType has no attribute setFocus` است: `QFileDialog` بومی Windows، فرزند Qt به نام fileNameEdit را فراهم نکرد و import دیتایل سقف انجام نشد. [متن واقعی notice](roof-native-first-failure.txt)، [metadata](roof-native-first-failure.json)، [artifact واقعی](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40674791106/artifacts/12809414711). علت نخستین FAIL روشن است؛ علت قطعی native crash بعدی جداگانه هنوز از نبودJUnit قابل اثبات نیست.

تغییر حداقلی واقعی محصول `app/roof_detail_editor.py`، تنها در انتخاب فایل JSON دیتایل، `QFileDialog.Option.DontUseNativeDialog` را اعمال می‌کند تا همان فرم Qt و کنترل قابل تعامل و دسترس‌پذیر روی Windows استفاده شود. هیچ mock جای پنجره یا QTest ننشسته و قرارداد فایل/منبع/BOQ تغییر نکرده است. [رگرسیون محلی سقف و شمع۲۴PASS،۱warning](qtfix-roof-native-green.xml). کد جدید cce78eb2b1beb11710a5b29355928e91a653a169، [CIهدفمند Windows40675283022](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675283022)، [CIپذیرش40675283032](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40675283032) درحال‌اجرا هستند؛ Windows جدید تا نتیجه واقعی PASS نیست.

رگرسیون گسترده محلی تکراری source a41cd18، پس از SIGSEGV اول، از ابتدا تکمیل شد: **۸۳۷۵PASS،۰FAIL/ERROR،۱۰SKIP،۳warning** در۵۸۱٫۸۳ثانیه، exit۰،بدونtimeout؛ JUnit/JSON/log واقعی در همین پوشه‌اند. این بازآزمایی SIGSEGV ثبت‌شده اول را محو نمی‌کند. کد cce شامل تغییر محصول بعدی است و به رگرسیون مستقل خود نیاز دارد.

---

## تشخیص مستقل شکست بعدی Windows

در CI40672896854، هر سه پارامتر `test_existing_roof_editor_real_planar_schedule_and_boq` به‌صورت FAIL دیده شدند و سپس subprocess هنگام `test_real_roof_geometry_revision_through_existing_amendment_buttons` با0xC0000409 پایان یافت؛ JUnit کامل ساخته نشد و علت شکست‌ها از خروجی باقی‌مانده مشخص نیست. Linux روی همان دو فایل سقف/اصلاحیه با `--maxfail=1` **۱۶PASS،۱warning** داشت ([JUnit](qtfix-roof-pair.xml)). برای شناسایی **اولین شکست واقعی Windows**، [CI هدفمند40674791106](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40674791106) روی source a41cd18 با Qt native، لاگ و JUnit اصلی و حداکثر۲۴۰ثانیه اجرا می‌شود. این اجرای تشخیصی، broad ناموفق را موفق نمی‌کند و هنوز نتیجه نداده است.

---

## نتایج GitHub روی a41cd18

[پذیرش40672896825](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896825): Linux و Windows هرکدام **۴۸۳PASS،۰FAIL/ERROR/SKIP،۱warning fitz**. historical۱۳۰،security۲۶ و دو تکرار۸تایی DPI در هرسیستم همگی PASS بدون warning. JUnit/تصاویر واقعی در [artifact Linux](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896825/artifacts/12808488866) و [artifact Windows](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896825/artifacts/12809771646)؛ شمارش/hash از notice در [JSON](acceptance-roof-final.json).

[گسترده40672896854](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896854): Linux **۸۳۸۰PASS،۰FAIL،۵SKIP،exit۰،بدونtimeout** از۸۳۸۵ مورد؛ [artifact واقعی Linux](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896854/artifacts/12809727288) و [notice](broad-roof-linux.json). Windows هنوز جاری؛ کل مأموریت تا نتیجه آن و بازرسی artifact PARTIAL است. این موفقیت‌ها SIGSEGV اجرای محلی قبلی را پاک نمی‌کنند.

---

## بازآزمایی مستقل پنج‌طبقه

آزمون `test_real_qt_fourteen_operations_five_floors_and_all_reports` روی همان worktree تمیز a41cd18 به‌تنهایی با faulthandler۶۰ثانیه **۱PASS در۷۵٫۹۶ثانیه** شد؛ [JUnit](qtfix-fivefloor-retry.xml) و log محفوظ‌اند. این بازآزمایی خطای SIGSEGV در broad محلی را رفع‌شده یا بی‌اثر نمی‌کند و علت آن را اثبات نمی‌کند. CI گسترده مستقل همان SHA در جریان است.

---

## رگرسیون محلی سقف: توقف native و نتیجه ناتمام

اجرای گسترده محلی worktree تمیز a41cd18 پیش از رسیدن به آزمون سقف، در `tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports` در حدود۳۴٪ با **pytest_exit_code=-11 (SIGSEGV)،timed_out=false و JUnit مفقود** پایان یافت. faulthandler پس از۶۰ثانیه فقط ابتدای stack را قبل از توقف نوشت؛ از آن علت crash معلوم نیست. log/JSON و شمارش ردیف‌های progress در این پوشه نگه داشته شده‌اند؛ این‌ها نتیجه PASS/FAIL نهایی نیستند. همان سناریو در full منبع قبلی fcf847 PASS شده بود. بازآزمایی مستقل در حال انجام است؛ CI هر دو سیستم جدید نیز جداگانه در حال اجراست.

---

## دومین شکست واقعی Windows و اصلاح سقف PDF

[CI40670626852](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852) روی fcf847: Linux۸۳۷۸PASS/۰FAIL/۵SKIP،بدونtimeout؛ Windows **exit3221226505 / 0xC0000409، `timed_out=false` و JUnit مفقود**. تا حدود۶۱٪ پیش رفت و آخرین سطر قابل مشاهده به `tests/test_phase2_pdf_roof_ui.py::test_actual_pdf_region_to_specialist_bo...` رسید. [JSON notice واقعی](broad-fcf-final.json) و [بخش واقعی قابل مشاهده لاگ](broad-fcf-windows-diagnostic.txt) ذخیره‌اند؛ نوع پارامتر و علت native crash از این سطر ناقص ثابت نمی‌شوند. شمار PASS Windows بدون JUnit معلوم نیست. این run شکست‌خورده است و در اولین timeout شمع باقی نماند.

همان آزمون سقف singleShot(40) داشت و callback بدون کنترل `activeModalWidget()` در finally `roof.reject()` را فراخوانی می‌کرد. [RED کنترل‌شده](qtfix-roof-red.xml) نشان داد تایمر می‌تواند قبل از نمایش RoofDetailEditor مقدار None ببیند. اصلاح حداقلی در خود تست، انتظار محدود برای QDialog فعال با نام RoofDetailEditor و ثبت خطا/cleanup را به کار می‌گیرد؛ Qt اصلی، PDF، SQLite، کلیک‌ها و assertionهای BOQ/مدرک حفظ شده‌اند. رگرسیون سقف/وافل۱۷PASS و رگرسیون مشترک شمع/سقف۲۱PASS، هرکدام۱warningfitz، JUnit واقعی کنار همین گزارش‌اند. این شواهد ریسک مسابقه را اثبات می‌کنند؛ علت دقیق کد 0xC0000409 تا مشاهده اجرای Windows جدید قطعی نیست.

کد/آزمون جدید `a41cd180d1b78b1233a20b4c5d440e93c792cce0`؛ workflow `2f766ca`؛ [CI پذیرش40672896825](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896825) اکنون آزمون واقعی سقف را نیز دارد و [CI گسترده40672896854](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40672896854) بر همان SHA ثابت است. هر دو تا نتیجه واقعی NOT VERIFIED. حدهای قبلی۱۲۰۰/۱۵۰۰ تغییر نکرده‌اند. Linux broad جداگانه در worktree تمیز همین SHA نیز در حال اجرا است.

---

## CI گسترده Linux روی SHA نهایی

[CI40670626852](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852): Linux **۸۳۷۸PASS،۰FAIL،۵SKIP** از۸۳۸۳مورد، exit۰، `timed_out=false` و `overall_green=true`؛ شمارش notice از JSON/JUnit واقعی runner گرفته شده است. این پنج SKIP به PASS تبدیل نمی‌شوند. Windows هنوز جاری است. [شاهد notice](broad-ci-linux.json)؛ JUnit/log محلی همان SHA جداگانه با۱۰SKIP قابل مشاهده است.

---

## پذیرش نهایی fcf847 — هر دو سیستم SUCCESS

[CI40669898079](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898079): Linux و Windows native هرکدام **۴۷۴PASS،۰FAIL/ERROR/SKIP،۱warning fitz**؛ historical۱۳۰،security۲۶ و DPI۱۵۰/۲۰۰ هرکدام۸تکرار در هر سیستم PASS. [شواهد شمارش/hash](acceptance-fcf-final.json). اجرای گسترده40670626852 هنوز مستقل و جاری است؛ تا نتیجه آن کل مأموریت PARTIAL است.

---

## رگرسیون گسترده محلی دقیق fcf847

از worktree تمیز در همان SHA fcf847، runner رسمی با timeout اصلی۱۲۰۰ثانیه تکمیل شد: **۸۳۷۳PASS،۰FAIL،۰ERROR،۱۰SKIP،۳warning** در۵۷۴٫۲۸ثانیه؛ exit۰ و `timed_out=false`. JUnit اصلی [qtfix-final-linux.xml](qtfix-final-linux.xml)، JSON/log اصلی و [اسامی/علت ده SKIP](final-linux-skips.json) موجودند. SKIPها PASS نیستند و هیچ موردی توسط این تغییر اضافه نشد. این نتیجه محلی Windows نیست؛ [CIگسترده40670626852](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852) جداگانه جاری است.

---

## پذیرش SHA نهایی — هر دو سیستم SUCCESS

[CI40669898079](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898079) روی کد fcf847: Linux و Windows هرکدام **۴۷۴PASS،۰FAIL/ERROR/SKIP،۱warning fitz**؛ historical۱۳۰،security۲۶ و DPI۱۵۰/۲۰۰ هرکدام۸تکرار در هرسیستم PASS،صفرFAIL/ERROR/SKIP و بدون هشدار pytest. notices واقعیJunit و digest artifact در [JSON](acceptance-fcf-final.json) ثبت شدند. رگرسیون گسترده40670626852 و بررسی کامل artifact مستقل از این پذیرش هنوز PARTIAL است.

---

## رگرسیون گسترده با تشخیص قابل بررسی

آخرین اجرای گسترده [40670626852](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852)، workflow `0a7decf`، روی کد ثابت fcf847 است و هنوز پایان نیافته. اگر runner شکست/timeout دهد، آخرین بخش همان لاگ واقعی به notice اضافه می‌شود تا محل شکست بعدی بدون دسترسی artifact API قابل بررسی باشد؛ timeout و خروجی اصلی تغییر نکرده‌اند. اجرای واقعی هر دو فرمان تشخیص با لاگ کنترل‌شده و کاراکترهای newline/percent، exit۰ و escaping درست را اثبات کرد. خروجی کامل همچنان در artifact اصلی است. CI پذیرش مستقل40669898079 از workflow قبلیa0cd4c7 روی همین کد fcf847 اجرا می‌شود؛ تغییر بعدی صرفاً diagnostic workflow گسترده است.

---

## آخرین کد و گیت‌های جاری

کد/آزمون نهایی `fcf8472493e842fe707740d2baf166468bf11cdf`، workflow `a0cd4c7`؛ [پذیرش40669898079](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898079) و [گسترده40669898071](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898071) هنوز تکمیل نشده‌اند، حکم نهایی PARTIAL است. متن زیر snapshotهای پیشین را حفظ می‌کند؛ CI موفق۴۷۳ تست مربوط به کد قبلی74cc است، نه SHA جدید.

پس از پذیرش74cc یک حفره در watchdog دیده شد: اگر QTest کلیک را بفرستد اما پنجره بسته نشود، توقف زودهنگام تایمر اجازه انتظار نامحدود می‌دهد. آزمون واقعی Qt با event filter که کلیک را می‌بلعد این حفره را بازتولید کرد:۱RED ([JUnit](qtfix-watchdog-red.xml)). تایمر اکنون پس از کلیک تا بازگشت واقعی modal فعال می‌ماند؛ در deadline با خطای صریح و cleanup خاتمه می‌دهد. suite هدفمند۱۰PASS ([JUnit](qtfix-watchdog-green.xml))؛ بدون حذف/Skip و بدون افزایش timeout گسترده.

---

# اصلاح Timeout پنجره Qt شمع — ۲۸ اکتبر ۲۰۲۶

**وضعیت: PARTIAL تا اتمام و بازرسی CI.** کد/آزمون واقعی روی PR34 اعمال و push شده است. SHA آزمون‌شونده `74cc37d68c35a0a113643e7538d9dce3378e3597`؛ workflow روی همان SHA ثابت است. [پذیرش مستقل](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40668037315) و [رگرسیون گسترده](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40668037298) آغاز شده‌اند؛ تا تولید نتیجه نهایی شمار Windows/Linux ادعا نمی‌شود.

در اجرای قبلی [40661082617](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40661082617) گزارش تحویل ثبت کرده Windows در `QMessageBox.exec` خط۱۴۱ و هنگام آزمون واقعی amendment با timeout۱۵۰۰ و exit۱۲۴ و JUnit مفقود مانده است. کد همان محل پنجره هشدار Qt با نام `BoredPileErrorMessage`، عنوان `کنترل دیتایل شمع` و دکمه Ok را می‌سازد. از stack به‌تنهایی اثبات نمی‌شود تایمر ۱۰ms علت قطعی Windows بوده است. درخواست مستقیم دریافت Artifact قبلی از API با Forbidden/credential نامعتبر مواجه شد؛ در این نوبت محتویات بایگانی را مستقیماً بازخوانی نکردیم و ادعای خلاف آن نداریم. [Artifact قبلی](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40661082617/artifacts/12805470944).

بازپخش کنترل‌شده با پنجره واقعی QMessageBox، نمایش تأخیری ۸۰ms و تایمر قبلی ۱۰ms نشان می‌دهد callback پیش از باز شدن پنجره اجرا می‌شود: [RED واقعی exit1](qtfix-old-timer-red.log)، [اسکریپت](qtfix-old-timer-repro.py). این امکان مسابقه را اثبات می‌کند؛ علت دقیق timeout Windows تا نتیجه اجرا هنوز فرضیه است.

تست واقعی با QTimer تکرارشونده و deadline محدود، فعال بودن QMessageBox، نام، عنوان، والد واقعی و دکمه استاندارد مورد انتظار را بررسی کرده و از QTest.mouseClick استفاده می‌کند. برای خطای amendment دکمه Ok و برای تأیید خروج بدون ذخیره دکمه Yes است؛ حالت پنجره غیرمنتظره بدون کلیک دکمه نامرتبط با خطای صریح پایان می‌یابد. انتظار نمایش فرم والد/شمع نیز محدود و به نام اصلی متصل است. در مسیر شکست فقط cleanup کنترل‌شده پنجره اجازه بازگشت pytest می‌دهد و شکست پنهان نمی‌شود. کد محصول، SQLite، CAS، شمار revision، رد مالکیت، BOQ و assertionهای قبلی محفوظ‌اند.

اجرای محلی واقعی Qt offscreen: [۹ PASS، صفر FAIL/ERROR/SKIP](qtfix-targeted.xml)، شامل آزمون جدید تأخیر و پنجره نامرتبط و suiteهای amendment/controller. Windows native و رگرسیون گسترده، تا گزارش مستقل GitHub در این checkpoint NOT VERIFIED است. نه Merge/ForcePush/main/Release/EXE و نه P6-6/فاز۷؛۸فاز و۸۵٪ حفظ است.

## رگرسیون محلی نسخه میانی

رگرسیون جاری محلی روی کد میانی1a37ec0 (پیش از کنترل والد در74cc37d) تکمیل شد:۸۳۷۱PASS،۱FAIL،۰ERROR،۱۰SKIP،۳warning؛۶۰۵٫۱۸ثانیه،بدونtimeout. شکست `tests/test_beam_historical_migration.py::test_migration_two_process_sqlite_cas[False]` از نوع `_queue.Empty` است. اجرای مستقل مجدد همان مورد۱PASS در۰٫۸۰ثانیه داشت؛ این نتیجه جداگانه، شکست full را حذف یا علت قطعی آن را ثابت نمی‌کند. XML/JSON/log اصلی و JUnit بازآزمایی در همین پوشه‌اند. این snapshot جای CI کد نهایی را نمی‌گیرد.

## CI پذیرش نهایی

[CI40668037315](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40668037315) SUCCESS: هر سیستم Linux و Windows native،۴۷۳PASS اصلی،۱۳۰تاریخی،۲۶security و۸+۸تکرارDPI، همگی صفرFAIL/ERROR/SKIP؛۱هشدارfitz در اصلی و۰ در دیگر مراحل. نسخه workflow b423fcf و کد/آزمون74cc37d یکسان‌اند؛ این بسته شامل آزمون واقعی شمع اصلاح‌شده است. هش JUnitهای واقعی از notices و artifact metadata در acceptance-ci-measured.json ثبت شده‌اند. رگرسیون گسترده هنوز باید جداگانه تمام شود؛ اینCIجای آن را نمی‌گیرد.

اجرای محلی74cc پیش از اتمام برای جایگزینی با source جدید fcf847، با SIGTERM روی همان subprocess آزمون متوقف شد؛ خروجی partial و JSON بدونJUnit ثبت شدند و PASS/FAIL نهایی نیستند. اجرای جدید محلی از worktree تمیز source fcf847 انجام می‌شود.

## اجرای گسترده superseded 74cc

Run40668037298 بعد از اصلاح watchdog جایگزین و Cancel شد؛ نتیجه نهایی قابل پذیرش نیست. notice عمومی Windows کد subprocess **3221226505 (0xC0000409)**، `timed_out=false` و JUnit مفقود را ثبت کرده است. علت این کد و نسبت آن با لغو از notice به‌تنهایی روشن نیست؛ نه PASS است و نه به مسابقه تایمر نسبت داده می‌شود. [اطلاعات ثبت‌شده](superseded-broad-ci.json). اجرای fcf847 مستقل ادامه دارد و Windows آن باید تعیین تکلیف شود.

رگرسیون محلی تمام۲۱فایل `tests/test_bored_pile*.py` روی کدfcf847: **۳۵۱PASS،۰FAIL/ERROR/SKIP،۰warning** در۴٫۷۳ثانیه؛ [JUnit](qtfix-bored-pile-suite.xml) و log اصلی محفوظ‌اند. این آمار شامل۱۰تست هدفمند است و نباید دوباره جمع شود.

## شاهد جزئی CI نهایی fcf847

Linux پذیرش40669898079:۴۷۴PASS،صفرFAIL/ERROR/SKIP،۱warningfitz؛ تاریخی۱۳۰،security۲۶،DPI۱۵۰و۲۰۰ هرکدام۸PASS. Windows همان run همچنان درحال‌اجراست؛ شمار آن حدس زده نشده است. [JSON شاهد جزئی](acceptance-fcf-partial.json).

## پیوند مستقیم artifactهای اجراهای ثبت‌شده

- پذیرش نهایی fcf847،[JUnit و شواهد Linux](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898079/artifacts/12807568509)،[JUnit و شواهد Windows](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40669898079/artifacts/12808760306).
- اجرای گسترده fcf847،[Linux](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852/artifacts/12808737175)،[Windows شکست‌خورده](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40670626852/artifacts/12808327783). Windows JUnit تولید نکرد؛ artifact شامل لاگ/JSON آن اجراست.

این شناسه‌ها از metadata عمومی همان صفحات واقعی آمده‌اند؛ دانلود ZIP از این محیط به دلیل Forbidden GitHub API انجام نشد.
