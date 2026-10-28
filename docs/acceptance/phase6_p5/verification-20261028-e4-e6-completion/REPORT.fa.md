# نتیجه نهایی این مأموریت — PARTIAL

اصلاحات قابل‌اثبات و مجاز E4/E6 پیاده‌سازی و روی Linux/Windows آزموده شدند؛ source نهایی **`cd855297af657a382c76909eabad7523688148a2`** است. HEAD اولیه **`d242797c2595938ad5be5baa25c27e783a15a324`** بود؛ HEAD کد/CI هنگام راستی‌آزمایی **`b2264832013f243d186aa2eeea9663c9a0246aa0`** است. commit پایانی شواهد کد آزموده‌شده را تغییر نمی‌دهد؛ HEAD پس از push در پاسخ نهایی و بررسی مستقل post-push ثبت می‌شود.

- کد محصول E4/E6: `aecf184424e944f4409800e50df5652f2a574c34`؛ کنترل اندیس معتبر Qt، حفظ CAS اصلی حین callback و محافظ زمینه IFC در Preview/Apply/Migrate.
- تقویت fixture سقف: `cd855297af657a382c76909eabad7523688148a2`؛ مشاهده هویت/دکمه واقعی پیش از QTest و cleanup محدود در همان مهلت۱ثانیه‌ای، بدون حذف assertion یا افزایش timeout.
- [هدفمند نهایی40749023272](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749023272): هر محیط159PASS، صفرFAIL/ERROR/SKIP و JUnit معتبر.
- [پذیرش جامع40749023450](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749023450): هر محیط515PASS اصلی +130تاریخی +26امنیت +8DPI150 +8DPI200، صفرFAIL/ERROR/SKIP؛ یک هشدار fitz در بسته اصلی.
- [رگرسیون کامل Windows40749998943](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943) و [بازآزمایی کامل Linux/Union40751958863](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751958863) روی **همان source**؛ job `verify-full-union` **SUCCESS**.

| محیط نهایی | PASS | FAIL | ERROR | SKIP | Exit | Timeout | JUnit |
|---|---:|---:|---:|---:|---:|---|---|
| Linux کامل، اجرای تازه | 8418 | 0 | 0 | 5 | 0 | false | معتبر |
| Windows shard0 | 2645 | 0 | 0 | 1 | 0 | false | معتبر |
| Windows shard1 | 3185 | 0 | 0 | 3 | 0 | false | معتبر |
| Windows shard2 | 2586 | 0 | 0 | 3 | 0 | false | معتبر |
| مجموع Windows | 8416 | 0 | 0 | 7 | 0 | false | سه XML معتبر |

**Union=8423 testcase یکتا،707ماژول،صفرDuplicate/Missing/Extra**. این تعداد testcase است، نه تعداد سناریوی مستقل مهندسی. manifest ماژول‌ها `e89de674e5fe212c3472b6e629eea6f23dc1fb8617e41ffee7de26524efde54a` است. XML/JSON/log اصلی هر چهار Artifact در گیت Union دانلود و بازخوانی شدند؛ هر فایل SHA256 مستقل دارد و tail واقعی log/علت SKIP در `final-union-inspected.json` ثبت است.

[Linux JUnit/JSON/log12844019387](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751958863/artifacts/12844019387)؛ [Windows0=12845415127](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943/artifacts/12845415127)؛ [Windows1=12842659855](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943/artifacts/12842659855)؛ [Windows2=12845050524](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943/artifacts/12845050524)؛ [Union و گزارش بازرسی12844708189](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751958863/artifacts/12844708189).

**علت PARTIAL:** E4/E6/W1 در کل هنوز قراردادهای فاقد سند دارند، A2 فاقد دارایی واقعی/مجوز معتبر است، UAT فیزیکی مستقل انجام نشده و علت دقیق SIGSEGV قبلی Linux اثبات نشده است. اجرای تازه Linux با همان کد8418PASS شد و بازتولید هدفمند22PASS بود؛ این شواهد علت crash قبلی را رفع‌شده ثابت نمی‌کنند. run40749998943 به علت SIGSEGV Linux همچنان **Failure** است؛ آن نتیجه و JUnit مفقودش حذف یا PASS نشده‌اند. هیچ اصلاح حدسی روی محصول/پاکسازی عمومی Qt اعمال نشد.

