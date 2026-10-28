## نتیجه نهایی قابل تحویل — ۲۸ اکتبر ۲۰۲۶

اصلاحات اجرایی، آزمون‌های RED/GREEN، رگرسیون، Commit و Push هر سه اولویت انجام شده‌اند؛ گیت‌های کلی P6-4/P6-5 همچنان **PARTIAL** هستند و موارد فاقد قرارداد یا سخت‌افزار پایین مشخص‌اند. **کل pytest سبز نیست**: دو شکست baseline با نام و شاهد مستقل ثبت شده‌اند.

| آخرین اجرای واقعی | Linux Qt | Windows native | FAIL/ERROR/SKIP | هشدار pytest |
|---|---:|---:|---|---|
| PR33،CI40616456506،کد04e2e61 |۲۵۷PASS|۲۵۷PASS|هر محیط۰/۰/۰|هر محیط۱fitz|
| PR34،CI40616837797،کدed0e28a |۴۶۱PASS|۴۶۱PASS|هر محیط۰/۰/۰|هر محیط۱fitz|
| Historical Quarantined همانCIجدید |۱۳۰PASS|۱۳۰PASS|هر محیط۰/۰/۰|۰|
| امنیت جداسازی همانCIجدید |۲۶PASS|۲۶PASS|هر محیط۰/۰/۰|۰|
| DPI۱۵۰٪ تکرارDock |۸PASS|۸PASS|هر محیط۰/۰/۰|۰|
| DPI۲۰۰٪ تکرارDock |۸PASS|۸PASS|هر محیط۰/۰/۰|۰|
| Broad Current روی005a55f |۸۳۵۱PASS|کل مجموعهWindows اجرا نشد|۲FAIL/۰ERROR/۱۰SKIP رویLinux|۳|

عددهای دو سیستم و تکرار DPI، سناریوهای یکتای قابل جمع نیستند. هشت Dock در مقیاس۱۰۰٪ داخل بسته اصلی‌اند. broad8363testcase،exit۱،بدونtimeout و JUnitواقعی دارد؛ هر دوFAILروی مبنای آغاز4bdbنیزFAILهستند. دهSKIP فقط قراردادهای بومیWindows/PowerShell درLinuxاند وPASS نیستند. پس از broad فقط۱۲حالت منفی IFC به آزمون W1 افزوده و در بسته۴۶۱هر دو سیستم مستقلاً اجرا شد؛ اجرای مجدد کل۸۳۷۵جاری در یک process رویed0e28a ادعا نمی‌شود. Collection مستقیم آخرین کد۸۵۰۵،صفرerror؛۱۵خطای قبلیCollection برطرف‌اند.

کد/Tree PR33: `04e2e61151013a09f31e92aa943978b5de8bf188` / `dc7078d441dd0d9e231ebc0d6f1c005178aee29f`؛ HEADاسناد `c859cebccf83a43e456e73377bb2dea764e00823`.
کد/Tree PR34: `ed0e28acc2fd4f3e2f22f674755a8f94ad9b4732` / `2d5be7e281f7e1c4bf74412b4877383b6994ed87`؛ HEADاسناد پس از این کد فقط شواهد/مستندات دارد و در تحویل نهایی/branch ثبت می‌شود.

[CI نهایی PR33 و Artifact/JUnit](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40616456506) | [CI نهایی PR34 و Artifact/JUnit/تصاویر Windows](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40616837797) | [شمارش و SHA256 واقعی CI](ci-measured.json) | [JUnit محلی۴۶۱](linux-latest-workflow.xml) | [JUnit گسترده](current-final.xml) | [شکست‌ها و Skipها](current-final-nonpasses.json) | [تصویر۱۰۰٪](screenshots-100/workspace.png) | [تصویر۱۵۰٪](screenshots-150/workspace.png) | [تصویر۲۰۰٪](screenshots-200/workspace.png) | [UAT انسانی](WINDOWS_UAT.fa.md).

