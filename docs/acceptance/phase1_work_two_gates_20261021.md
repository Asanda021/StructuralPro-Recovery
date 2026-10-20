# فاز ۱ — دو گیت Linux و شواهد مهندسی — وضعیت مسدود — ۲۰۲۶/۱۰/۲۱

## تصمیم پذیرش
**حالت B — دارای مانع. فاز ۱ بسته یا آماده پذیرش نهایی Windows اعلام نمی‌شود.**
این گزارش نتیجه اجرای موفق pytest نیست. محیط اجرای انتخاب‌شده در همین نشست unavailable بود؛ تلاش ابزار اجرای محلی حتی برای `pwd` با پیام `No usable execution environment is available. Wait for an environment to become available before using this tool.` متوقف شد. هیچ pytest، جمع‌آوری pytest، Python، Qt، SQLite یا تولید/رندر گزارش در این مأموریت اجرا نشد. تغییر محصول بدون بازتولید و آزمون انجام نشد. GitHub از طریق اتصال رسمی در دسترس بود و خواندن و ثبت این گزارش واقعاً انجام شد.

## مبنا و تغییرات
- HEAD اولیه از GitHub: `128575a82fbac1fb6aa29f186ac97aab1b85e43b`؛ PR #18 واقعاً Open/Draft، بدون Merge.
- Compare با مبنای اعلامی مالک: identical، صفر Commit اختلاف.
- Compare با تحویل پیشین `2080ec7a24a81609cf1bd9283698c1583f18994e`: ۲۱ Commit جلوتر و ۹ فایل تغییرکرده؛ سه فایل محصول (مدل پروژه، user_workflow و application)، دو فایل آزمون، چهار سند. موتورهای محاسباتی، ProjectStore و commit_guards در این اختلاف تغییر ندارند؛ این مشاهده تفاوت فایل است، نه اثبات عدم رگرسیون.
- تنها تغییر این مأموریت: همین گزارش. هیچ موتور، Schema، SQLite واقعی، قیمت، BOQ، Fixture یا آزمون موجود تغییر نکرد.
- HEAD تحویل: Commit حاوی همین فایل؛ SHA قطعی در پاسخ Work و سابقه GitHub ثبت می‌شود. به دلیل خودارجاعی، SHA آینده در متن فایل جعل نشده است.
- این سند هیچ ادعای آزمون روی Commit تحویل یا درخت HEAD کامل ندارد.

## دفتر اجرای این مأموریت
| عملیات | نتیجه | PASS / FAIL / ERROR / SKIP | Exit |
|---|---|---|---|
| خواندن PR و Compare از GitHub | انجام‌شده | بررسی متادیتا، نه pytest | ندارد |
| خواندن هشت فایل درخواستی و دو آزمون اخیر | انجام‌شده | ممیزی ایستا | ندارد |
| تطبیق شناسه‌های بانک و ماتریس | انجام‌شده | ۷۴ تطابق دقیق در بانک ۸۵تایی؛ صفر شناسه مفقود | ندارد |
| راه‌اندازی اجرای محلی | مسدود محیطی | ابزار اجرایی در دسترس نیست؛ شکست محصول محسوب نشده | تولید نشد |
| pytest هدفمند | NOT RUN | شمار PASS/FAIL/ERROR/SKIP قابل گزارش نیست؛ حتی collect اجرا نشده | تولید نشد |
| pytest جامع | NOT RUN | شمار PASS/FAIL/ERROR/SKIP قابل گزارش نیست | تولید نشد |
| SQLite/CAS و بازگشایی در این نشست | NOT RUN | شواهد تازه تولید نشد | تولید نشد |
| سناریوی مهندسی پنج‌طبقه و گزارش‌های تازه | NOT RUN | شاهد تازه یا مقدار مرجع تازه تولید نشد | تولید نشد |
| Windows/Office | خارج از اجرای این نشست و تأییدنشده | PASS ادعا نشده | ندارد |

تعدادهای موفق مأموریت‌های قبلی به این HEAD نسبت داده نشده‌اند. دوازده اجرای منفرد ثبت‌شده در آخرین Commit Chat، آزمون تابع استخراج‌شده با ورودی مصنوعی‌اند؛ جای pytest کامل، SQLite اصلی یا پذیرش مهندسی نیستند. ۶۹۱۶ PASS قدیمی ماتریس متعلق به درخت قبلی است. اجرای فاز ۲/PR #20 نیز شاهد این HEAD فاز ۱ نیست.