PR33/34 طبق بررسی تازه **Open/Draft/Unmerged**؛ main=`9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` و PR33=`c859cebccf83a43e456e73377bb2dea764e00823` ثابت. PR34 با base=PR33 دو تعارض واقعی add/add در `scripts/phase6_acceptance_summary.py` و `scripts/run_phase6_pytest.py` دارد؛ فقط بررسی و پیشنهاد انجام شد. Merge/Rebase/ForcePush/main/Release/installer/EXE/P6-6/فاز۷ انجام نشد. فاز۶/P6-5، نقشه راه۸فاز و پیشرفت ثبت‌شده۸۵٪ ثابت است.

اقدام بعدی محدود: قرارداد و سند مستقل مالکیت مشترک/inverse Crosswalk/مقصد تخصصی DWG و IFC؛ دارایی واقعی A2 با منشأ/مجوز/runtime/inference و Human Review؛ UAT مالک؛ و capture native backtrace در صورت بازتولید crash. رفع تعارض فقط در مأموریت دارای مجوز مستقل مجاز است. سایر کارهای مستقل مجاز این نوبت انجام شدند.

---

وضعیت‌های درحال‌اجرا در تاریخچهٔ زیر، متعلق به لحظهٔ ثبت همان checkpoint هستند؛ نتیجهٔ نهایی بالای این فایل مرجع است.

# تکمیل محدوده معتبر E4/E6 — ۲۸ اکتبر ۲۰۲۶

وضعیت مأموریت **PARTIAL** است؛ CI اولیه هدفمند و جامع موفق بودند، ولی رگرسیون کامل یک نقص واقعی در fixture مودال Windows پیدا کرد. اصلاح و RED/GREEN آن ثبت شده؛ CI source نهایی تا پایان واقعی باز است. این گزارش تعداد testcase را ثبت می‌کند، نه شمار سناریوهای مستقل مهندسی.

## هویت و محدوده

- HEAD اولیه بازیابی‌شده از remote: `d242797c2595938ad5be5baa25c27e783a15a324`.
- RED source: `535abd97683f9792d9853dc49af672bbabfe0764`؛ فقط دو ماژول آزمون به کد اولیه افزوده شده‌اند.
- source اصلاح محصول E4/E6: `aecf184424e944f4409800e50df5652f2a574c34`.
- source نهایی شامل تقویت fixture مودال: `cd855297af657a382c76909eabad7523688148a2`. source محصول app/core با aecf184 یکسان است؛ آزمون سقف بعداً تقویت شد.
- commit اجرای CI هدفمند: `c1e28be25fc73d77946490a888499c8c289f4a78`؛ پس از source فقط workflow تغییر کرده است.
- commit workflow رگرسیون کامل: `1300eaa`؛ checkout محصول/آزمون هر چهار job و validator روی source بالا قفل است.
- اختلاف محصول/آزمون E4/E6 اولیه با HEAD اولیه: ۴ فایل، ۱۶۰ خط افزوده و۸ خط حذف‌شده؛ fixture سقف پس از شکست CI جداگانه تقویت شد. اختلاف تجمیعی با merge-base شاخه PR33:۳۸۴ فایل؛ با main:۲۱۸۲ فایل؛ عمده این اختلاف تاریخچه توسعه/شواهد پیشین است و معادل تغییر جدید این مأموریت نیست.
- شاخه همان `feature/phase6-p5-workspace-e3-e6-20261027` است. remote پیش از push بررسی شد و push عادی بدون بازنویسی پذیرفته شد.
- فاز فعلی ۶، اولویت P6-5؛ نقشه راه دقیقاً ۸ فاز و پیشرفت ثبت‌شده کل پروژه ۸۵٪ ثابت است. هیچ Merge/Rebase/ForcePush/Release/EXE/P6-6/فاز۷ انجام نشده است.

## نقص‌های اثبات‌شده و اصلاح حداقلی

۱. `app/project_search_panel.py`: اندیس `-1`، `True` یا اندیس معتبر متعلق به ردیف دیگر در UserRole می‌توانست مقصد واقعی متفاوتی را باز کند. اکنون نوع دقیق int، دامنه و تطبیق شماره ردیف QListWidget با نتیجه کنترل می‌شود؛ انتخاب نامعتبر با پیام صریح لغو می‌شود.

