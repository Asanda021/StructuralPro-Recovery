# تصمیم نهایی فنی فاز ۶ — مأموریت ۲۹ اکتبر ۲۰۲۶

**PHASE 6 PARTIAL / NO-GO**

مشکل واقعی خواندن Placement بهداشتی اصلاح و شواهد RED/GREEN حفظ شد. پایان فاز ۶ اعلام نمی‌شود: پذیرش منبع مستقل محوطه/بازسازی در قرارداد مصوب هنوز اثبات نشده و UAT سخت‌افزار Windows مالک انجام نشده است. این‌ها همان دامنه مصوب‌اند؛ تعداد مدل یا فاز تازه و نامحدود تعریف نشده است.

## منبع، تغییر و مجوز

- HEAD آغاز مطابق HEAD واقعی PR: `34a1b81237cbbe813f6979e169c70db7ddc93089`.
- Source محصول و رگرسیون نهایی: `efaab3c5dc335012ef6b8fec89a041247b509207`؛ Tree `8d5de283fc3c15b7b0e4d44819216d8e9aef6c05`.
- Commit محلی `43c7b6efdcce2a60cf33b665aab3f3cb5709bbc3` به علت نبود احراز هویت CLI مستقیماً push نشد؛ اتصال GitHub همان Tree را با parent صحیح و بدون Force در commit `efaab3c5…` ثبت کرد. بنابراین این دو commit دو نسخه متفاوت محصول نیستند.
- HEAD نهایی شواهد، commit حاوی این گزارش است. تمام تفاوت‌های پس از Source فوق فقط گزارش، JSON گیت، شواهد و README روش بسته‌بندی‌اند؛ فایل اجرایی app/core/tests/requirements/pytest تغییر تازه‌ای ندارد. Commitهای تشخیصی پس از Source فقط Workflow بررسی فونت Native و تصحیح انتقال backend به child پنجره اصلی را اضافه می‌کنند؛ آزمون‌های موجود Native در سه مقیاس جدا اجرا می‌شوند. بقیه تفاوت‌ها اسناد/شواهدند. تفاوت backend و نتیجه همان تست‌ها در RTL_EXPORTS و بخش پذیرش Native ثبت است؛ broad عمومی را به‌عنوان full native-shell UAT جا نمی‌زنیم.
- PR #34 Open / Draft / Unmerged حفظ شد؛ Merge، Force Push، تغییر main، ساخت EXE، Installer، Release و شروع فاز ۷ انجام نشد.

تغییر محصول محدود به `core/drawings/bim_adapter.py` است: تصویر RefDirection طبق IFC4 IfcBuildAxes و رد جهت‌های صفر/موازی/نزدیک موازی. تلرانس 1e-12 افزایش نیافت؛ ظرفیت هندسه، حق مقدار، CAS، SQLite و منطق مالی تغییر نکردند. `tests/test_phase6_ifc_build_axes_contract.py` افزوده و دو تست اشتباهِ skew معتبر در `test_phase6_g2_axis_orthogonality.py` به رد محور نزدیک موازی تصحیح شدند. جزئیات استاندارد و جدول همه ۹۶ Placement در [گزارش G2](G2_ENGINEERING.fa.md) و `san-placement-numerical.json` است.

ابزار اندازه‌گیری `scripts/diagnostics/p6_sanitary_build_axes_audit.py` و Workflow تجمیعی `.github/workflows/phase6-final-closeout.yml` افزوده شدند؛ pin همان adapter در دو Workflow تشخیصی موجود هم به‌روز شد. آزمون مرجع پنج‌طبقه دست‌نخورده است. RED محلی ۴ FAIL / ۴ PASS و سپس GREEN همان مسیر همراه گیت‌های موجود ۱۴ PASS است؛ آزمون واحد مصنوعی برای اثبات نقص به کار رفت، نه جایگزین پذیرش منبع مستقل.

## اجراها و اصل شواهد

[CI نهایی 40929200449](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449) همه Jobها را با checkout صریح Source بالا اجرا می‌کند. Windows backend عمومی `windows` و Linux backend `offscreen` دارد؛ استثنای child آزمون shell و اصلاح CI بعدی به‌طور صریح در RTL_EXPORTS ثبت شده است. اصل Artifact ZIPها دوباره دریافت و SHA256 سرویس مقایسه شد؛ JUnitها مستقل خوانده شدند. نبود JUnit، exit نامعتبر یا timeout هیچ‌گاه PASS نیست. Artifact inventory و شمارش/دلایل SKIP در `CI_VERIFIED.json` و `manifest.json` نگهداری می‌شوند.

