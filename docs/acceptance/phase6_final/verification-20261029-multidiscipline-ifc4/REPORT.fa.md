# StructuralPro | ادامه فاز ۶: رفع نقص واقعی IFC4 در نمایش چندرشته‌ای

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**مخزن:** `Asanda021/StructuralPro-Recovery`  
**شاخه و PR:** `feature/phase6-p5-workspace-e3-e6-20261027` / [PR #34](https://github.com/Asanda021/StructuralPro-Recovery/pull/34)، Draft/Open/Unmerged  
**آخرین HEAD کد/تست آزموده‌شده:** `11c4c8112fcd7ac754fd5ea33e1e260e5bb94581`  
**دامنه:** گیت باز G2، همان «نمایش سه‌بعدی واقعی چندرشته‌ای» فاز ۶ مصوب؛ نه اولویت/فاز جدید، نه اعلام تکمیل P6-6.

## نقص با بازتولید RED
آداپتر `core/bim/ifc.py` در `read_display_meshes` همه `IfcProduct`های دارای Representation را هندسه‌سازی می‌کرد؛ ولی `BIMAdapter.read_document` فقط `IfcElement`ها را در قرارداد هویت/BOQ تأییدشده منتشر می‌کند. `IfcSpace` (فضای معماری) از `IfcProduct` است و می‌تواند هندسه واقعی داشته باشد، اما `IfcElement` نیست؛ در نتیجه افزودن آن به مدل، کل `read_display_contract` را با `ValueError: هندسه فاقد عضو معتبر در قرارداد IFC است` رد می‌کرد.

**آزمایش قرمز واقعی:** [GitHub Actions #40874227765](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40874227765)، روی `f879deec20580fb1523435706afb33a0f21ab2eb`، هر دو سیستم قرمز؛ traceback Linux به `core/bim/ifc.py:149` در همین mismatch اشاره می‌کند. داده و هندسه آزمون واقعی IFC4 هستند و با ifcopenshell تولید می‌شوند؛ **مدل یک ساختمان تجاری نیست**.

## اصلاح محدود و ایمن
فقط محل فهرست‌سازی منبع مش به `model.by_type("IfcElement")` محدود شد. این با قرارداد مستند `read_document` منطبق است و همه `IfcElement`های واقعی، از جمله MEP، اجزای معماری، نمای پوششی و انواع موقعیت‌دار دیگر را نگه می‌دارد. `IfcSpace` به‌اشتباه Member یا مبنای Quantity معرفی نمی‌شود. موتور متره، مقدار، BOQ، قیمت، تاریخچه، SQLite، Oracle پنج‌طبقه و schema تغییر نکرده‌اند.

تست جدید `tests/test_phase6_multidiscipline_ifc4_geometry.py` یک فایل **IFC4 واقعی مصنوعیِ صریح** می‌سازد و هندسه **۱۴ نوع `IfcElement`** را در کنار فضای دارای Representation آزمون می‌کند:
- `IfcBeam`, `IfcWall`, `IfcSlab`, `IfcDuctSegment`
- `IfcFooting`, `IfcDoor`, `IfcWindow`, `IfcCovering`, `IfcStair`, `IfcCurtainWall`
- `IfcPipeSegment`, `IfcFlowTerminal`, `IfcGeographicElement`, `IfcBuildingElementProxy`

هندسه‌های IFC واقعی World-Coordinate، نوع/GlobalID/طبقه واقعی، انتخاب و فیلتر نوع در Qt، نبود مجوز Quantity، رد Revision بی‌اعتبار، تغییر SHA و عدم از دست‌رفتن عضو آزموده شدند. **وجود `IfcBuildingElementProxy` یا `IfcGeographicElement` در fixture اثبات قابلیت مهندسی بازسازی یا محوطه واقعی نیست.** `IfcSpace` به‌عنوان context فضایی غیرعضو از قرارداد Member حذف می‌شود؛ پشتیبانی اختصاصی از نمایش حجم فضاها در این اصلاح اضافه نشده است.

## شواهد GREEN
۱. [Run #40874474395](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40874474395) روی commit `8d780682f3833e38bfdd916084703230869f8fa8`: **۱۵ PASS Linux و ۱۵ PASS Windows** برای سه آزمون جدید و رگرسیون نمایش/اتصال چهارطرفه؛ هیچ FAIL/ERROR/SKIP.

۲. [Run #40874887085](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40874887085)، روی `11c4c8112fcd7ac754fd5ea33e1e260e5bb94581`: **هر دو Job completed/success**. Workflow همان سناریو را با آزمون‌های ۱/۵/۲۰/۵۰/۱۰۰ طبقه، بارگذاری پس‌زمینه/لغو، E2 بازگشایی نشست، batch parsing و اتصال چهارطرفه ترکیب کرد.

| دسته | Linux | Windows |
|---|---:|---:|
| هندسه چندرشته‌ای و `IfcSpace` | ۳ PASS | ۳ PASS |
| آزمون‌های موجود 3D، فیلتر، pick، worker، ۱۰۰ طبقه، E2 و چهار نما | ۲۷ PASS | ۲۷ PASS |
| **کل JUnit** | **۳۰ PASS** | **۳۰ PASS** |
| FAIL / ERROR / SKIP | **۰ / ۰ / ۰** | **۰ / ۰ / ۰** |

هر دو ZIP دانلود، SHA-256 محاسبه و XML اصلی به‌صورت مستقل parse شد:
- [Windows Artifact #12898016528](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40874887085/artifacts/12898016528)؛ ZIP SHA256 = `36947f38ac6cb936b906e98d4668a7cd5fd1419b65f41c4064b52eaf9ea4715b`
- [Linux Artifact #12897253349](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40874887085/artifacts/12897253349)؛ ZIP SHA256 = `ba2ff0359d7a1e86277353aaa8a95cc66dd1a0d21e8aae40332daaa0be0a7c6a`

به‌دلیل تغییر فایل `core/bim/ifc.py`، ۷۱۶ PASS گیت قبلی [#40870775780](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40870775780) متعلق به SHA **قبل از این اصلاح** است و به‌اشتباه «تکرار کامل روی HEAD جدید» خوانده نمی‌شود. گیت فعلی فقط رگرسیون مرتبط با تغییر را آزموده است.

## نسبت واقعی با P6-6 و گیت G2
ممیزی سند مصوب هشت‌فاز نسخه ۱٫۵ در PR #24 و گزارش‌های PR #34 نشان می‌دهد **عنوان P6-6 در گزارش‌ها به‌عنوان «اولویت نهایی در انتظار» آمده، اما قرارداد صریحِ قابل اجرا شامل ورودی، خروجی، تست و دامنه اختصاصی P6-6 در اسناد موجود ارائه نشده است**. بنابراین این اصلاح به‌جای جعل یک اولویت تازه، تحت G2 فاز ۶ انجام شد؛ **P6-6 همچنان NOT VERIFIED / NOT DEFINED IN ACCEPTANCE** و آغاز/پایان آن ادعا نمی‌شود.

**حکم G2:** بهبود مستند، نه بسته‌شدن کامل. آزمون IFC4 چندرشته‌ای ساختگی مهندسی ۱۴ نوع و محیط واقعی Qt Windows **PASS**؛ اما پوشش هر خانواده هندسه و تمام سطوح واقعی، نمای خارج، لایه‌های نازک‌کاری، MEP پیچیده، بازسازی و محوطه با فایل اجرای مستقل، سقف فعلی ۴۰هزار مثلث، UAT مشتری و مشکل کرش تاریخی `0xC0000005` هنوز باز یا محدودند. مدل از هندسه نامعتبر مقدار/قیمت تولید نمی‌کند.

## تصمیم نهایی، بدون بسط بی‌پایان
- **این قدم:** RED واقعی → Patch کوچک → ۶۰ اجرای JUnit معتبر (۳۰ در هر OS)، در دامنه مدل آزمایشی IFC4.
- **کل فاز ۶:** `PARTIAL`؛ **گیت G2 باز با پوشش افزوده**، G1 Native `OPEN`، G3/P6-6 فاقد قرارداد پذیرش مستقل، G4 UAT انسانی و G5 AI دارای مجوز/نسخه واحد طبق گزارش ممیزی پیشین.
- **تعهدات ثابت:** ۸ فاز با پیشرفت رسمی ۸۵٪؛ بدون Android، Merge، main، ForcePush، EXE یا Release؛ PR #34 Open/Draft/Unmerged.
- **قدم فنی بعدی:** فقط مدل IFC چندرشته‌ای واقعی و قابل اشتراک/تأیید مالک، یا شواهد رسمی ورودی/خروجی P6-6 موجود، برای پذیرش تکمیلی؛ نه جعل مدل واقعی از fixture و نه تکرار نامحدود Runهای سبز.
