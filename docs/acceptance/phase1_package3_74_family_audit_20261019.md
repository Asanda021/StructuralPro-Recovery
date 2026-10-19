# بازسنجی شواهد ۷۴ خانواده — فاز ۱، بسته سوم، ۲۰۲۶-۱۰-۱۹

محیط: ChatGPT Work / Linux، Qt offscreen. سهمیه باقی‌مانده معلوم نیست؛ آزمون کل پروژه اجرا نشد.

HEAD اولیه و مبنای آزمون: `7c90b659005b82f44522d1083226862ec2de84fd`؛ درخت آزموده: `0a459cf5eee1ff5a83243551b6143c74c276260e`. HEAD نهایی همان Commit حامل این سند است و در رسید انتشار/بازیابی ثبت می‌شود. تغییر محصول انجام نشده؛ فقط ماتریس، دفتر اجرا و این گزارش تغییر می‌کنند.

این وضعیت، درصد پیشرفت نرم‌افزار نیست. verified فقط دامنه همان سلول و آزمون را تأیید می‌کند، نه کل خانواده، برداشت نقشه، طراحی واقعی یا Windows. صفر خانواده پذیرش کامل دارند. فیلد legacy ویندوز برای سازگاری آزمون قبلی حفظ شد؛ وضعیت مرجع جدید در reassessment.dimensions.windows برابر not_tested است.

## تطبیق ۷۴ و ۸۵

هر ۷۴ شناسه و عنوان با بانک مرجع برابر است؛ صفر تغییرنام، ادغام یا شناسه مفقود. بانک اصلی و ۸۷۹ ذکر زیرآیتم تغییر نکردند. هشت گونه سقف زیر هفت شناسه خانواده‌اند؛ وافل یک‌طرفه و دوطرفه دو گونه یک خانواده‌اند. حذف یا ایجاد خانواده انجام نشد.

|شناسه خارج از فاز اول|عنوان|فاز|
|---|---|---|
|drawing_sources|بازکردن و مدیریت نقشه|2|
|drawing_selection|انتخاب و برداشت نقشه|2|
|manual_workbench|متره دستی|2|
|boq|ریز متره و BOQ|3|
|pricebook|فهرست بها|3|
|estimate|برآورد|3|
|statement|صورت وضعیت|3|
|cost_control|کنترل هزینه|3|
|scheduling|برنامه زمانبندی|4|
|reporting|گزارش حرفه ای|7|
|audit_provenance|حسابرسی و کنترل|5|

## نتیجه قابل اتکا

۳۰ خانواده مسیر تخصصی محدود را با شاهد کنترلر، SQLite و Qt واقعی دارند؛ ۴۴ خانواده تأیید محدود دارند. برای هر ۷۴ خانواده دست‌کم مسیر عمومی ثبت فرمول مستند/قرارداد/پیش‌ارزیابی و شاهد مرتبط موجود است؛ بنابراین فقدان مطلق پیاده‌سازی برای هیچ خانواده ثابت نشده است. برای ۴۱ خانواده مسیر اختصاصی مستقل احراز نشده، که با «کد وجود ندارد» متفاوت است. برای ۳۷ خانواده آزمون مستقل تخصصی کافی احراز نشده؛ اما هیچ خانواده‌ای مطلقاً فاقد آزمون نیست: آزمون ثبت پیش‌نویس فرمول هر ۸۵ شناسه و قراردادهای عمومی موجود است. این آزمون عمومی مجوز تأیید تخصصی نیست.

steel_frame در ماتریس قبلی فاقد شاهد بود ولی موتور، فرم، SQLite، اصلاحیه و چهار گزارش با آزمون‌های موجود بازسنجی شدند. cement_render به‌عنوان جزء سطح دیوار شاهد دارد، نه پذیرش خانواده مستقل. paint_finish و suspended_ceiling موتور تخصصی و آزمون SQLite/BOQ دارند ولی فرم تخصصی کاملشان مسدود است. column_joint فقط پیش‌ارزیابی خواندنی، pile_foundation فقط اتصال محدود مرکز فضایی و bored_pile فقط پیش‌نویس/اصلاحیه غیرمالی احراز شده‌اند؛ قفل BOQ این سه نقص محسوب نمی‌شود و حفظ شد.

## اجراها

|اجرا|PASS|FAIL|ERROR|SKIP|Exit|
|---|---:|---:|---:|---:|---:|
|catalog_generic|229|0|0|0|0|
|structural|115|0|0|0|0|
|roofs_steel|312|0|0|0|0|
|architecture|412|0|0|0|0|
|wall_stair_handoff|124|0|0|0|0|
|manual_void_ui|32|0|0|0|0|
|form-scope|2|0|0|0|0|