نتیجه نهایی Workflow: **SUCCESS، هر ۹ Job موفق**. رگرسیون فعال در هر سیستم ۸۴۵۹ testcase یکتا و ۷۱۶ ماژول دارد؛ سه shard ویندوز غیرهم‌پوشان‌اند و با Linux عیناً تطبیق دارند.

| محیط | تست | PASS | FAIL | ERROR | SKIP | Exit / Timeout |
|---|---:|---:|---:|---:|---:|---|
| p6-broad-current-windows-1 | 3266 | 3265 | 0 | 0 | 1 | ۰ / خیر |
| p6-broad-current-windows-0 | 2483 | 2480 | 0 | 0 | 3 | ۰ / خیر |
| p6-broad-current-linux | 8459 | 8454 | 0 | 0 | 5 | ۰ / خیر |
| p6-broad-current-windows-2 | 2710 | 2707 | 0 | 0 | 3 | ۰ / خیر |
| Windows جمع یکتا | 8459 | 8452 | 0 | 0 | 7 | ۰ / خیر |

پذیرش عملکردی جدا: Linux **347 PASS**، Windows **369 PASS**، بدون FAIL/ERROR/SKIP. هدفمند IFC/GUI/نسخه واحد: Linux **45 PASS + 1 SKIP**، Windows **46 PASS**. Historical جدا: **130 PASS در هر سیستم**، بدون FAIL/ERROR/SKIP. این مجموعه‌ها برای تولید یک عدد PASS ظاهراً بزرگ با رگرسیون فعال جمع نشده‌اند؛ هم‌پوشانی سناریوها حفظ و آشکار است.

علت SKIPهای Linux، آزمون‌های Native Windows/NTFS/توکن و PowerShell است. علت SKIPهای Windows، قراردادهای POSIX/hard-link/rename مختص Linux است. شناسه دقیق و علت تک‌تک موارد در `CI_VERIFIED.json` ثبت شده؛ تست حذف یا XFail نشده است. تمام JSONهای Runner خروج صفر و `timed_out=false` دارند؛ Native AV تازه در این اجرای رگرسیون مشاهده نشد. این نتیجه اثبات علت کرش تاریخی نیست.

اصل JUnit/JSON/Log تمام Artifactها در `original-ci-junit-json-logs.tar.gz` پایدار است؛ SHA256: `f08c4bdc51bcc2222cf83e5fc5f0afa78b659a269a5cf9fd3b019e17c6b654d5`. لینک مستقیم Artifactها در بخش زیر و inventory با digest اصلی سرویس موجود است.

- [p6-broad-current-windows-1 — 12923575447](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12923575447)
- [p6-final-acceptance-windows-2022 — 12923515112](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12923515112)
- [p6-broad-current-windows-0 — 12922802946](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12922802946)
- [p6-broad-shard-union-verification — 12922558861](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12922558861)
- [p6-broad-current-linux — 12922407211](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12922407211)
- [p6-closeout-engineering-windows-2022 — 12921902346](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12921902346)
- [p6-closeout-engineering-ubuntu-24.04 — 12921797451](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12921797451)
- [p6-broad-current-windows-2 — 12921539419](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12921539419)
- [p6-final-acceptance-ubuntu-24.04 — 12921114084](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200449/artifacts/12921114084)


۱۵ ماژول Historical/Release Contract از مجموعه Current مستقل باقی ماندند؛ همان ۱۵ ماژول با ۱۳۰ testcase در هر سیستم در fixture آفلاین و موقت، بدون اجرای YAML، ساخت یا Release آزموده شدند. آن ۱۳۰ مورد به آمار PASS مجموعه فعال اضافه نمی‌شود و اجازه Build یا تأیید بسته واقعی نیست.

دو Workflow تشخیصی قدیمی نیز خودکار از تغییر adapter تحریک شدند: [40929200245](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200245) و [40929200271](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40929200271). هر دو FAILURE هستند، نه PASS؛ در گیت اولیه SHA ثابت `core/bim/ifc.py` توقف کردند، زیرا هنوز blob قبل از پیاده‌سازی batching را انتظار داشتند. این شکست زیرساختی با شکست هندسه محصول یا JUnit رگرسیون نهایی یکی نیست و هیچ نتیجه‌ای از آن‌ها به آمار پذیرش افزوده نشده است. رکورد شکست حذف/بازنویسی یا به‌عنوان سبز معرفی نشد. Workflow نهایی خواندن واقعی و قراردادهای جدید را جداگانه آزمود؛ آزمایش تاریخی full-scene خارج از ظرفیت جای پذیرش batching نیست.