Artifact ZIPها درGitHubنیاز به ورود دارند و دانلود آن‌ها ادعا نشده؛ metadata/digest عمومی واقعیCI و JUnitهای محلی اصلی نگه‌داری شده‌اند. SHA256SUMS همه شواهد پوشه و source-SHA256SUMS تعداد۱۳۸۰فایل اصلی را پوشش می‌دهد. manifest آرشیو۱۹۳Workflow عیناً ثابت است. هیچ اجرای Workflowتاریخی، Merge، ForcePush، تغییرmain، Release، EXE،P6-6یا فاز۷ انجام نشد. Windowsفیزیکی و A2تجاری همچنانNOT VERIFIED/BLOCKED هستند؛۸فاز و۸۵٪ ثابت.

---

# تکمیل سه اولویت باقی‌مانده P6-4/P6-5 — ۲۸ اکتبر ۲۰۲۶

این گزارش جایگزین checkpointهای قدیمی برای این مأموریت است. فاز ۶ و نقشه‌راه دقیقاً هشت‌فازی و پیشرفت ثبت‌شده ۸۵٪ بدون تغییر است. هر دو PR باز و Draft باقی می‌مانند؛ Merge، Force Push، تغییر main، Release، EXE، P6-6 و فاز۷ انجام نشده‌اند.

## دامنه واقعی و حکم گیت‌ها

| گیت | نتیجه قابل اثبات | مرز باقی‌مانده |
|---|---|---|
| E6 | گسترش همان IFC_TRANSFER/دفتر اصلاحیه موجود با Undo/Redo الحاقی، CAS، بازبین مستقل اصلی، کنترل مجوز زنده، SQLite Atomic/Reopen، اوراکل طول۶=۲+۴ و سطح۱٫۸ و حجم۰٫۳۶ برای Split و Merge | مالکیت هندسی مشترک دلخواه، میلگرد یا پوشش بین چند عضو و نسبت فاقد مدرک همچنان BLOCKED؛ inverse برای Crosswalk مهاجرت‌کرده فاقد قرارداد است |
| W1 | guard زنده تمام mutationهای قابل دسترس سقف/معماری، نوع خانواده، تأیید Delete؛ Beam و Column با IFC4 مصنوعی معتبر و GlobalId/SHA/Revision و فرم اصلی؛ Slab→solid_slab و Wall→block_wall حفظ شده | IFC MEP فاقد نگاشت مهندسی تأییدشده؛ سایر زیرگونه‌ها و ساختمان واقعی مالک NOT VERIFIED |
| E4 | جست‌وجوی نشست اصلی PDF/DXF، بازکردن GraphicalTakeoffDialog اصلی با شناسه/Revision/SHA و آیتم/صفحه ذخیره‌شده؛ انتخاب واقعی Handle در DXF با واحد مستند | DWG فاقد قرارداد تبدیل/منشأ؛ handoff مستقیم نتایج عمومی به Beam/Column/MEP/سقف/معماری و گزارش فاقد هویت تخصصی BLOCKED |
| QA | جداسازی رسمی جاری/تاریخی؛ محافظ صفر Workflow فعال در Disposable حفظ؛ ۱۹۳ YAML با manifest دقیق؛ تاریخی مستقل ۱۳۰ آزمون | نتیجه کل مجموعه جاری فقط از اجرای نهایی واقعی اعلام می‌شود؛ checkpoint ناقص یا timeout سبز نیست |
| Windows UAT | Qt native و DPI ۱۰۰/۱۵۰/۲۰۰ در CI، هشت آزمون Dock تکرارشده در هر DPI | دستگاه فیزیکی دو‌مانیتوره، Sleep/Resume و تأیید مهندسی مالک NOT VERIFIED |
| A2 | وضعیت پیشین حفظ | وزن، Runtime، منشأ و مجوز مدل تجاری موجود نیست؛ BLOCKED، دانلود انجام نشد |

## نقص‌های واقعی و معماری

