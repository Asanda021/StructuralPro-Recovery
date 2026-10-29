# رابط فارسی و خروجی‌ها؛ تفکیک آزمون خودکار از پذیرش فیزیکی

منبع محصول: `efaab3c5dc335012ef6b8fec89a041247b509207`، CI نهایی `40929200449`.

مجموعه پذیرش موجود، با اصل JUnit، مسیرهای P1/P2/P3، پنل‌های شناور E5، انتخاب 2D↔3D↔Tree↔BOQ و عملیات P4/P5 را می‌آزماید. مجموعه persistence شامل SQLite، بکاپ/Restore، DOCX، CSV، XLSX و PDF است؛ متن فارسی و صفر ابتدایی CSV، rightToLeft واقعی sheetهای XLSX، جدول و ردیف‌های DOCX، دقت Decimal، دفاع تزریق فرمول و تولید/رندر صفحات PDF بررسی می‌شوند. آزمون رد PDF هنگام نبود موتور bidi نیز مستقل حفظ شده است.

در Linux این اجرای پذیرش ۳۴۷ PASS، صفر FAIL/ERROR/SKIP و سه JUnit معتبر داشت؛ تصویر workspace بازیابی‌شده از Artifact `12921114084` دیده شد: برچسب‌ها و جدول فارسی، کنترل‌های بازبینی و نمایش read-only مشخص‌اند. این مشاهده، ممیزی جامع زیبایی بصری تمام صفحه‌ها یا صحت چاپ Office واقعی نیست.

Windows Server 2022 از backend واقعی `windows` استفاده می‌کند. آزمون‌های ۱۰۰٪، ۱۵۰٪ و ۲۰۰٪ در فرایندهای مستقل و با QT_SCALE_FACTOR مشخص‌اند؛ این آزمون CI جای مانیتور واقعی، mixed-DPI فیزیکی، GPU/driver، Sleep/Resume یا تأیید مالک را نمی‌گیرد. در Artifact `12923515112`، ۳۶۹ PASS و صفر FAIL/ERROR/SKIP در شش JUnit معتبر ثبت است: views=50، operations=275، persistence=22، SQLite native=2، DPI150=10 و DPI200=10. این شمارش رفتاری است؛ نقص تصویری زیر مستقل و باز است.

PDF/XLSX/DOCX/CSV در محدوده قراردادهای فعلی خروجی بررسی می‌شوند؛ این کار شروع فاز ۷ و اجرای قابلیت‌های جدید گزارش‌سازی نیست. بازبینی انسانی فونت/خوانایی و Office/چاپ فیزیکی طبق فاز ۸ مستقل می‌مانند. ابزار GUI بومی یا سخت‌افزار شخصی مالک در این محیط در دسترس نبود؛ موارد فیزیکی NOT EXECUTED هستند.


## اختلاف screenshot و اصلاح مسیر Native در CI

تصویر اولیه `p6-p1-win32-light.png` از Artifact `12923515112` حاوی نوشته‌های مربع بود. علت اختلاف backend روشن شد: `test_phase6_p1_shell.py:104` در child مقدار `QT_QPA_PLATFORM` را از `STRUCTURALPRO_P6_QPA_PLATFORM` می‌گیرد و در نبود آن **offscreen** انتخاب می‌کند. Workflow تجمیعی فقط متغیر عمومی QT را تنظیم کرده بود؛ بنابراین نباید screenshot پنجره اصلی آن را Native نامید. سایر تست‌های GUI که همان متغیر عمومی را مصرف می‌کنند همچنان مستقل‌اند.

Probe واقعی با `windows` در [40932291857](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40932291857)، مقیاس ۱۰۰٪، و [40932828838](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40932828838)، مقیاس‌های ۱۵۰٪ و ۲۰۰٪، به پایان موفق رسید؛ هر سه Tahoma را با صفر glyph مفقود در فونت برنامه و Brand ثبت کردند. تصاویر ۱۰۰٪ و ۲۰۰٪ مستقیماً دیده شدند و متن فارسی/لاتین در آن‌ها خواناست. این تشخیص، نقص فونت محصول را اثبات نکرد؛ مسیر offscreen و native را از هم جدا می‌کند.

دو تلاش اولیه Runner تشخیصی، به علت ساخت singleton دوم و سپس فراخوانی اشتباه static exec، نامعتبر بودند؛ در `font-probe-invalid-attempts.json` حفظ شده‌اند و از آن‌ها PASS/RED محصول استنتاج نشده است. پس از اصلاح harness، اجرای محلی نیز صحت آن را تأیید کرد. هیچ تغییر font محصول یا افزایش تلرانس داده انجام نشد.

متغیر مخصوص shell child در Workflowهای تجمیعی/عملکردی تصحیح شد. Commit تنظیمات `f4a90c30c37d182c18e23c34b655314b5acc8ab6` با skip-ci ثبت شد تا رگرسیون ۸هزار‌تایی بدون تغییر محصول بی‌دلیل تکرار نشود؛ تست بومی جایگزین نشده یا حذف نشده است: Workflow `phase6-native-shell-final.yml` آزمون‌های موجود کلیک/Ribbon/Dock/فونت را در هر سه مقیاس روی child واقعی Windows اجرا می‌کند. نتیجه JUnit آن در گزارش نهایی ثبت می‌شود. این اجرا نیز UAT فیزیکی نیست.


## نتيجة پذیرش اصلی Native بعد از اصلاح CI

[Run 40933689980](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933689980) روی commit `e012f0acf1f2dd475f79e49fc43552c10850b47e` در سه Job مستقل Windows Server 2022: مقیاس‌های ۱۰۰٪، ۱۵۰٪ و ۲۰۰٪، **هرکدام ۱۱ PASS و صفر FAIL/ERROR/SKIP** با JUnit معتبر. هم `QT_QPA_PLATFORM` و هم متغیر child برابر `windows` بودند. آزمون‌های موجود P1، تشخیص glyph و E5 اجرا شدند؛ تست محصول حذف/ویرایش نشد. screenshot بومی ۲۰۰٪ همین اجرای نهایی هم مستقیماً دیده شد و فارسی/لاتین خواناست.

اجرای [40933291757](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40933291757) قبل از افزودن وابستگی CI، در هر مقیاس **۱۰ PASS / ۱ FAIL** داشت؛ شکست دقیق `test_real_ifc_2d_3d_docks_share_selection_and_close_on_project_change` با `ModuleNotFoundError: ifcopenshell` بود. این شواهد حفظ شد؛ افزودن parser در Workflow، همان تست‌ها را سبز کرد. این RED→GREEN مربوط به محیط CI است و به‌عنوان اصلاح محصول جا زده نمی‌شود.

اصل XMLهای RED و GREEN، JSONهای Probe و تصاویر شاهد در `original-native-font-shell-evidence.tar.gz` ثبت‌اند. پذیرش Native در این دامنه **ACCEPTED_AUTOMATED** است؛ GPU فیزیکی، دو مانیتور واقعی، Sleep/Resume و امضای مالک همچنان NOT EXECUTED هستند.