## مسیر واقعی و پوشش بررسی‌شده
- `ProjectModel._identity`: NFKC، معادل رقم‌ها و ی/ک عربی، trim و casefold برای طبقه/عضو؛ مدل، طبقه عضو و شناسه تکراری را بررسی می‌کند.
- `StructuralProApp.add_project_floor/add_project_member`: از `_explicit_project_structure`، digest، مدل موجود و همان `ProjectStore.save(expected_digest)` استفاده می‌کنند؛ دفتر موازی ندارند.
- `ProjectStore.save`: BEGIN IMMEDIATE، کنترل version/digest پیش از نوشتن، rollback، ذخیره نسخه در revisions و نگهبان‌های مالی/اصلاحیه در متن فعلی موجودند. `get` ستون نسخه SQLite را پیش از استفاده از cache می‌خواند. این‌ها مشاهده کد هستند؛ آزمون تازه هم‌زمانی یا integrity انجام نشده است.
- `reconcile_persisted_takeoff_identities`: سه رجیستر سازه، AEC و فرمول دستی را با source_id دقیق و حساس به بزرگی حروف و Unicode مرتبط می‌کند؛ alias طبقه/عضو را با source provenance یکی نمی‌گیرد. وضعیت linked صرفاً هویت ناوبری است و محاسبه/تأیید/پرداخت را ثابت نمی‌کند.
- `select_persisted_record`: نسخه جاری SQLite را با نسخه زمان بارگذاری می‌سنجد؛ داده کهنه باید رد شود. اجرای دو اتصال واقعی هنوز لازم است.
- `from_store`: از داده صریح موجود می‌خواند؛ برای پروژه قدیمی فاقد طبقه/عضو، آن‌ها را حدس نمی‌زند. رویدادهای قبلی محاسبه/بازبینی را بازسازی نمی‌کند.
- مسیر ثبت قطعی همچنان سرویس‌های موجود `reviewed_structural`، `reviewed_aec`، `manual_formula_register` و `commit_guards` است؛ tracker مالی نیست.
- نکته ایستای نیازمند بازتولید: در `LiveTakeoffTracker.emit(review_approved)` و `confirm_boq_transfer` هنوز `_identity` برای مقایسه source_id/revision استفاده شده، در حالی که تطبیق persisted و commit guard منشأ را دقیق می‌خواهند. این ناهمسانی باید با ورودی‌هایی مثل SRC-1/src-1 و رقم/حروف Unicode بازتولید شود. بدون محیط اجرا، نه اصلاح آزموده ادعا شده، نه اثر مالی واقعی یا P0 اعلام شده است؛ tracker فقط وضعیت UI است و BOQ verifier جدا دارد.
- رویدادهای calculated/reviewed در tracker قرارداد اطلاع‌رسانی‌اند؛ وجود رشته source/revision یا آزمون verifier با lambda، شاهد محاسبه واقعی یا رسید واقعی BOQ نیست. اتصال فراخواننده به سرویس مهندسی و شاهد معتبر باید در آزمون اصلی احراز شود.

## پوشش آزمون‌های موجود و کمبود مشخص
`tests/test_phase1_live_floor_events_chat.py::test_dynamic_floors_and_members` پنج پارامتر ۱/۵/۲۰/۵۰/۱۰۰ دارد، اما round-trip آن JSON و ProjectModel است؛ آزمون SQLite برای هر پنج اندازه محسوب نمی‌شود.
`tests/test_phase1_persisted_identity_reconciliation_chat.py::test_canonical_app_can_persist_explicit_floor_and_member_and_reopen` از SQLite/StructuralProApp واقعی برای پنج طبقه استفاده می‌کند. گسترش و اجرای ذخیره/بستن/بازگشایی همان چرخه برای ۱/۲۰/۵۰/۱۰۰ نیز لازم است. هیچ نبود قابلیت محصول از نبود این تست نتیجه‌گیری نشده است.
دو فایل اخیر دارای آزمون‌های هویت تکراری، حساسیت منشأ، حفظ متره قدیمی، رجیستر ناسازگار، Snapshot کهنه و عدم تولید رسید هستند؛ خواندن آزمون برابر PASS نیست.