### پذیرش مکمل Native Windows بعد از کشف تفاوت backend

[40933689980](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980) روی HEAD اجرایی CI `e012f0acf1f2dd475f79e49fc43552c10850b47e`: **۳ Job SUCCESS**؛ در ۱۰۰٪، ۱۵۰٪ و ۲۰۰٪ هرکدام **۱۱ PASS، صفر FAIL/ERROR/SKIP**، JUnit معتبر و child backend واقعی windows. [Artifact ۱۰۰٪](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980/artifacts/12924191585)، [۱۵۰٪](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980/artifacts/12923133912)، [۲۰۰٪](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980/artifacts/12924785017). تصویر پنجره اصلی ۲۰۰٪ همین اجرای نهایی خوانده شد و متن فارسی/لاتین خواناست.

تفاوت این HEAD نسبت به Source رگرسیون جامع طبق compare مستقیم GitHub فقط **چهار فایل Workflow** است، نه app/core/tests؛ در `post-product-workflow-only-compare.json` ثبت شده است. تنظیم متغیر مخصوص child، خوانایی در offscreen را با native اشتباه نمی‌گیرد. برای کد محصول بدون تغییر، رگرسیون گسترده دوباره تکرار نشد. اجرای قبلی Native در هر مقیاس ۱۰ PASS/۱ FAIL مربوط به نبود ifcopenshell در CI بود و در `native-shell-red-ci-dependency.json` و اصل JUnitها حفظ شد؛ بعد از نصب وابستگی، همان تست‌ها سبز شدند. دو اجرای نامعتبر اولیه Probe نیز صریح ثبت شده‌اند، نه PASS محصول.

## حکم گیت‌های مصوب

| گیت | معیار | حکم این مأموریت |
|---|---|---|
| G1 | سناریوی Native سابق، خروج/JUnit واقعی، تایمر صفر و Handler فعال | پذیرش خودکار محدود قبلی حفظ؛ علت تاریخی قطعی نیست. مقایسه Faulthandler تکرار نشد؛ رگرسیون جدید نتیجه مستقل دارد |
| G2 | انتخاب و نمایش معتبر چندرشته‌ای در حد هندسه مستند، ردیابی منبع و جلوگیری از BOQ غیرمجاز | ایراد SAN اصلاح؛ منابع SAN v1/v2/گرمایش در هر دو سیستم پذیرفته در دامنه دو بسته؛ G2 کلی BLOCKED به دلیل پذیرش مستقلِ نامثبت محوطه/بازسازی |
| G3 | قرارداد مستقل مصوب برای P6-6 | چنین قرارداد مستقلی پیدا نشد؛ NONBLOCKING، بدون اختراع مانع و بدون ادعای تکمیل قابلیت نامعین |
| G4 | تجربه واقعی روی Windows مالک، GPU/driver، چند مانیتور و Sleep/Resume و امضا | NOT EXECUTED؛ CI و DPI شبیه‌سازی‌شده جانشین آن نیست |
| G5 | فقط یک Windows جامع؛ ساخت با اجازه جداگانه | ACCEPTED_SINGLE_UNIFIED_POLICY_NO_BUILD؛ پروفایل unified کامل و marker آن authoritative است، سازگاری editionهای قدیمی خروجی جدا نیست |

مدل AI محلی کاربرد غیرتجاری دارد؛ تهیه مجوز تجاری AI شرط فاز ۶ نیست. وزن GGUF واقعی در این مأموریت نصب/آزموده نشده و Placeholder عملیاتی اعلام نشد. کنترل SHA و مجوز کاربرد/بازنشر وزن واقعی برای استفاده احتمالی و گیت ساخت آتی حفظ است؛ fallback rule-based آزموده‌شده معتبر است.

## رابط، گزارش، کارایی و بازیابی