E6 ابتدا APIهای واقعی موجود در ifc_lineage، ifc_pipeline، manual_formula_amendments و application بررسی شدند. Split/Merge واقعی پیش‌تر در محصول وجود داشت؛ موتور، هندسه یا بانک مالکیت جدید ساخته نشد. عملیات جدید همان دفتر immutable و BOQ rebuild موجود را استفاده می‌کند؛ داده خام takeoff و register تغییر نمی‌کند. replay بر اساس previous_transfer_id انجام می‌شود تا ترتیب کلید JSON ترتیب مالی را عوض نکند. Undo و Redo رویداد جدید با group_revision افزایشی، دلیل، نویسنده، همان بازبین مستقل و نقش ثبت‌شده، ردیف‌های قبل/بعد و منشأ اصلی می‌سازند. محافظ مستقیم Store، شناسه کلید/رویداد، schema، زمان timezone-aware، revision و review را کنترل می‌کند. preview بدون نوشتن است. SQLite trigger واقعی شکست میانی درج revision را تحمیل می‌کند و rollback/reopen کامل بررسی می‌شود.

Crosswalk و مالکیت دو قرارداد مستقل موجودند. Undo/Redo پس از مهاجرت Crosswalk عمداً رد می‌شود؛ همچنین مهاجرت هنگام undone بودن مالکیت رد می‌شود تا ترتیب Apply→Undo→Migration کاربر را بدون مسیر Redo باقی نگذارد. مهاجرت پیش از اولین انتقال که پیش‌تر پشتیبانی می‌شد حفظ شده است. تغییر علامت Decimal با copy_negate دقیق است و به precision محیط وابسته نیست.

W1 Guard به wizard/proposal اصلی متصل است؛ جایگزینی wizard، منبع، پروژه، طبقه، عضو، revision، SHA و CAS آن را معتبر نمی‌کند. guard همه Save/Review/Commit/Copy/Delete/amendmentها و بعد از Yes بومی Delete را پوشش می‌دهد. Beam Preview طبق قرارداد اصلی Draft ذخیره می‌کند: هویت مجاز پیش از این mutation گرفته می‌شود و report همان هویت خوانده می‌شود؛ Commit فقط برای Draft دقیقاً یکسان از Save ضمنی تکراری عبور می‌کند. تغییر ورودی به مسیر اصلی Preview/Save برمی‌گردد. refresh صریح crossview بین mutationها مورد نیاز است، نه احیای خودکار مجوز منقضی.

IFC fixtureها با IfcOpenShell parse می‌شوند و هویت واقعی GlobalId/SHA/Revision دارند، ولی مصنوعی‌اند. کمیت‌های فرم از ورودی دستی صریح و مستند fixture هستند؛ استخراج هندسی متره از IFC یا تأیید نقشه ساختمانی مالک ادعا نشده است. دو مقدار سطح و حجم E6 از QTO صریح مدل مصنوعی و اوراکل مستقل می‌آیند، نه درصد حدسی اشتراک.

E4 موتور جست‌وجوی فعلی را حفظ می‌کند. source/Revision/SHA نشست canonical، نبود symlink، مجوز پروژه و digest پس از render دوباره بررسی می‌شود؛ BOQ و SQLite در ناوبری تغییر نمی‌کنند. نشست IFC در route جدید مجاز نیست و مسیر عضو IFC همچنان به bridge بازبینی‌شده موجود وابسته است. ماتریس تفصیلی مقصدها و RED کلیک Qt در [e4/REPORT.md](e4/REPORT.md) است.

QA محافظ current_policy را حذف نمی‌کند: منبع در Disposable بدون .git و بدون Workflow فعال stage می‌شود؛ ۱۹۳ YAML تاریخی فقط fixture متنی مستقل‌اند و هیچ Actions/Release از آن‌ها اجرا نمی‌شود. هر استفاده cache، manifest و bytes اصلی را دوباره بررسی می‌کند. runner stdout/stderr زنده و JUnit واقعی را نگه می‌دارد؛ timeout هرگز XML ساختگی یا PASS تولید نمی‌کند. دو آزمون قدیمی bulk edit به پیام تأیید بومی Yes پاسخ نمی‌دادند؛ فقط آزمون اصلاح شد، با QTest واقعی و حفظ اوراکل قبلی ۶→۳ و ۰٫۶. آزمون handoff نیز تایمر یک‌باره‌ای داشت که پیش از نمایش modal مصرف می‌شد؛ اکنون فقط پنجره واقعی و قابل‌مشاهده را می‌بندد.