## بانک ۸۵ خانواده و ماتریس ۷۴ خانواده
بانک واقعی از `docs/aec_priority_1_9_master_inventory_20261013.json` و ماتریس از `docs/acceptance/phase1_package1_74_family_evidence_20261019.json` در همان HEAD خوانده شدند. ۸۵ آیتم بانک، ۷۴ شناسه یکتای ماتریس، ۷۴ تطابق دقیق، صفر تغییرنام/ادغام/مفقودی وجود دارد.
یازده شناسه خارج از این ماتریس: `drawing_sources`، `drawing_selection`، `manual_workbench`، `boq`، `pricebook`، `estimate`، `statement`، `cost_control`، `scheduling`، `reporting`، `audit_provenance`.
متره دستی، BOQ و گزارش در سناریوی یکپارچه فاز ۱ همچنان باید آزموده شوند؛ خارج‌بودن شناسه بانکی آن‌ها مجوز کنارگذاشتن آزمون وابستگی نیست.

Baseline تاریخی ۳۰/۴۴ با متن فعلی ماتریس یکسان نیست: **۳۳ مسیر تخصصی محدود و ۴۱ شاهد محدود دیگر** ثبت شده‌اند. ۴۰ خانواده فاقد مسیر اختصاصی اثبات‌شده، ۳۶ فاقد آزمون خانواده‌ای و ۳۷ فاقد شاهد مستقل تخصصی کافی ثبت شده‌اند. این دسته‌ها هم‌پوشان‌اند و جمع نمی‌شوند. صفر پذیرش کامل مهندسی و صفر پذیرش Windows ثبت شده است. این اعداد، بازاجرای خانواده‌ها در این مأموریت نیستند.

جدول زیر **سابقه مستند ماتریس** را نقل می‌کند؛ ستون‌ها verified/limited/... ادعای اجرای تازه نیستند. وضعیت اجرای تازه تمام ۷۴ خانواده **not_tested_environment_unavailable** و پذیرش کامل تازه صفر است.

| شناسه | عنوان | قرارداد سابق | فرم سابق | Decimal سابق | SQLite سابق | CAS سابق | BOQ سابق | گزارش سابق | آزمون خانواده‌ای در ماتریس | کمبود مستقل |
|---|---|---|---|---|---|---|---|---|---|---|
| beam_schedule | جدول و دیتایل تیر | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| beam_reinforcement | پنج گروه آرماتور تیر | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| beam_concrete_formwork | بتن و قالب تیر | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| column | ستون بتنی | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| column_joint | اتصالات و المان های خاص ستون | limited | limited | limited | limited | limited | blocked | not_tested | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| isolated_footing | پی منفرد | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| strip_footing | پی نواری | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| mat_footing | پی گسترده | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| tie_beam | شناژ و کلاف | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| pile_foundation | پی عمیق و شمع | limited | limited | limited | limited | limited | blocked | not_tested | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| shear_wall | دیوار برشی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| stair | پله بتنی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| stair_metal | پله فولادی و نرده | verified | verified | limited | verified | verified | blocked | limited | ثبت شده؛ اجرا نشده | باز |
| solid_slab | دال توپر | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| joist_block | سقف تیرچه بلوک | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| joist_foam | سقف تیرچه یونولیت | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| waffle | سقف وافل | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| uboot | سقف یوبوت | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| cobiax | سقف کوبیاکس | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| hollow_core | هالوکور | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| steel_deck | عرشه فولادی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| kromit_roof | سقف کرومیت | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| composite_roof | سقف مرکب | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| sandwich_roof | ساندویچ پانل سقف | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| timber_roof | سقف چوبی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| precast_roof | سقف پیش ساخته | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| steel_frame | اسکلت فولادی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| composite_frame | سازه مرکب | limited | limited | limited | limited | limited | limited | limited | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| timber_frame | سازه چوبی | limited | limited | limited | limited | limited | limited | limited | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| block_wall | دیوار بلوکی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| brick_wall | دیوار آجری | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| gypsum_partition | دیوار خشک | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| plaster_finish | گچ و خاک و سفیدکاری | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| cement_render | سیمان کاری و اندود | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| ceramic_finish | کاشی و سرامیک | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| paint_finish | رنگ آمیزی | verified | verified | verified | verified | verified | verified | limited | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| waterproofing | عایق رطوبتی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| thermal_insulation | عایق حرارتی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| acoustic_insulation | عایق صوتی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| floor_finish | کف سازی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| stone_floor | سنگ کف و سنگ پله | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| suspended_ceiling | سقف کاذب | verified | verified | verified | verified | verified | verified | limited | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| door_window | درب و پنجره | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| upvc_aluminium_windows | پنجره UPVC و آلومینیوم | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| glass_curtain_wall | نمای شیشه ای | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| stone_cladding | نمای سنگی | verified | verified | verified | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| facade_cladding | نمای خشک | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| handrails_metalwork | نرده و فلزکاری | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| plumbing | آبرسانی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| sanitary_drainage | فاضلاب و باران | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| hvac | گرمایش سرمایش تهویه | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| mechanical_ventilation | تهویه مکانیکی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| plantroom | موتورخانه | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| natural_gas | گاز رسانی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| fire_protection | اطفا حریق | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| electrical_power | برق قدرت | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| lighting | روشنایی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| low_voltage | جریان ضعیف | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| fire_alarm | اعلام حریق | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| data_network | شبکه دیتا | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| security_systems | دوربین و کنترل دسترسی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| emergency_power | برق اضطراری | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| elevator | آسانسور | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| external_earthwork | عملیات خاکی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| blinding_concrete | بتن مگر | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| retaining_structures | سازه نگهبان | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| external_works | محوطه سازی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| site_drains | زهکشی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| demolition | تخریب | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| concrete_repair | ترمیم سازه | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| seismic_retrofit | مقاوم سازی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| historic_restoration | مرمت تاریخی | limited | limited | limited | limited | limited | limited | limited | احراز نشده | باز |
| pile_cap | کلاهک شمع | verified | verified | limited | verified | verified | verified | verified | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |
| bored_pile | شمع بتنی درجا | limited | limited | verified | limited | limited | blocked | limited | ثبت شده؛ اجرا نشده | استناد به دامنه محدود سابق |