۲. همان فایل: callback می‌توانست پروژه را تغییر دهد و جست‌وجو را دوباره اجرا کند؛ مقایسه با `self.digest` جدید، CAS اولیه را از بین می‌برد. اکنون توکن پیش از ناوبری در متغیر محلی ثابت می‌ماند و قبل/بعد از callback عمومی و IFC کنترل می‌شود. قرارداد `None` موفق legacy و `False` صریح ناموفق محفوظ است؛ Exception پیام موفقیت نمی‌دهد.

۳. `app/ifc_lineage_controls.py`: محافظ زمینه زنده فقط Undo/Redo را شامل می‌شد. Apply و Migrate پس از تغییر پروژه، Revision یا مسیر IFC نمایان همچنان مالکیت یا Crosswalk را در SQLite ثبت می‌کردند. همان محافظ موجود به Preview/Apply/Migrate گسترش یافت. هیچ مقدار، سهم، هندسه یا نگاشت جدید ساخته نشده است.

آزمون‌های جدید در `tests/test_phase6_p5_e4_identity_generation.py` و `tests/test_phase6_p5_e6_live_context.py` هستند. QTest واقعی، فرم اصلی GraphicalTakeoffDialog، IFC مصنوعی معتبر با منشأ و بازبینی مستقل صریح و SQLite واقعی به کار رفته‌اند. آزمون‌های قبلی حذف یا ضعیف نشده‌اند. تغییر مهندسی و مالی ناخواسته، Digest، شمار revisions، integrity و Reopen در مسیرهای رد کنترل می‌شوند.

## RED و GREEN محلی

| اجرا | PASS | FAIL | ERROR | SKIP | شاهد |
|---|---:|---:|---:|---:|---|
| RED واقعی | ۰ | ۱۱ | ۰ | ۰ | `p6-e4e6-red-final.xml` و log |
| GREEN همان ۱۱ حالت | ۱۱ | ۰ | ۰ | ۰ | `p6-e4e6-green.xml` |
| رگرسیون مرتبط E4/E6/Split/Merge | ۱۴۹ | ۰ | ۰ | ۰ | `p6-e4e6-related.xml`؛ یک هشدار fitz |
| مرز مالکیت مشترک و GGUF | ۱۸۸ | ۰ | ۰ | ۰ | `p6-contract-boundaries.xml` |
| رگرسیون کامل محلی snapshot aecf184 | ۸۴۱۲ | ۰ | ۰ | ۱۰ | `p6-e4e6-broad-local.xml.gz`؛ ۶۵۷٫۰۶ثانیه،۳warning،exit=0،timeout=false |

اجراهای هدفمند محلی با بایت‌های محصول/آزمون متناظر source ثبت‌شده، پیش از commit اجرا شدند. رگرسیون کامل محلی پس از commit source در کپی موقت runner اجرا شد. هر۸۴۲۲ testcase اصلی JUnit مستقل شمارش شد، شناسه تکراری ندارد و حفظ bytes پس از gzip کنترل شد. پنج skip اضافی محلی ناشی از نبود PowerShell است؛ نتیجه Windows بومی از این اجرا استنتاج نمی‌شود. CI pinned مستقل برای source تمیز انجام می‌شود. اعداد بسته‌های هم‌پوشان جمع سناریوهای مستقل نیستند. هش فایل‌ها در `local-measured.json` و `SHA256SUMS` است.

## بازبینی مستقل