## شواهد و آزمون‌ها

REDهای مستقل حفظ شده‌اند: W1 اولیه۲، mutationهای ثانویه۱۰، خانواده۶، تأیید Delete۲، IFC specialist۲؛ E6 دفتر۲، UI۱، محافظ Store۴، تغییر context۳، Crosswalk قبل/بعد Undo هرکدام۱؛ E4 یک RED کلیک اصلی. برخی REDهای زمان‌انتظار QA لاگ دارند و JUnit تولید نکرده‌اند؛ نباید به تعداد failureهای XML افزوده شوند. جزئیات QA و جمعیت هر snapshot در qa/REPORT.md و JSON همان اجرا است. نتیجه‌های تاریخی و checkpointهای قبل نباید با HEAD نهایی مخلوط شوند.

شکست callback آزمایشی QMessageBox.done به‌عنوان RED محصول شمرده نشده است. تأییدهای پذیرفته‌شده کلیک واقعی دکمه Yes/No Qt هستند. آزمون ۱/۵/۲۰ گروه مستقل، جدا از آزمون قدیمی ۲۰ عضو است؛ این دو مترادف نیستند.

## فایل‌های اجرایی اصلی

- E6: core/takeoff/manual_formula_amendments.py، core/drawings/ifc_pipeline.py، core/platform/application.py، app/ifc_lineage_controls.py و tests/test_phase6_p5_e6_ifc_transfer_history.py؛ fixture QTO در tests/test_phase2_priority5_complete.py.
- W1: app/graphical_takeoff.py، app/roof_detail_editor.py، app/architecture_detail_editor.py، app/beam_detail_panel.py و tests/test_phase6_p4_contextual_takeoff.py.
- E4: core/search/global_search.py، app/project_search_panel.py، app/verified_search_navigation.py، app/main.py و tests/test_phase6_p5_e4_sessions.py.
- QA: scripts/run_quarantined_workflow_qa.py، tests/historical_contracts.py، tests/test_recovery_quarantined_workflow_qa.py و دو آزمون legacy native bulk؛ workflow پذیرش و helperهای log/summary.

## ادامه دقیق

فقط گیت‌های فاقد قرارداد یا سخت‌افزار باقی بمانند: قرارداد inverse Crosswalk، تخصیص مالکیت مشترک مستند برای میلگرد/پوشش/چند وابستگی، نگاشت مهندسی IFC MEP و زیرگونه‌های دیگر، قرارداد هویت مقصد تخصصی E4 و UAT انسانی Windows. مدل تجاری A2 تا وجود وزن/Runtime/منشأ/مجوز معتبر BLOCKED است. تکمیل این موارد مجوز شروع فاز جدید یا تغییر ۸۵٪ نیست.

## RED/GREEN تفکیک‌شده و نقص E4 در رگرسیون گسترده

| بسته | RED واقعی ذخیره‌شده | GREEN مستقل |
|---|---|---|
| W1 |۲ اولیه +۱۰ mutation ثانویه +۶ خانواده +۲ post-Yes Delete +۲ IFC specialist در XMLهای PR33 |CI نهایی PR33:۲۴۵درهرسیستم؛ اعداد گروه‌ها هم‌پوشان‌اند |
| E6 |۲ دفتر +۱ UI +۴ Store +۳ context +۱ inverse Crosswalk +۱ migration-after-Undo |۷۲آزمون E6/original و بسته اصلی CI نهایی |
| E4 نشست |۱RED کلیک search |۳۰پیش از اصلاح انتخاب؛۳۱پس از افزودن حالت جدول |
| E4 انتخاب BOQ |۱RED Qt با SelectColumns، و شکست همان currentRow=-1 در اجرای گسترده |۳۱آزمون مقصد/جست‌وجو پس از setCurrentCell با ClearAndSelect و Rows |
| QA محافظ |لاگ‌های اولیه۷،integrity۱،timeout۲،cached-tamper۲،JUnit۲،streaming۱ failure؛ collection-integration۱error |۲۴قبل از پیگیری Windows؛۲۶پس از دو آزمون جدید checkout/CLI |
| QA آماده‌سازی |۱RED CLI فاقد شاهد setup، همراه یک PASS اثبات مستقل رفتار Git CRLF |۲۶security؛ هیچ guard حذف نشد |
| QA legacy modal |دو timeout مستقل native bulk و توقف تشخیصی handoff؛ JUnit تولید نشده |Oracle اصلی و تأیید واقعی حفظ شد؛ این timeoutها failure XML یا PASS شمرده نشده‌اند |