## وابستگی‌های مستقل ۳۷ خانواده
مرجع تفصیلی خوانده‌شده: `docs/acceptance/phase1_closure_37_family_review_20261020.json`. برای همه ۳۷ مورد شاهد مستقل در همان فایل missing است. مدرک یا تأیید جدید از عبارت «تکمیل شود» تولید نشده است.

| خانواده | مدرک لازم طبق سند موجود | مسئول تأمین/بازبینی | معیار خروج |
|---|---|---|---|
| stair_metal | دیتایل مصوب تمام ۱۱ گروه یا عدم کاربرد مستند؛ مختصات تماس، واکنش و ظرفیت طراحی هر تکیه‌گاه؛ طول و مشخصات جوش، پیچ، مهره و انکر و مالک پرداخت هر قطعه | طراح سازه و بازبین مستقل اتصالات فولادی | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| kromit_roof | پلان و مقاطع سقف، چیدمان و مشخصات واقعی قطعات؛ دیتایل بازشو، اتصال، میلگرد و مالکیت سطوح مشترک؛ مشخصات مقدار/واحد و قواعد اندازه‌گیری مستقل کل خانواده | طراح سازه، تهیه‌کننده شاپ و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| composite_roof | پلان و مقاطع سقف، چیدمان و مشخصات واقعی قطعات؛ دیتایل بازشو، اتصال، میلگرد و مالکیت سطوح مشترک؛ مشخصات مقدار/واحد و قواعد اندازه‌گیری مستقل کل خانواده | طراح سازه، تهیه‌کننده شاپ و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| sandwich_roof | پلان و مقاطع سقف، چیدمان و مشخصات واقعی قطعات؛ دیتایل بازشو، اتصال، میلگرد و مالکیت سطوح مشترک؛ مشخصات مقدار/واحد و قواعد اندازه‌گیری مستقل کل خانواده | طراح سازه، تهیه‌کننده شاپ و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| timber_roof | پلان و مقاطع سقف، چیدمان و مشخصات واقعی قطعات؛ دیتایل بازشو، اتصال، میلگرد و مالکیت سطوح مشترک؛ مشخصات مقدار/واحد و قواعد اندازه‌گیری مستقل کل خانواده | طراح سازه، تهیه‌کننده شاپ و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| precast_roof | پلان و مقاطع سقف، چیدمان و مشخصات واقعی قطعات؛ دیتایل بازشو، اتصال، میلگرد و مالکیت سطوح مشترک؛ مشخصات مقدار/واحد و قواعد اندازه‌گیری مستقل کل خانواده | طراح سازه، تهیه‌کننده شاپ و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| gypsum_partition | برداشت ابعاد واقعی، بازشو و شناسه وجه یا قطعه؛ مشخصات لایه/مقطع/اتصال و واحد اندازه‌گیری؛ جدول مستقل مقادیر با مرجع و تأیید بازبین | طراح معماری/نما و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| cement_render | برداشت ابعاد واقعی، بازشو و شناسه وجه یا قطعه؛ مشخصات لایه/مقطع/اتصال و واحد اندازه‌گیری؛ جدول مستقل مقادیر با مرجع و تأیید بازبین | طراح معماری/نما و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| door_window | برداشت ابعاد واقعی، بازشو و شناسه وجه یا قطعه؛ مشخصات لایه/مقطع/اتصال و واحد اندازه‌گیری؛ جدول مستقل مقادیر با مرجع و تأیید بازبین | طراح معماری/نما و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| upvc_aluminium_windows | برداشت ابعاد واقعی، بازشو و شناسه وجه یا قطعه؛ مشخصات لایه/مقطع/اتصال و واحد اندازه‌گیری؛ جدول مستقل مقادیر با مرجع و تأیید بازبین | طراح معماری/نما و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| glass_curtain_wall | برداشت ابعاد واقعی، بازشو و شناسه وجه یا قطعه؛ مشخصات لایه/مقطع/اتصال و واحد اندازه‌گیری؛ جدول مستقل مقادیر با مرجع و تأیید بازبین | طراح معماری/نما و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| facade_cladding | برداشت ابعاد واقعی، بازشو و شناسه وجه یا قطعه؛ مشخصات لایه/مقطع/اتصال و واحد اندازه‌گیری؛ جدول مستقل مقادیر با مرجع و تأیید بازبین | طراح معماری/نما و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| handrails_metalwork | برداشت ابعاد واقعی، بازشو و شناسه وجه یا قطعه؛ مشخصات لایه/مقطع/اتصال و واحد اندازه‌گیری؛ جدول مستقل مقادیر با مرجع و تأیید بازبین | طراح معماری/نما و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| plumbing | مسیر و طول واقعی شبکه و فهرست قطعات و تجهیزات؛ مشخصات سازنده، واحد و دیتایل نصب/عایق/تکیه‌گاه؛ جدول مستقل اندازه‌گیری و حدود مالکیت بدون نسبت یا طول حدسی | طراح مکانیک و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| sanitary_drainage | مسیر و طول واقعی شبکه و فهرست قطعات و تجهیزات؛ مشخصات سازنده، واحد و دیتایل نصب/عایق/تکیه‌گاه؛ جدول مستقل اندازه‌گیری و حدود مالکیت بدون نسبت یا طول حدسی | طراح مکانیک و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| hvac | مسیر و طول واقعی شبکه و فهرست قطعات و تجهیزات؛ مشخصات سازنده، واحد و دیتایل نصب/عایق/تکیه‌گاه؛ جدول مستقل اندازه‌گیری و حدود مالکیت بدون نسبت یا طول حدسی | طراح مکانیک و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| mechanical_ventilation | مسیر و طول واقعی شبکه و فهرست قطعات و تجهیزات؛ مشخصات سازنده، واحد و دیتایل نصب/عایق/تکیه‌گاه؛ جدول مستقل اندازه‌گیری و حدود مالکیت بدون نسبت یا طول حدسی | طراح مکانیک و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| plantroom | مسیر و طول واقعی شبکه و فهرست قطعات و تجهیزات؛ مشخصات سازنده، واحد و دیتایل نصب/عایق/تکیه‌گاه؛ جدول مستقل اندازه‌گیری و حدود مالکیت بدون نسبت یا طول حدسی | طراح مکانیک و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| natural_gas | مسیر و طول واقعی شبکه و فهرست قطعات و تجهیزات؛ مشخصات سازنده، واحد و دیتایل نصب/عایق/تکیه‌گاه؛ جدول مستقل اندازه‌گیری و حدود مالکیت بدون نسبت یا طول حدسی | طراح مکانیک و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| fire_protection | مسیر و طول واقعی شبکه و فهرست قطعات و تجهیزات؛ مشخصات سازنده، واحد و دیتایل نصب/عایق/تکیه‌گاه؛ جدول مستقل اندازه‌گیری و حدود مالکیت بدون نسبت یا طول حدسی | طراح مکانیک و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| electrical_power | مسیر کابل/لوله/سینی و طول واقعی هر مدار؛ جدول واقعی تجهیزات و مشخصات سازنده؛ واحد، مرز مالکیت و جدول مستقل اندازه‌گیری؛ بدون حدس ظرفیت یا تعداد | طراح برق و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| lighting | مسیر کابل/لوله/سینی و طول واقعی هر مدار؛ جدول واقعی تجهیزات و مشخصات سازنده؛ واحد، مرز مالکیت و جدول مستقل اندازه‌گیری؛ بدون حدس ظرفیت یا تعداد | طراح برق و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| low_voltage | مسیر کابل/لوله/سینی و طول واقعی هر مدار؛ جدول واقعی تجهیزات و مشخصات سازنده؛ واحد، مرز مالکیت و جدول مستقل اندازه‌گیری؛ بدون حدس ظرفیت یا تعداد | طراح برق و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| fire_alarm | مسیر کابل/لوله/سینی و طول واقعی هر مدار؛ جدول واقعی تجهیزات و مشخصات سازنده؛ واحد، مرز مالکیت و جدول مستقل اندازه‌گیری؛ بدون حدس ظرفیت یا تعداد | طراح برق و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| data_network | مسیر کابل/لوله/سینی و طول واقعی هر مدار؛ جدول واقعی تجهیزات و مشخصات سازنده؛ واحد، مرز مالکیت و جدول مستقل اندازه‌گیری؛ بدون حدس ظرفیت یا تعداد | طراح برق و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| security_systems | مسیر کابل/لوله/سینی و طول واقعی هر مدار؛ جدول واقعی تجهیزات و مشخصات سازنده؛ واحد، مرز مالکیت و جدول مستقل اندازه‌گیری؛ بدون حدس ظرفیت یا تعداد | طراح برق و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| emergency_power | مسیر کابل/لوله/سینی و طول واقعی هر مدار؛ جدول واقعی تجهیزات و مشخصات سازنده؛ واحد، مرز مالکیت و جدول مستقل اندازه‌گیری؛ بدون حدس ظرفیت یا تعداد | طراح برق و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| elevator | مسیر کابل/لوله/سینی و طول واقعی هر مدار؛ جدول واقعی تجهیزات و مشخصات سازنده؛ واحد، مرز مالکیت و جدول مستقل اندازه‌گیری؛ بدون حدس ظرفیت یا تعداد | طراح برق و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| external_earthwork | نقشه برداشت، تراز و مقاطع معتبر و محدوده فیزیکی؛ مرجع صریح کسورات، واحد و مالک پرداخت؛ جدول محاسبات مستقل حجم/سطح/طول یا قطعات | نقشه‌بردار، طراح عمران و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| blinding_concrete | نقشه برداشت، تراز و مقاطع معتبر و محدوده فیزیکی؛ مرجع صریح کسورات، واحد و مالک پرداخت؛ جدول محاسبات مستقل حجم/سطح/طول یا قطعات | نقشه‌بردار، طراح عمران و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| retaining_structures | نقشه برداشت، تراز و مقاطع معتبر و محدوده فیزیکی؛ مرجع صریح کسورات، واحد و مالک پرداخت؛ جدول محاسبات مستقل حجم/سطح/طول یا قطعات | نقشه‌بردار، طراح عمران و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| external_works | نقشه برداشت، تراز و مقاطع معتبر و محدوده فیزیکی؛ مرجع صریح کسورات، واحد و مالک پرداخت؛ جدول محاسبات مستقل حجم/سطح/طول یا قطعات | نقشه‌بردار، طراح عمران و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| site_drains | نقشه برداشت، تراز و مقاطع معتبر و محدوده فیزیکی؛ مرجع صریح کسورات، واحد و مالک پرداخت؛ جدول محاسبات مستقل حجم/سطح/طول یا قطعات | نقشه‌بردار، طراح عمران و بازبین مستقل متره | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| demolition | ارزیابی وضع موجود و طرح مصوب مداخله؛ روش اندازه‌گیری و محدوده واقعی تخریب/ترمیم/تقویت یا مرمت؛ جدول مستقل مقادیر، واحد و مدارک مجوز/بازبینی مربوط | مهندس ارزیاب/طراح مداخله و بازبین مستقل؛ مرمت با متخصص میراث | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| concrete_repair | ارزیابی وضع موجود و طرح مصوب مداخله؛ روش اندازه‌گیری و محدوده واقعی تخریب/ترمیم/تقویت یا مرمت؛ جدول مستقل مقادیر، واحد و مدارک مجوز/بازبینی مربوط | مهندس ارزیاب/طراح مداخله و بازبین مستقل؛ مرمت با متخصص میراث | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| seismic_retrofit | ارزیابی وضع موجود و طرح مصوب مداخله؛ روش اندازه‌گیری و محدوده واقعی تخریب/ترمیم/تقویت یا مرمت؛ جدول مستقل مقادیر، واحد و مدارک مجوز/بازبینی مربوط | مهندس ارزیاب/طراح مداخله و بازبین مستقل؛ مرمت با متخصص میراث | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |
| historic_restoration | ارزیابی وضع موجود و طرح مصوب مداخله؛ روش اندازه‌گیری و محدوده واقعی تخریب/ترمیم/تقویت یا مرمت؛ جدول مستقل مقادیر، واحد و مدارک مجوز/بازبینی مربوط | مهندس ارزیاب/طراح مداخله و بازبین مستقل؛ مرمت با متخصص میراث | positive independent quantity oracle + negative altered geometry/source/units/owner + real SQLite/CAS/reopen/BOQ invariant checks |

