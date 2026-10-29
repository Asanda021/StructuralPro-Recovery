# StructuralPro | فاز ۶ | گزارش G2 محوطه‌سازی و بازسازی، منابع مستقل

**تاریخ:** ۲۰۲۶-۱۰-۲۹  
**وضعیت رسمی:** **PARTIAL / NO-GO برای G2 جامع**. پذیرش اصیل محوطه‌سازی IFC4 در دامنه دو مدل تأیید شده؛ پذیرش مستقل هندسه **بازسازی واقعی IFC4** و حالت **IfcSite-only terrain** هنوز احراز نشده است. هیچ معیار پذیرش مصوب حذف یا سبک نشده است.

## ۱. اسناد منبع، هویت و نحوه آزمون

الف) منبع با مجوز CC-BY-4.0 و مسیر ثابت:
- مخزن `BIMvoice/ifcsamples`، commit `7a7eb6bdeab3e630eeef0e923a908d0c6af07cd2`.
- مدل‌های `IFC4/buildingSMART-Certification-datasets/Simple-Scene/Building-Landscaping.ifc` و `Infra-Landscaping.ifc`، اصل منتشرشده برای **آزمون سازگاری** و نه پرونده تأییدشده یک کارگاه واقعی.
- Git Blob SHA1 و اندازه اصلی هر فایل پیش از تست بررسی شد؛ SHA256 فایل‌ها در شواهد ثبت است. IFC و داده هندسی اصلی در Artifact بارگذاری نشد.

ب) منبع پژوهشی بازسازی موجود:
- `BIM4EEB Demonstration building BIM Model`، DOI `10.5281/zenodo.6685810`، سه مدل کشور فنلاند/لهستان/ایتالیا، MD5 ناشر هر سه مطابق اصل دانلودشده.
- **schema هر سه IFC2X3** است؛ محصول در این گیت قرارداد **IFC4** را پذیرفته است. تبدیل مدل به IFC4، تغییر مخفی Schema، یا ثبت این سه مورد به‌عنوان IFC4 مجاز نیست.

ج) مرجع واقعی محوطه:
- صفحه رسمی `https://www.swisstopo.admin.ch/en/buildings-terrain-ifc`، نمونه ZIP ۱۲ ژانویه ۲۰۲۴ با `SHA256 6e2a370ca56a0a09e4baf52cbe008a88d9f39b97dc1e0bf66c8073d445f3d189`.
- فایل‌های اصلی فقط در حافظه/دایرکتوری موقت CI بررسی و بلافاصله حذف شدند. هیچ داده جی‌آی‌اس، مختصات واقعی، نام صاحب زمین یا خود مدل منتشر نشد.

## ۲. آزمون واقعی GUI اصلی StructuralPro در Windows و Linux