طبق مهارت [requesting-code-review](skill://plugins~Plugin_60aea7460bd4819199fd97a9553a5e12/requesting-code-review/SKILL.md)، بازبین مستقل diff را بدون تغییر فایل/شاخه بررسی کرد؛ یافته قابل اقدام Critical/Important/Minor گزارش نشد. ۲۲ آزمون باریک مستقل با Qt/SQLite واقعی در ۳٫۰۶ ثانیه PASS شدند. این بازبینی مجوز Merge یا پذیرش CI ناتمام نیست. پوشش منفی Preview و الزام generation مستقل وقتی Digest تغییر نکرده صرفاً پیشنهاد اختیاری بود؛ پیش‌نمایش read-only و محافظ مشترک mutation آزموده شده و قرارداد generation جدید تعریف نشد.

## GitHub Actions و رگرسیون کامل

- هدفمند pinned source: [40745562636](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40745562636)، **SUCCESS**: Linux۱۴۹PASS و Windows۱۴۹PASS، صفرFAIL/ERROR/SKIP، JUnit معتبر. [Artifact Linux12841022909](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40745562636/artifacts/12841022909)، [Artifact Windows12840759510](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40745562636/artifacts/12840759510).
- پذیرش جامع E3–E6: [40745562892](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40745562892)، **SUCCESS هر دو سیستم**: هر محیط۵۱۴PASS اصلی +۱۳۰تاریخی +۲۶امنیت +۸DPI150 +۸DPI200، صفرFAIL/ERROR/SKIP؛ یک هشدار fitz در بسته اصلی. [Artifact Linux12842046209](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40745562892/artifacts/12842046209)، [Artifact Windows12841144041](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40745562892/artifacts/12841144041). کد محصول و آزمون checkout commit `c1e28be...` با source `aecf184...` دقیقاً یکسان است؛ فقط workflow فرق دارد.
- رگرسیون کامل source جدید و Union: [40746431177](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40746431177)، پس از SUCCESS هدفمند دو سیستم آغاز شد؛ تا اجرای کامل و JUnit جدید، نتیجه قبلی به source جدید تعمیم داده نمی‌شود.
- مرجع اولیه مستقل [40719136460](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40719136460) روی `426c485...`: Linux 8406PASS/5SKIP، Windows 8404PASS/7SKIP، صفر FAIL/ERROR/Timeout؛ Union=8411 testcase/705 ماژول. این نتیجه متعلق به source قبلی است.

## CI نهایی پس از تثبیت fixture

- source نهایی: `cd855297af657a382c76909eabad7523688148a2`.
- رگرسیون مرتبط محلی نهایی:۱۵۹PASS، صفرFAIL/ERROR/SKIP و۱warning fitz،۵۴٫۷۵ثانیه؛ JUnit `p6-e4e6-stable-related.xml`.
- هدفمند Windows/Linux: [40749023272](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749023272)، **SUCCESS**، هر محیط۱۵۹PASS و صفرFAIL/ERROR/SKIP؛ JUnit معتبر. [Artifact Linux12841619350](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749023272/artifacts/12841619350)، [Artifact Windows12843915525](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749023272/artifacts/12843915525).
- پذیرش جامع دو سیستم: [40749023450](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749023450)، **SUCCESS**، هر محیط۵۱۵PASS اصلی +۱۳۰تاریخی +۲۶امنیت +۸DPI150 +۸DPI200، صفرFAIL/ERROR/SKIP و JUnit معتبر؛ یک هشدار fitz در بسته اصلی. [Artifact Linux12842119720](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749023450/artifacts/12842119720)، [Artifact Windows12842379948](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749023450/artifacts/12842379948). کد app/core/tests/scripts در checkout workflow `0a82cc7...` با source نهایی `cd85529...` یکسان است.
- full Linux/سه shard Windows/Union جدید: [40749998943](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943)، workflow `acb0fa4` و source pinned `cd855297af657a382c76909eabad7523688148a2`؛ پس از SUCCESS هدفمند آغاز شد. اجرای قدیمی FAIL به‌عنوان شاهد باقی می‌ماند.

## شکست بعدی Windows و رفع fixture، بدون پنهان‌کردن نتیجه

در [40746431177](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40746431177) روی aecf184، shard1 ویندوز **3183PASS/1FAIL/3SKIP، exit1، timeout=false** شد؛ JUnit واقعی موجود است: [Artifact12843025787](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40746431177/artifacts/12843025787). نام شکست `test_delayed_roof_modal_is_seen_even_if_construction_is_slow` بود. state.started=False؛ این نتیجه FAIL است و پذیرفته یا حذف نشده است. Linux همان source8417PASS/5SKIP شد؛ Windows shard0=2645PASS/1SKIP، shard1=3183PASS/1FAIL/3SKIP و shard2=2586PASS/3SKIP. همه exit واقعی و JUnit دارند و timeout=false است؛ verify-full-union به علت FAIL اجرا نشد. این نتایج به source نهایی تعمیم داده نمی‌شوند.

علت fixture: خود آزمون پنجره را با singleShot20ms می‌بست، درحالی‌که poll20ms و quit180ms می‌توانستند فرصت مشاهده را از بین ببرند. با first-poll120ms، همان assertion پیش از اصلاح به‌صورت قطعی RED شد (`p6-roof-self-dismiss-red.xml`:1FAIL). اکنون موفقیت فقط بعد از هویت دقیق همان QDialog و مشاهده دکمه Close واقعی visible/enabled و کلیک QTest مجاز است؛ خروج حلقه با برگشت exec هماهنگ است. مهلت۱ثانیه‌ای افزایش نیافت.

بازبین مستقل، پوشیده‌شدن سقف با مودال تو‌در‌تو را نیز بازتولید کرد: helper پس از بستن مودال رویی متوقف می‌شد و سقف می‌ماند؛ اجرای مستقل بیرونی در۴ثانیه exit124 داشت. timer پاکسازی owned در همان مهلت1000ms اضافه شد که هم مودال فعال و هم سقف شناخته‌شده را می‌بندد و خطای صریح ثبت می‌کند. این مسیر هرگز موفقیت محسوب نمی‌شود. `p6-roof-nested-red.json` و `p6-roof-nested-green.json` نشان می‌دهند بعد از اصلاح assertion صریح و activeModal=None با exit0 از اسکریپت تشخیص ثبت شد. یک آزمون Qt واقعی جدید همین حالت خطا را کنترل می‌کند. تمام فایل سقف10PASS (`p6-roof-self-dismiss-final.xml`)، با یک هشدار fitz شد. این timeout مربوط به بازتولید محلی کنترل‌شده است؛ run ویندوز timeout نداشت.

## توقف native Linux پس از اصلاح Windows

در [40749998943](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943) روی source نهایی cd85529، Linux با **exit=-11/SIGSEGV، timeout=false، JUnit مفقود** متوقف شد. [Artifact اصلی12842899022](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943/artifacts/12842899022) شامل JSON/log واقعی است؛ این قسمت FAIL/NOT VERIFIED است و تعداد PASS نهایی برای آن ساخته نمی‌شود. Windows همان source هر سه shard را با JUnit واقعی تمام کرد: shard0=2645PASS/1SKIP، shard1=3185PASS/3SKIP و shard2=2586PASS/3SKIP؛ جمع8416PASS/7SKIP و صفرFAIL/ERROR/Timeout، exit0. [Windows0 Artifact12845415127](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943/artifacts/12845415127)، [Windows1 Artifact12842659855](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943/artifacts/12842659855)، [Windows2 Artifact12845050524](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943/artifacts/12845050524). خود این run در مجموع به علت Linux همچنان Failure است و Union آن اجرا نشد.

آخرین لاگ در حدود۳۴٪ به `tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports` می‌رسد. faulthandler60s فقط نمونه stack است، نه حد timeout testcase؛ همین پیام در رگرسیون محلی موفق هم وجود دارد. stack موجود پس از `posixpath.join` و آغاز frame بعدی قطع شده و محل crash native را ثابت نمی‌کند. فایل‌های این مسیر و cleanup آن از source قدیمی a41 تا cd85529 تغییر نکرده‌اند؛ این به‌تنهایی علت یا بی‌اثربودن تغییرات دیگر را ثابت نمی‌کند.

بررسی مستقل یک مسئله چرخه‌عمر قدیمی را بازتولید کرد: سه تست فرم قبلی پس از close/deleteLater/processEvents به‌ترتیب۱/۲/۳ فرم پنهان و timer فعال باقی می‌گذارند؛ ارسال DeferredDelete تعداد را به صفر می‌رساند. ارتباط علّی این مسئله با SIGSEGV اثبات نشده؛ اصلاح حدسی روی محصول یا conftest انجام نشد.

[تشخیص Artifact و بازتولید همان SHA40751306233](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751306233) **SUCCESS،22PASS/صفرFAIL/ERROR/SKIP** شد؛ ماژول‌های بلافاصله پیشین و آزمون متوقف‌شده بدون تغییر assertion اجرا شدند. [Artifact12843891778](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751306233/artifacts/12843891778). فایل اصلی log داخل CI واقعاً بازخوانی شد:348292byte، SHA256=`ec99df2884f7c5bf7ed8e94d71312a11b7a332e89566386a4731aa2ddfa652ef`؛ JUnit اصلی موجود نیست. stack واقعاً در همان frame ناقص قطع شده است. PASS این22آزمون علت crash کامل را تعیین نمی‌کند. بازآزمایی کامل فقط Linux روی همان source در [40751958863](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751958863) با ثبت backtrace native و Union از Windows همان SHA جدا اجرا می‌شود؛ core حافظه منتشر نمی‌شود و فقط backtrace بدون آرگومان frame ممکن است ثبت شود. تکرار موفق به‌تنهایی اثبات رفع علت نیست.

## ماتریس پذیرش و پیش‌نیازهای بیرونی

| گیت | وضعیت | پذیرفته‌شده/مرز باقی‌مانده |
|---|---|---|
| E4 | PARTIAL | ناوبری شناسه واقعی، CAS، رکورد یکتا، callback و نشست PDF/DXF معتبر در محدوده قرارداد موجود آزموده شده؛ قرارداد مقصد تخصصی همه خانواده‌ها هنوز کامل نیست |
| E6 | PARTIAL | Split/Merge دارای QTO و جدول تخصیص مستقل، Undo/Redo الحاقی، SQLite/CAS، تاریخچه و کنترل زمینه واقعی موجود؛ این پذیرش معادل تخصیص اشتراک فیزیکی دلخواه نیست |
| W1 | PARTIAL | مسیرهای موجود فرم‌های اصلی و IFCهای آزمایشی معتبر محفوظ؛ IFC MEP و نگاشت همه زیرگونه‌ها بدون قرارداد مستقل تأیید نمی‌شوند |
| A2 | BLOCKED | manifest مدل واقعی هش و مجوز نمونه دارد؛ وزن GGUF در مسیرهای بررسی‌شده یافت نشد و `llama_cpp` نصب نیست؛ آزمون مرز نرم‌افزار، inference واقعی را ثابت نمی‌کند |
| گیت‌های مشترک | PARTIAL | CI/Union جدید باید کامل شوند؛ UAT فیزیکی Windows و تأیید مهندسی مالک مستقل است |

پیش‌نیازهای دقیق:

- DWG عمومی: مدرک تبدیل معتبر با هویت فایل اصلی/خروجی، SHA، Revision و منشأ تأییدشده؛ بدون آن مسیر تخصصی مسدود است.
- IFC تخصصی Beam/Column/MEP/Roof/Report از جست‌وجو: قرارداد مقصد با شناسه رکورد/عضو، نگاشت Crosswalk و بازبینی مستقل معتبر؛ نام یا هندسه به‌تنهایی مجوز انتساب نیست.
- اشتراک بتن/میلگرد/پوشش بین چند عضو: شناسه فیزیکی جزء و مالک پرداخت، جدول مقدار/سهم صریح و مستند، منشأ و بازبینی مستقل و مجوز تغییر BOQ مالی لازم است. preflightهای فعلی read-only هستند؛ نتیجه بدون سند `BLOCKED_FOR_COMMIT` باقی می‌ماند.
- inverse Crosswalk مهاجرت‌کرده: سند مستقل نگاشت معکوس شامل شناسه‌های قبلی/جاری، نشست/آیتم، SHA/Revision و تأیید مستقل لازم است؛ Undo مالکیت اجازه اختراع این قرارداد را نمی‌دهد.
- A2: وزن واقعی، runtime قابل اجرا، منشأ، SHA معتبر، مجوز تجاری/توزیع و آزمون inference واقعی با Human Review؛ هیچ مدل یا مجوزی در این مأموریت حدس یا دانلود نشده است.
- Windows فیزیکی: دو نمایشگر، GPU مشتری و Sleep/Resume با UAT مالک همچنان جداست.

## بررسی تعارض PR34 — فقط بررسی

base واقعی PR34 شاخه `feature/phase6-p4-contextual-wizard-20261026` با HEAD `c859cebccf83a43e456e73377bb2dea764e00823` (PR33) است؛ base اصلی `main` نیست. merge-base برابر `241dd15e3e5c3c572f94237da5146ceb04dc9dbf` و در نقطه شروع PR34 تعداد۱۵۲ commit جلو و۴۱ commit عقب بود.

`git merge-tree --write-tree HEAD origin/p6-base` بدون تغییر شاخه/working tree، دو تعارض واقعی add/add نشان داد:

- `scripts/phase6_acceptance_summary.py`
- `scripts/run_phase6_pytest.py`

فایل `base-merge-tree-conflicts.txt` خروجی اصلی را نگه می‌دارد. هر دو شاخه ابزارها را مستقل افزوده‌اند. سمت P5 شمارش هشدار هر مرحله و مسیر log از `PHASE6_PYTEST_LOG_PATH` را دارد؛ کنارگذاشتن این رفتار می‌تواند شاهد مراحل را مخلوط کند. `main` جد مستقیم source فعلی است و مقایسه با آن تعارض ندارد؛ مشکل از واگرایی PR33/base است. هیچ تعارضی حل و هیچ شاخه‌ای merge/rebase نشده است.

پیشنهاد کم‌ریسک برای نوبت دارای مجوز مستقل: ادغام عادی base/PR33 در checkout موقت PR34، حل فقط دو تعارض با حفظ رفتارهای لازم هر دو شاخه، اجرای آزمون ابزار و Qt دو سیستم و ثبت نتیجه بدون بازنویسی تاریخچه. این پیشنهاد مجوز اجرا نیست و در این مأموریت ادغام ممنوع باقی می‌ماند. صرف افزودن یک commit ویرایش متن روی PR34 تضمین نمی‌کند تعارض add/add ناشی از ancestry برطرف شود؛ راهکار نباید با از دست‌دادن log هر مرحله تعارض را ظاهراً پاک کند.

## حدود دسترسی به شواهد

Git read/push از مسیر مجاز موجود کار می‌کند. GitHub API در محیط فعلی `Forbidden` برمی‌گرداند؛ دانلود مستقیم ZIPهای CI ادعا نشده است. گیت verify-full-union در خود GitHub Actions، Artifactهای اصلی همین اجرا را دانلود می‌کند و XML/JSON/log را بازخوانی، شمارش و SHA256 می‌کند؛ خروجی عمومی محاسبه‌شده و لینک Artifactها در این پوشه نگه‌داری می‌شود. JUnit و log محلی نیز فایل اصلی واقعی‌اند.

## فهرست تغییرات این مأموریت

محصول: `app/project_search_panel.py` و `app/ifc_lineage_controls.py`. آزمون: دو ماژول جدید E4/E6 که در بخش نقص‌ها نام برده شدند. CI: سه workflow هدفمند/پذیرش/رگرسیون کامل. شواهد: همین پوشه و `CONTINUE.fa.md`. فهرست مسیرهای کامل در `changed-files.txt` و بایت‌های شواهد در `SHA256SUMS` ثبت می‌شود. فقط fixture مودال سقف در یک فایل آزمون قبلی تقویت شد؛ نام و assertionهای اصلی حفظ شدند و یک آزمون تو‌در‌تو افزوده شد. هیچ testcase قبلی حذف یا Skip/XFail نشد.

## بررسی نهایی PR و مبنای انتشار

پس از تغییرات کد/CI، `post-change-verification.json` با Git remote و HTML تازه تأیید کرد: PR33 و PR34 هر دوDRAFT/Open با closedTime=null و mergedTime=null؛ main=`9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` و PR33=`c859cebccf83a43e456e73377bb2dea764e00823` بدون تغییرند. HEAD هنگام این بررسی `b2264832013f243d186aa2eeea9663c9a0246aa0` است؛ commit پایانی فقط شواهد را تکمیل می‌کند و post-push جدا بررسی می‌شود. `final-base-merge-tree-conflicts.txt` همان دو تعارض را دوباره نشان داد و `PR34-base-diff-stat.txt` اختلاف واقعی شاخه با base را در این snapshot ثبت می‌کند. Release/installer/EXE یا تغییر main انجام نشد.

## ادامه اجرایی

تکمیل و بررسی CI هدفمند Windows/Linux، پذیرش جامع و رگرسیون کامل pinned با سه shard ویندوز و verify-full-union؛ سپس ثبت شمارش و هش Artifactها و کنترل دوباره PR33/34/main. تا آن زمان هیچ گیت باز PASS اعلام نمی‌شود.