مسیرهای ناقص و غیرمالی باید مسدود بمانند. وجود قرارداد عمومی، نام در بانک، تست منفی یا مثبت مؤلفه‌ای، پذیرش کل خانواده نیست. پله فولادی با پله بتنی معادل نیست. اگر مدارک معتبر بعداً فراهم شد، در همین دامنه ارزیابی شوند؛ مسئولیت تأیید طراح/بازبین به Chat یا Work واگذار نشده است.

## سناریوی پنج‌طبقه — بازاستفاده از شواهد موجود، بدون ادعای اجرای تازه
فایل‌های واقعی موجود در HEAD خوانده شدند:
1. `tests/test_manual_formula_fivefloor_closure.py`: چهارده عملیات صریح در پنج طبقه و ۷۰ ردیف یکتا، Qt واقعی، Decimal، واحد صریح، ویرایش ناقص بدون تغییر، بازبینی/ثبت و ذخیره/بازگشایی؛ خروجی PDF/XLSX. این آزمون مصنوعی است و سناریوی تخصصی کامل پی/شناژ/تیر/ستون/سقف محسوب نمی‌شود.
2. `tests/test_golden_five_storey_building.py`: داده مرجع assembly و انتقال به سرویس/BOQ، تفکیک نقش مصالح و عدم قیمت ساختگی؛ مقایسه‌های Float/approx آن معادل پذیرش Decimal تمام مسیرها نیست.
3. `tests/test_stair_five_floors_stage3.py`: ۳۵ BOQ، نسخه مؤثر L3=3 و آرماتور 498.1680 کیلوگرم در Fixture صریح، گزارش‌های PDF/XLSX/DOCX/CSV و رد مالکیت تکراری.
این مقادیر فقط assertions موجود در فایل‌اند؛ نتیجه اجرای این نشست نیستند. هیچ SQLite یا گزارش جدید تولید/رندر نشد. شواهد تاریخی ARCH-5/STAIR-5 جای سناریوی سراسری مالکیت سازه با مدرک مستقل را نمی‌گیرند.