این‌ها شمار رخدادهای هر اجرای RED هستند، نه جمع سناریوهای یکتای پروژه. probeهای Ctrl و NoSelection هردو۲PASS بودند و علت شکست را بازتولید نکردند؛ به‌عنوان RED شمرده نشده‌اند. SelectColumns واقعاً currentRow=-1 را بازتولید کرد. انتخاب E4 اکنون به‌جای فرض رفتار selectRow، current index و همان ردیف را مستقیماً در selection model تعیین می‌کند. داده BOQ و مقدار/قیمت دوباره محاسبه نمی‌شود.

CI40614473374 عمداً FAILURE ثبت است: Linux همه مراحل گذشت؛ Windows۴۴۸اصلی و۲۴security گذشت ولی historical قبلJUnit شکست خورد و DPIها در آن اجرای قبلی اجرا نشدند. محافظ manifest پابرجا ماند. تنظیم byte-exact Git checkout پیش از checkout Windows افزوده شد و آزمون واقعی Git export نشان می‌دهد CRLF موجب رد محافظ و checkout دقیق موجب پذیرش همان۱۹۳hash می‌شود. تشخیص کامل setup اکنون در log/JSON و annotation ظاهر می‌شود، staleJUnit پاک می‌شود و exit۱ حفظ می‌شود. DPI مستقل با always اجرا می‌شود تا یک مرحله مسدود، کارهای مستقل را متوقف نکند. تا CI جدید، اجرای قبلی کامل سبز نامیده نمی‌شود.

## پانزده ماژول تاریخی Collection

همگی با قرارداد مستقل Disposable اجرا می‌شوند؛ این‌ها فرمان انتشار یا اجرای YAML نیستند.

| ماژول | PASS مستقل |
|---|---:|
| tests.test_binary_build_security_contract | 25 |
| tests.test_owner_approved_binary_build_workflows | 6 |
| tests.test_p37_real_product_deployment | 2 |
| tests.test_p37_release_gate_separation | 21 |
| tests.test_p61_p70_release_delivery | 4 |
| tests.test_priority_10_compliance | 3 |
| tests.test_priority_10_release | 3 |
| tests.test_priority_10_release_integrity | 7 |
| tests.test_priority_17_reports_excel_pdf | 38 |
| tests.test_priority_38_pre_release_freeze | 4 |
| tests.test_priority_41_ci_dependency_parity | 2 |
| tests.test_priority_42_windows_runtime_smoke | 2 |
| tests.test_priority_43_release_artifact_integrity | 2 |
| tests.test_priority_49_windows_installer_acceptance | 2 |
| tests.test_priority_9_qa | 9 |

مجموع۱۳۰؛ شمار هر testcase در historical-final.json/XML و artifact همان CI موجود است. در checkout اصلی هیچ YAML تاریخی فعال نشد.

## نتیجه قطعی مجموعه گسترده جاری

اجرای رسمی مستقل روی کد005a55f پس از اصلاح انتخاب E4 تمام شد: **۸۳۶۳ testcase = ۸۳۵۱ PASS،۲FAIL،۰ERROR،۱۰SKIP**؛۳warningpytest،۵۶۸٫۷۱ثانیه،exit۱،بدونtimeout،JUnitاصلی واقعی. کل مجموعه **GREEN نیست**. هر دو FAIL دقیقاً همان دو baseline قبلاً بازتولیدشده‌اند؛ دو حالت BOQ navigation اکنون در همین اجرای گسترده PASS هستند. ده SKIP مربوط به Windows NTFS/token/PowerShell بومی روی Linux است، نه PASS. نام/علت هر عدم‌قبولی در current-final-nonpasses.json و متن کامل هر testcase در current-final.xml/current-final.json ذخیره است.