nodeهای کامل آزمون‌ها، SHA درخت، Exit Code و هش JUnit/لاگ در phase1_package3_74_family_executions_20261019.json ثبت شده‌اند. 1226 node یکتا اجرا شد؛ شمارش فایل تکراری یا جمع نتایج تاریخی انجام نشده است. دو PASS مربوط به form-scope، اثبات شکاف فرم‌اند و معادل دو فرم پذیرفته‌شده نیستند. دو هشدار قدیمی record_property/JUnit در اجرای manual_void_ui وجود داشت؛ آزمونی Skip یا تضعیف نشد.

## نقص‌ها و برنامه بعدی

|اولویت/شناسه|یافته و شاهد|اقدام بعدی، اجرا نشده|
|---|---|---|
|P0|در دامنه آزمون‌های اجراشده تخریب داده، ثبت غیرمجاز، دوباره‌شماری یا نقض هویت اثبات نشد؛ نبود خطا در همه حالات ادعا نمی‌شود|در صورت بازتولید، آزمون قرمز و اصلاح حداقلی|
|P1-UI-01|دو فرم paint_finish و suspended_ceiling فیلدهای قرارداد جدید را ندارند؛ مشاهده واقعی Qt و رسید فیلدها در دفتر اجرا|ابتدا اتصال همین دو قرارداد به فرم موجود و آزمون کلیک کامل؛ بدون کنترلر موازی|
|P1-TEST-01|۳۷ خانواده فاقد آزمون مستقل تخصصی کافی‌اند؛ لیست دقیق زیر|تعریف مرجع مهندسی و آزمون ذخیره/نسخه/تکرار برای هر خانواده؛ آزمون عمومی جای آن را نمی‌گیرد|
|P1-REPORT-01|گزارش تخصصی سه ردیف تیر و ستون و پنج خانواده پی/شناژ فقط PDF/XLSX دارد؛ آداپتورهای beam_detail_report و column_detail_report صریحاً سایر قالب‌ها را رد می‌کنند|افزودن DOCX/CSV به همان مسیر مشترک پس از تأیید؛ صادرکننده عمومی موازی ساخته نشود|
|P1-PRECISION-01|مسیر عمومی legacy از float استفاده می‌کند؛ تضمین Decimal تخصصی برای همه آن‌ها احراز نشده؛ این ممیزی خطای مالی تازه‌ای بازتولید نکرد|قرارداد دقت و آزمون مرزی مستقل قبل از هر توسعه یا تبدیل|
|P2-EVIDENCE-01|نبود شاهد در ماتریس قبلی با نبود کد اشتباه‌پذیر بود؛ نگاشت و nodeهای اجرایی اکنون ثبت شد|حفظ این تفکیک در پذیرش‌های بعدی|
|P2-ENV-01|Windows/Office برای هر ۷۴ خانواده not_tested است؛ علت Exit135 قبلی همچنان اثبات نشده|آزمون واقعی Windows هنگام دسترسی؛ ثبت crash dump در صورت تکرار|

خانواده‌های فاقد آزمون مستقل تخصصی کافی: stair_metal, kromit_roof, composite_roof, sandwich_roof, timber_roof, precast_roof, gypsum_partition, cement_render, door_window, upvc_aluminium_windows, glass_curtain_wall, facade_cladding, handrails_metalwork, plumbing, sanitary_drainage, hvac, mechanical_ventilation, plantroom, natural_gas, fire_protection, electrical_power, lighting, low_voltage, fire_alarm, data_network, security_systems, emergency_power, elevator, external_earthwork, blinding_concrete, retaining_structures, external_works, site_drains, demolition, concrete_repair, seismic_retrofit, historic_restoration.

ترتیب پیشنهادی پس از تأیید مالک: اتصال فرم رنگ/سقف کاذب؛ تکمیل قالب‌های گزارش تخصصی محدود؛ تعریف پذیرش مستقل برای خانواده‌های عمومی بر اساس نیاز پروژه؛ سپس آزمون Windows/Office. این برنامه اجرا نشده است.

## حفاظت از سوابق