برای پذیرش سازه‌ای یکپارچه، دیتایل صریح پی/شناژ/ستون/تیر/سقف/پله، گروه‌های میلگرد، واحدها، هندسه مشترک/کسورات و مالک پرداخت باید کنار مرجع مستقل مقادیر موجود باشند. مرز وابستگی‌های هندسی بسته‌های قبلی عوض نشده و هیچ مقدار یا سند فرضی ساخته نشده است.

## دستور دقیق ادامه در محیط آماده
از همین شاخه و HEAD تحویل شروع شود؛ فقط محیط و وابستگی موجود بازاستفاده شود. ابتدا SHA و وضعیت PR دوباره کنترل شوند. سپس خروجی/Exit Code و JUnit با SHA/Tree واقعی نگهداری شوند. از exit اشتباه ناشی از pipe/tee جلوگیری شود.

```bash
git fetch origin fix/integrated-priorities-1-15-20261013
git switch fix/integrated-priorities-1-15-20261013
git pull --ff-only
git rev-parse HEAD 'HEAD^{tree}'
export QT_QPA_PLATFORM=offscreen
export PYTHONFAULTHANDLER=1
python -m pytest -q \
 tests/test_phase1_live_floor_events_chat.py \
 tests/test_phase1_persisted_identity_reconciliation_chat.py \
 tests/test_recovery_concurrent_takeoff.py \
 tests/test_takeoff_revision_safe_edit.py \
 tests/test_manual_formula_persistence.py \
 --junitxml=phase1-focused.xml
# پس از رفع واقعی شکست‌ها و موفقیت هدفمند:
python -m pytest -q --junitxml=phase1-full.xml -o faulthandler_timeout=180
# سناریوهای فعلی؛ اجرای آن‌ها به‌تنهایی پذیرش مهندسی سراسری نیست:
python -m pytest -q \
 tests/test_manual_formula_fivefloor_closure.py \
 tests/test_golden_five_storey_building.py \
 tests/test_stair_five_floors_stage3.py \
 --junitxml=phase1-fivefloor.xml
```