[GitHub Actions #40944167672](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40944167672): هر **دو Job SUCCESS** روی `f5f4c816a796c9e1c4f2b619971143996ea4c782`.

| مدل | IFC Elements | دارای هندسه | IfcGeographicElement واقعی | نتیجه Qt Linux / Windows |
|---|---:|---:|---:|---|
| Building-Landscaping IFC4 | ۶ | ۶ | ۴ | **PASS / PASS** |
| Infra-Landscaping IFC4 | ۱۱۱ | ۱۰۱ | ۷۶ | **PASS / PASS** |

- عبور از مسیر واقعی `GraphicalTakeoffDialog.open_cad_async` و QProcess، پنجره 3D، Worker بارگذاری، منوی انتخاب نوع/طبقه، انتخاب GlobalID موجود در فایل و تعویض صحنه.
- خروجی هر دو سیستم: انتخاب مستقیم عضو `IfcGeographicElement`، صحت ثابت SHA256، شناسایی کامل roster، رد انتخاب قدیمی پس از بارگذاری بسته جدید، صفر نوشتن BOQ و `quantity_authority=false`.
- شمارش بعد از تعویض: مدل کوچک `displayed:1, not_loaded:5, without_geometry:0`. مدل Infra `displayed:1, not_loaded:100, without_geometry:10`. ۱۰ عضو فاقد هندسه حذف یا ساختگی جایگزین نشد.
- شواهد: Linux artifact `12928670986` (ZIP SHA256 `aa713636aa0da145fb465baea2705606dd7912c5cf44354f401efb92a6e73f4c`) و Windows `12928113462` (ZIP SHA256 `fb491613d2e9b62a528b4df43264e5ccae46734d503b157d55b75de2d4a3c801`).

**این نتیجه، دامنه نمایش خواندنی و انتخاب یک عضو معتبرِ طبقهٔ جغرافیایی را می‌پذیرد، نه هر محوطه واقعی یا برداشت مهندسی و مترهٔ قابل‌استناد.**

## ۳. شکست‌های باز که نباید مخفی شوند

### ۳-۱. BIM4EEB: موجود واقعی، اما با Schema متفاوت

[Source audit #40944705589](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40944705589) با تأیید MD5 ناشر:

| مدل | IFC Schema | IfcElement | دارای هندسه | نتیجه |
|---|---|---:|---:|---|
| Finland | IFC2X3 | ۹۳۹ | ۹۳۹ | BLOCKED_UNSUPPORTED_SCHEMA |
| Poland | IFC2X3 | ۳۶۲ | ۳۵۶ | BLOCKED_UNSUPPORTED_SCHEMA |
| Italy | IFC2X3 | ۲۷۷۸ | ۲۷۷۸ | BLOCKED_UNSUPPORTED_SCHEMA |

این فایل‌ها از منبع واقعی و منتشرشده‌اند، ولی **در محدوده تعریف‌شده IFC4 از خود نرم‌افزار عبور نکرده‌اند**. بدون تغییر مصوب در پشتیبانی Schema یا دریافت مدل renovation IFC4 معتبر، شرط بازسازی را ACCEPTED نمی‌نامیم. هیچ مدلی تحت عنوان مستقل IFC4 بازتولید/بازنویسی نشد.

### ۳-۲. منبع رسمی swisstopo: حالت متفاوت هندسه Terrain

[Official source audit #40944658112](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40944658112):

- دو فایل زمین IFC4 به‌ترتیب حدود ۲۶۶ و ۶۰ کیلوبایت، **صفر `IfcElement` و یک `IfcSite`** دارند؛ هندسه Terrain از طریق منطق `IfcSite` ارائه می‌شود و در مدل هویت‌محور فعلی اعضای قابل‌انتخاب نمایش داده نمی‌شود.
- فایل ساختمان IFC4، ۶۹ عضو `IfcRoof`/ `IfcWall` با هندسه دارد؛ در گیت سختگیرانه `BIMAdapter` برای GlobalId در خطوط نزدیک ۶۳ رد شد؛ علت مشخص‌تر بدون شواهد امن کافی به‌عنوان «خطای قطعی ناشر» اعلام نمی‌شود.
- **موفقیت `IfcGeographicElement` معادل حمایت از IFC4 Terrain در `IfcSite` نیست**. هیچ `IfcSite` به‌زور به `IfcElement` یا به BOQ قابل‌ثبت تبدیل نشد.

## ۴. نتیجه و اقدام محدود بعدی

**دامنهٔ جدید پذیرفته‌شده:** IFC4 original GUI source-backed landscaping با شناسه واقعی `IfcGeographicElement` روی دو سیستم، هرکدام دو بسته واقعی.

**G2 جامع:** هنوز **BLOCKED**؛ فقط دو تفاوت اثبات‌نشده باقی است: **(الف) نمایش صحیح terrain واقعی که فقط در `IfcSite` هندسه دارد**، با جداسازی Spatial Context از اعضای قابل متره؛ **(ب) منبع مستقل واقعی بازسازی در Schema پشتیبانی‌شده IFC4 یا تصمیم رسمی درباره پشتیبانی اعتبارسنجی‌شده IFC2X3**.

این دو را نمی‌توان با داده ساختگی، تغییر نام مدل، تبدیل کور یا کاهش محافظ‌های مهندسی بست. اصلاح عمومی پشتیبانی IFC2X3 یا قرارداد `IfcSite` بدون طراحی و آزمون پذیرش جدید انجام نشده است.

- نسخه واحد Windows ثابت است؛ EXE، Installer، Release، Merge، تغییر main یا شروع فاز ۷ انجام نشده است.
- G1 و رگرسیون جامع آخرین نسخهٔ محصول از قبل با شواهد مستقل پذیرفته‌اند؛ کد app/core و تست اصلی در این نوبت تغییر نکرد.
- فاز ۶ **PARTIAL**، UAT واقعی G4 نیز باز؛ نقشه‌راه همچنان هشت فاز و پیشرفت رسمی ۸۵٪.

## خلاصه وضعیت پروژه و همین گفت‌وگو

**G2 Site IfcGeographicElement: ACCEPTED_AUTOMATED_SCOPE**. **G2 جامع: BLOCKED** به دو دلیل مستقل فوق؛ **G4: NOT VERIFIED**. آخرین commit معتبر محصول `efaab3c5dc335012ef6b8fec89a041247b509207` و پذیرش GUI محل `f5f4c816a796c9e1c4f2b619971143996ea4c782` است. PR #34 باید Draft/Open/Unmerged بماند. نه درصد پیشرفت تغییر می‌کند، نه فاز تازه‌ای ایجاد می‌شود.