بکاپ بسته دوم گام دوم از Dropbox دوباره دریافت شد و SHA-256 آن با `932046c1d08938434c07c2a83a23268054fde77812d4007038f687bb832a6437` برابر است. Manifest فایل‌های مرجع/رسید SQLite و گزارش قبلی کنترل شد: ARCH-5 دارای ۸۳ BOQ، شش اصلاحیه و ۱۳۹ Snapshot؛ STAIR-5 دارای ۳۵ BOQ، یک اصلاحیه و نسخه L3=3 و مجموع 498.1680 kg است. داده‌های تاریخی در این بسته بازنویسی نشدند و آزمون تاریخی کامل بی‌دلیل تکرار نشد؛ این اعداد شواهد بازیابی‌شده قبلی‌اند، نه اجرای تازه سناریوی تاریخی. بکاپ قبلی و داده‌های لازم در بسته مستقل جدید تو‌در‌تو حفظ می‌شوند.

اتصال ده قرارداد و قفل‌های مالی در آزمون phase1_contract_ui_integration بازسنجی شد. آزمون شماره ردیف عددی Excel در test_shared_report_persian اجرا شد. هویت، CAS، اصلاحیه و منع دوباره‌شماری در مجموعه‌های مرتبط اجرا شدند. در این اجراها خروج ۱۳۵ رخ نداد؛ علت قبلی همچنان باز است و رفع اعلام نمی‌شود.

## وضعیت هر خانواده

ستون‌های جدول خلاصه‌اند؛ دوازده محور، مسیرها، نام کامل آزمون‌ها، شواهد مشترک و محدودیت‌ها در JSON همراه هستند. گزارش verified برای خانواده‌های دارای قرارداد تخصصی به معنای چهار خروجی در همان دامنه است؛ گزارش limited برای تیر/ستون/پی شامل محدودیت قالب و برای مسیرهای عمومی صرفاً زیرساخت مشترک است.