برای ۱/۲۰/۵۰/۱۰۰ طبقه، آزمون واقعی service/SQLite در کنار مورد پنج‌طبقه موجود افزوده و اجرا شود؛ JSON جای آن نیست. نمونه‌های source متفاوت با حروف/Unicode برای persisted و reducer/receipt جداگانه آزموده شوند. CAS دو اتصال، digest و مقایسه محتوای قبل/بعد در شکست الزامی است.
نتیجه جامع قبل از اصلاحات جدید به HEAD تازه نسبت داده نشود. Skipها فقط از خروج واقعی جمع‌آوری و به محیط/محصول تفکیک شوند؛ آزمون‌ها دستی Skip نشوند.

## منشأ فایل‌های خوانده‌شده
Git blob SHAهای زیر از اتصال GitHub دریافت شدند؛ SHA-256 فایل مدرک مهندسی نیستند:

- `core/projects/project_model.py`: `318c2658ea88e6971157fc413bcc9d2b7fb05e3f`
- `core/projects/user_workflow.py`: `f208ecd766abb18469ae09f19cf26470b79e0ebf`
- `core/projects/store.py`: `ba8149b5f35e954c45f708e78e3da17d5b8c2af8`
- `core/platform/application.py`: `56ee2a266d606d8724e9262228cb453e711d5cb6`
- `core/takeoff/commit_guards.py`: `cf3c73f4585c646c70cc63c877e39d4c1eed3aad`
- `core/takeoff/reviewed_structural.py`: `85d6283d41303d1bc07b33a141ec079608a4b58f`
- `core/takeoff/reviewed_aec.py`: `12abd4b3cc4c8ff59795ede4d5f99e5249d986f9`
- `core/takeoff/manual_formula_register.py`: `953bb66a6ee3d668931acf1c52522ac0460bb8b8`
- `tests/test_phase1_live_floor_events_chat.py`: `67c59cd7f9f765b3f25d1fa196510b574ad979a7`
- `tests/test_phase1_persisted_identity_reconciliation_chat.py`: `c1a3f1aafaa2b0b71b2f6727d32db1eada4e3b2c`