[گزارش RTL و خروجی‌ها](RTL_EXPORTS.fa.md) دامنه واقعی QTest، پنل شناور، Ribbon، 2D↔3D↔Tree↔BOQ، SQLite/بازگشایی، بازیابی خرابی و PDF/XLSX/DOCX/CSV را توضیح می‌دهد. تصاویر واقعی backend windows در ۱۰۰٪ و ۲۰۰٪ دیده شدند؛ ممیزی همه صفحه‌های محصول یا چاپ فیزیکی Office ادعا نمی‌شود. CI Windows مقیاس ۱۰۰/۱۵۰/۲۰۰ را در فرایندهای جدا اجرا می‌کند؛ داده/خروجی مدل‌های مستقل و fixture تست از هم جدا هستند.

رگرسیون فعال شامل سنجش موجود ۱/۵/۲۰/۵۰/۱۰۰ طبقه و گیت حافظه با نمونه‌برداری RSS است؛ fixture آن مصنوعی و مشخص است. این، تضمین کارایی همه مدل‌های واقعی یا GPU فیزیکی نیست. مدل مستقل ۵۵۰ عضوی در full-scene به ظرفیت رسید و به‌صورت fail-closed رد شد؛ همان منبع در مسیر واقعی دو بسته و انتخاب IfcCovering محلی پذیرفته شد. سقف حافظه/مثلث برای سبزکردن آزمون بالا نرفت.

## فقط کارهایی که مالک باید انجام دهد

[چک‌لیست Windows واقعی](WINDOWS_OWNER_UAT.fa.md): بررسی دیداری فارسی/RTL روی دستگاه، mixed-DPI/مانیتور دوم در صورت وجود، GPU/Driver، Sleep/Resume، ذخیره/بازگشایی و امضای نتیجه با SHA. این دستگاه و تأیید انسانی در محیط حاضر در دسترس نیست. نه نصب بسته تازه و نه ساخت EXE در این مأموریت رخ داده است.

**تنها اقدام اجرایی بعدی:** تکمیل همان پذیرش G2 برای یک منبع IFC4 واقعاً مستند محوطه/بازسازی و نگاشت هندسی معتبر در مسیر اصلی، بدون فرض اینکه IfcSite یا Proxy به‌تنهایی آن را اثبات می‌کند؛ سپس تصمیم مالک براساس چک‌لیست G4. معیار یا فاز جدید ایجاد نشود و اصلاح SAN دوباره از صفر انجام نشود.

## خلاصه وضعیت پروژه و این گفت‌وگو

| فاز | وضعیت و حد این گزارش |
|---|---|
| ۱ — مهندسی و متره | دامنه فنی پذیرفته‌شده پیشین حفظ؛ بستن/پذیرش تازه اعلام نشد |
| ۲ — ورودی نقشه و BIM | دامنه فنی قبلی حفظ؛ اصلاح IFC این مأموریت در گیت رابط فاز ۶ مستند است |
| ۳ — BOQ و مالی | دامنه قبلی حفظ؛ منطق مالی تغییر نکرد |
| ۴ — مدیریت پروژه | تکمیل فنی قبلی Non-Windows حفظ؛ پذیرش فیزیکی/ریسک تاریخی مستقل باقی است |
| ۵ — داده و امنیت | دامنه فنی قبلی و گیت‌های مستقل A1/پذیرش واقعی حفظ؛ مدل Placeholder پذیرفته نشده |
| ۶ — رابط و نمایش زنده | PARTIAL / NO-GO؛ اصلاح واقعی SAN و پذیرش خودکار مستند، G2 باقیمانده و G4 انسانی باز |
| ۷ — گزارش مهندسی | شروع نشده؛ مجوز داده نشده |
| ۸ — پذیرش نهایی | شروع نشده؛ انتشار و امضای نهایی مستقل |

دقیقاً **۸ فاز** و **۸۵٪ رسمی**، بدون افزایش حدسی. در این مأموریت نقص خواندن IFC اثبات و اصلاح شد، شواهد همه Placementهای مسئله‌دار حفظ شد، CI کامل/هدفمند اجرا شد، ۱۵ قرارداد تاریخی جدا آزموده شدند، سه منبع مستقل دیگر بررسی شدند و سیاست یک نسخه Windows تثبیت شد. G2 کلی و UAT مالک هنوز اجازه بستن فاز را نمی‌دهند. PR #34 باز و Draft باقی است. یک نسخه نهایی Windows از نظر تصمیم محصول واحد است؛ بسته واقعی ساخته/امضا/پذیرفته نشده و Release-ready اعلام نمی‌شود. عبارت PHASE 6 CLOSED یا اجازه فاز ۷ صادر نشده است.