|شناسه|عنوان|مسیر کلی|فرم|SQLite|BOQ|گزارش|Qt|
|---|---|---|---|---|---|---|---|
|beam_schedule|جدول و دیتایل تیر|verified|verified|verified|verified|limited|verified|
|beam_reinforcement|پنج گروه آرماتور تیر|verified|verified|verified|verified|limited|verified|
|beam_concrete_formwork|بتن و قالب تیر|verified|verified|verified|verified|limited|verified|
|column|ستون بتنی|verified|verified|verified|verified|limited|verified|
|column_joint|اتصالات و المان های خاص ستون|limited|limited|limited|blocked|not_tested|verified|
|isolated_footing|پی منفرد|verified|verified|verified|verified|limited|verified|
|strip_footing|پی نواری|verified|verified|verified|verified|limited|verified|
|mat_footing|پی گسترده|verified|verified|verified|verified|limited|verified|
|tie_beam|شناژ و کلاف|verified|verified|verified|verified|limited|verified|
|pile_foundation|پی عمیق و شمع|limited|limited|limited|blocked|not_tested|verified|
|shear_wall|دیوار برشی|verified|verified|verified|verified|verified|verified|
|stair|پله بتنی|verified|verified|verified|verified|verified|verified|
|stair_metal|پله فولادی و نرده|limited|limited|limited|limited|limited|not_tested|
|solid_slab|دال توپر|verified|verified|verified|verified|verified|verified|
|joist_block|سقف تیرچه بلوک|verified|verified|verified|verified|verified|verified|
|joist_foam|سقف تیرچه یونولیت|verified|verified|verified|verified|verified|verified|
|waffle|سقف وافل|verified|verified|verified|verified|verified|verified|
|uboot|سقف یوبوت|verified|verified|verified|verified|verified|verified|
|cobiax|سقف کوبیاکس|verified|verified|verified|verified|verified|verified|
|hollow_core|هالوکور|verified|verified|verified|verified|verified|verified|
|steel_deck|عرشه فولادی|verified|verified|verified|verified|verified|verified|
|kromit_roof|سقف کرومیت|limited|limited|limited|limited|limited|not_tested|
|composite_roof|سقف مرکب|limited|limited|limited|limited|limited|not_tested|
|sandwich_roof|ساندویچ پانل سقف|limited|limited|limited|limited|limited|not_tested|
|timber_roof|سقف چوبی|limited|limited|limited|limited|limited|not_tested|
|precast_roof|سقف پیش ساخته|limited|limited|limited|limited|limited|not_tested|
|steel_frame|اسکلت فولادی|verified|verified|verified|verified|verified|verified|
|composite_frame|سازه مرکب|limited|limited|limited|limited|limited|not_tested|
|timber_frame|سازه چوبی|limited|limited|limited|limited|limited|not_tested|
|block_wall|دیوار بلوکی|verified|verified|verified|verified|verified|verified|
|brick_wall|دیوار آجری|verified|verified|verified|verified|verified|verified|
|gypsum_partition|دیوار خشک|limited|limited|limited|limited|limited|not_tested|
|plaster_finish|گچ و خاک و سفیدکاری|verified|verified|verified|verified|verified|verified|
|cement_render|سیمان کاری و اندود|limited|limited|limited|limited|limited|not_tested|
|ceramic_finish|کاشی و سرامیک|verified|verified|verified|verified|verified|verified|
|paint_finish|رنگ آمیزی|limited|blocked|limited|limited|limited|limited|
|waterproofing|عایق رطوبتی|verified|verified|verified|verified|verified|verified|
|thermal_insulation|عایق حرارتی|verified|verified|verified|verified|verified|verified|
|acoustic_insulation|عایق صوتی|verified|verified|verified|verified|verified|verified|
|floor_finish|کف سازی|verified|verified|verified|verified|verified|verified|
|stone_floor|سنگ کف و سنگ پله|verified|verified|verified|verified|verified|verified|
|suspended_ceiling|سقف کاذب|limited|blocked|limited|limited|limited|limited|
|door_window|درب و پنجره|limited|limited|limited|limited|limited|not_tested|
|upvc_aluminium_windows|پنجره UPVC و آلومینیوم|limited|limited|limited|limited|limited|not_tested|
|glass_curtain_wall|نمای شیشه ای|limited|limited|limited|limited|limited|not_tested|
|stone_cladding|نمای سنگی|verified|verified|verified|verified|verified|verified|
|facade_cladding|نمای خشک|limited|limited|limited|limited|limited|not_tested|
|handrails_metalwork|نرده و فلزکاری|limited|limited|limited|limited|limited|not_tested|
|plumbing|آبرسانی|limited|limited|limited|limited|limited|not_tested|
|sanitary_drainage|فاضلاب و باران|limited|limited|limited|limited|limited|not_tested|
|hvac|گرمایش سرمایش تهویه|limited|limited|limited|limited|limited|not_tested|
|mechanical_ventilation|تهویه مکانیکی|limited|limited|limited|limited|limited|not_tested|
|plantroom|موتورخانه|limited|limited|limited|limited|limited|not_tested|
|natural_gas|گاز رسانی|limited|limited|limited|limited|limited|not_tested|
|fire_protection|اطفا حریق|limited|limited|limited|limited|limited|not_tested|
|electrical_power|برق قدرت|limited|limited|limited|limited|limited|not_tested|
|lighting|روشنایی|limited|limited|limited|limited|limited|not_tested|
|low_voltage|جریان ضعیف|limited|limited|limited|limited|limited|not_tested|
|fire_alarm|اعلام حریق|limited|limited|limited|limited|limited|not_tested|
|data_network|شبکه دیتا|limited|limited|limited|limited|limited|not_tested|
|security_systems|دوربین و کنترل دسترسی|limited|limited|limited|limited|limited|not_tested|
|emergency_power|برق اضطراری|limited|limited|limited|limited|limited|not_tested|
|elevator|آسانسور|limited|limited|limited|limited|limited|not_tested|
|external_earthwork|عملیات خاکی|limited|limited|limited|limited|limited|not_tested|
|blinding_concrete|بتن مگر|limited|limited|limited|limited|limited|not_tested|
|retaining_structures|سازه نگهبان|limited|limited|limited|limited|limited|not_tested|
|external_works|محوطه سازی|limited|limited|limited|limited|limited|not_tested|
|site_drains|زهکشی|limited|limited|limited|limited|limited|not_tested|
|demolition|تخریب|limited|limited|limited|limited|limited|not_tested|
|concrete_repair|ترمیم سازه|limited|limited|limited|limited|limited|not_tested|
|seismic_retrofit|مقاوم سازی|limited|limited|limited|limited|limited|not_tested|
|historic_restoration|مرمت تاریخی|limited|limited|limited|limited|limited|not_tested|
|pile_cap|کلاهک شمع|verified|verified|verified|verified|limited|verified|
|bored_pile|شمع بتنی درجا|limited|limited|limited|blocked|limited|verified|

PR #18 باید Open / Draft بماند. بدون Merge، Force Push، تغییر Actions، EXE، Release، تغییر بانک، Schema، موتور یا قفل مالی. مأموریت پس از انتشار اسناد و کنترل بازیابی متوقف می‌شود؛ اجرای اصلاحات P1/P2 نیازمند تأیید مالک است.