## موانع و پذیرش
| مانع | مسئول/نیاز | آزمون خروج |
|---|---|---|
| محیط اجرای Work unavailable | فراهم‌شدن runtime قابل استفاده؛ بدون Actions دستی یا ساخت EXE به‌عنوان میان‌بر | pytest هدفمند، سپس جامع، با SHA/Tree/JUnit/Exit واقعی |
| پوشش SQLite اندازه‌های ۱/۲۰/۵۰/۱۰۰ در آزمون جدید احراز نشده | Work پس از دسترسی محیط؛ همان سرویس موجود | ذخیره، بستن، بازگشایی، عضو/طبقه و حفظ BOQ برای هر اندازه |
| ناهمسانی ایستای normalization در live event/receipt | بازتولید متمرکز قبل از اصلاح؛ UI با مالی خلط نشود | رد منبع/نسخه متفاوت و حفظ توالی/وضعیت؛ رسید واقعی از سرویس |
| شاهد مستقل ۳۷ خانواده | طراح/متخصص و بازبین طبق جدول؛ Work اجراکننده آزمون است | oracle مستقل مثبت/منفی، بایت/SHA، واحد/فرمول، SQLite/CAS/BOQ |
| ساختمان واقعی و مالکیت مشترک | نقشه و دیتایل معتبر، هندسه/کسورات و مالک مصوب، بازبین مستقل | تطبیق کل اجزا، عدم دوباره‌شماری و ثبات پس از بازگشایی |
| Windows/PowerShell/Office | محیط واقعی مجاز مالک؛ خارج از اجرای فعلی | رابط/فونت/RTL/DPI/چاپ و بازخوانی Office واقعی |

هیچ PASS، گزارش بصری، بکاپ جدید یا بازیابی مستقل تازه در این نشست ادعا نشده است. این سند در GitHub ماندگار شد؛ Git commit جانشین بکاپ داده نیست. هیچ Merge، Force Push، Release، EXE، اجرای دستی Actions، دستکاری قیمت یا فعال‌سازی مالی انجام نشده است. PR #18 باید Open/Draft بماند. هیچ فاز تازه یا ورود به فاز ۲ تا ۸ انجام نشد.