[JUnit گسترده](current-final.xml) | [JSON رسمی](current-final.json) | [شاهد SHA و شمارش](current-final-provenance.json) | [شکست‌های baseline](BASELINE-FAILURES.fa.md). پس از این snapshot فقط پوشش۱۲آزمون منفی IFC در فایل آزمون W1 اضافه می‌شود؛ این۱۲در package و CI آخرین SHA مستقلاً آزموده می‌شوند، اما ادعای اجرای مجدد کل مجموعه گسترده بر همان SHA جدید نمی‌شود.

CI40615793724 روی005a55f پس از حفظ بایت checkout موفق شد: هر سیستم۴۴۹اصلی،۱۳۰تاریخی،۲۶security و۸+۸تکرارDPI؛ صفرFAIL/ERROR/SKIP. هشدارpytestاصلی۱fitz و سایرمرحله‌ها۰ است. notice هشدار Node20→24 اکشن‌های pinned مستقل از هشدارpytest است. CIقبلی40614473374 همچنانFAILURE تاریخی باقی است و به سبز تغییرنام داده نمی‌شود.

## تکمیل آخرین پوشش IFC و انتقال معتبر

کد/آزمون PR33:04e2e61151013a09f31e92aa943978b5de8bf188،Tree dc7078d441dd0d9e231ebc0d6f1c005178aee29f؛ CI40616456506 روی هر سیستم۲۵۷PASS و صفرFAIL/ERROR/SKIP،۱warningpytestfitz. HEAD اسناد PR33:c859cebccf83a43e456e73377bb2dea764e00823.

۱۲حالت منفی IFC جدید برای Slab/Wall × Save/Review/Commit × bytes/revision به fixture مثبت اصلی افزوده شدند؛ ابتدا validReview و refresh صریح برای Commit برقرار می‌شود. guard مشخص IFC و SQLite snapshot/digest/BOQ/integrity/Reopen بررسی می‌شوند. هر۱۲از ابتداPASS بودند،نهREDمحصول جدید. نتیجه هدفمند۱۴PASS،۰warning است. پس از انتقال patch دقیق و بررسی blobها، چهار فایل Beam/Roof/Architecture/W1test در PR33/34 دقیقاً یکسان‌اند؛ GraphicalTakeoffDialog ادغام‌های مستقل E4 شاخهP5 را حفظ می‌کند.

آخرین کد/آزمون/CI PR34:ed0e28acc2fd4f3e2f22f674755a8f94ad9b4732،Tree2d5be7e281f7e1c4bf74412b4877383b6994ed87؛ رگرسیون مستقل محلی۴۶۱PASS،صفرFAIL/ERROR/SKIP و۱warningfitz در linux-latest-workflow.xml/log. CI مستقل آخرینSHA:40616837797. آخرین HEAD مستندات PR34 پس از این SHA فقط اسناد/شواهد است و در شاخهGitHub/پاسخ تحویل ثبت می‌شود؛ آخرین HEAD اسناد از GitHub و پاسخ تحویل خوانده می‌شود.

Collection نهایی مستقیم **۸۵۰۵testcase،صفرcollectionerror** است؛۱۳۰تاریخی مستقل‌اند. broad قبلی روی کد005a55f با۸۳۶۳testcase تمام شد و تمام app/core/scripts/workflow همان محصول نهایی است؛ تفاوت نهایی فقط۱۲آزمون W1 است. کل مجموعه۸۳۷۵جاری در یک subprocess رویed0e28a مجدداً اجرا نشده و PASS نامیده نمی‌شود؛ آن۱۲در بسته۴۶۱ و هر دوCI واقعی پوشش دارند. این تفکیک از شمارش تست‌های اجرا‌نشده جلوگیری می‌کند.

انتقال سطح/حجم QTO در E6، پذیرش تقاطع هندسی همزمان چندعضو نیست؛ آن قرارداد مشترک همچنان BLOCKED است. هیچ نسبت سهم فیزیکی بدون مدرک برای گرفتنPASS ساخته نشده است.
