# StructuralPro | گیت G2 فاز ۶: آزمون مدل‌های مستقل IFC4 معماری و تهویه

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**مخزن و PR:** `Asanda021/StructuralPro-Recovery`، [PR #34](https://github.com/Asanda021/StructuralPro-Recovery/pull/34)، Draft/Open/Unmerged  
**HEAD دقیق آزمون:** `d48613c71247159f07156d43f5140d36690fcd22`  
**حکم:** **G2 = BLOCKED در نمونه‌های مستقل بزرگ‌تر؛ فاز ۶ PARTIAL و پایان/انتشار NO-GO.** این گزارش شکست واقعی را PASS معرفی نمی‌کند.

## ۱. پیدا کردن داده واقعی و تعیین سطح اعتبار
- بررسی فایل‌های این مخزن یک IFC4 آزمایشی در `docs/acceptance/phase2_priority5_verified_assets_20261022/synthetic-ifc4.ifc` نشان داد، نه مدل تجاری ساختمان.
- جست‌وجوی عنوان‌های IFC/BIM در Google Drive و Dropbox متصل، فایل مرتبط با اعتبار کافی در نتایج برنگرداند. این نتیجه صرفاً مربوط به جست‌وجوی انجام‌شده است، نه اثبات فقدان هر فایلی در همه حساب‌ها.
- برای عبور از محدودیت آزمایش‌های تولیدشده توسط خود StructuralPro، مجموعه متن‌باز و مستقل `RWTH-E3D/DigitalHub` از RWTH Aachen انتخاب شد. مجموعه مدل‌های معماری و تهویه IFC4 صادرشده از Revit را منتشر کرده است. مجوز خود مخزن `MIT` و commit مرجع `36565d529b4dadeca625de2b793d7e16700171e9` است. این **مدل مرجع منتشرشده مستقل** است؛ سند کافی برای «ساختمان واقعاً اجراشده کارفرما» یا تأیید مهندسی آن نداریم.

## ۲. روش آزمون مستقل، محدود و محرمانه
دو فایل با Git SHA و اندازه دقیق از همان commit ثابت در subprocess و بدون دستکاری محصول دانلود شدند؛ دریافت صرفاً به Runner موقت محدود بود. Git Blob SHA-1 با فرمول canonical Git روی bytes بازحساب و با شیء Git upstream تطبیق داده شد؛ SHA256 واقعی فایل در گزارش ثبت شد. مدل خام، نام سازنده، GUIDها، QTO، اشکال، مختصات، مسیرهای محلی و Traceback خام **نه Commit و نه Upload شدند**.

| رشته | IFC upstream | بایت | SHA256 واقعی |
|---|---|---:|---|
| معماری | `Version_2/DigitalHub_FM-ARC_v2.ifc` | ۹٬۰۲۲٬۲۵۵ | `19d7d02d53c2b88e86890ee236297b12bbb0f7748030cd32ff6a22762e9966bb` |
| تهویه | `Version_2/DigitalHub_FM-LFT_v2.ifc` | ۱۲٬۷۳۷٬۸۳۳ | `c0a1807875957c4154d45d14a3b5ed480dd3178a5bdc3262302a7eccf76d5cb1` |

**ابزار:** `scripts/diagnostics/p6_independent_ifc_public_reference.py`، Workflow `.github/workflows/phase6-public-reference-ifc4-probe.yml`، Windows Server 2022/Qt windows، Ubuntu 24.04، Python 3.12، IfcOpenShell، دو child process مستقل با سقف هر یک ۲۴۰ ثانیه، سقف مدل ۳۰MiB و سقف نمایش رسمی **۴۰٬۰۰۰ مثلث**. منبع هندسه مستقل هیچ مجوز Quantity یا قیمت ندارد و آزمایش هیچ تغییری در BOQ/SQLite ایجاد نکرد.

## ۳. نتیجه واقعی: هر دو پلتفرم RED
**[Run #40876168743](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40876168743)** در هر دو Job `completed/failure` است و باید همان‌طور ثبت شود؛ این خطای تصادفی CI نیست. Git Blob SHA و حجم هر دو مدل در هر دو OS تأیید شد.

| فایل | ویژگی واقعی | Linux | Windows |
|---|---|---|---|
| Architecture IFC4 | ۹۵۷ `IfcElement`، ۶۴ `IfcSpace`، ۹۴۹ عضو دارای Representation | `CAPACITY_40000_TRIANGLES`؛ ۱۰٫۳۱ ثانیه | همان محدودیت؛ ۱۴٫۶۹ ثانیه |
| Ventilation IFC4 | ۱۳۱۰ `IfcElement`، صفر `IfcSpace`، ۱۳۱۰ عضو دارای Representation | `SOURCE_PLACEMENT_CONTRACT`؛ ۴٫۰۷ ثانیه | همان محدودیت؛ ۴٫۱۴ ثانیه |

- **Architecture:** آداپتر در ظرفیت محافظه‌کارانه مصوب ۴۰هزار مثلث متوقف شد؛ نه Runtime Crash Native بود و نه دست‌کاری/حذف خاموش هندسه. تعداد مثلث دقیق کل مدل در این اجرای محدود اندازه‌گیری نشده؛ تنها عبور از سقف قطعی است. مدل موفقیت کامل Viewer را اثبات نکرد.
- **Ventilation:** فایل/Schema IFC4 و اصالت آن تأیید شده اما اعتبارسنجی Placement موتور اصلی خطا داده است. جزئیات نوع خاص Placement و سازگاری تبدیل هندسی *هنوز مشخص نشده*؛ بدون تحلیل placement matrix و نگاشت SI، رفع با تبدیل یا فرضیات مختصاتی ممنوع است.
- علت‌های فوق در دو سیستم یکسان بودند، بنابراین باگ صرفاً Platform/Qt به نظر نمی‌رسد؛ **این به‌تنهایی اثبات نمی‌کند** که تمام سیستم‌عامل‌ها رفتار یکسان دارند.
- برخلاف ۶۰ PASS روی فایل‌های IFC4 آزمایشی مستقل‌ساخت در [#40874887085](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40874887085)، این دو مدل منتشرشده خارج از مخزن StructuralPro **هیچ PASS برای G2** ندارند. دامنه آزمون‌های قبلی به‌درستی محدود نگه داشته شد.

### شواهد قابل راستی‌آزمایی
- [Windows Artifact #12897804269](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40876168743/artifacts/12897804269)؛ ZIP SHA256: `083d93a30a713e3d9cb99f0db9baf3a8a8515bfe748f004c481595f8e137ad8a`
- [Linux Artifact #12898655316](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40876168743/artifacts/12898655316)؛ ZIP SHA256: `7aba8b0a4cae5ff2b72eb5f1063a6d10aba6810eb7dcdf565dc204e4986b6b3b`

هر دو Artifact دریافت و `summary.json` آنها به‌صورت مستقل خوانده شد. **این اجرای قرمز JUnit ندارد، چون probe یک CLI subprocess diagnostic با JSON اتمیک است؛ بنابراین به‌عنوان آزمون JUnit موفق شمارش نشود.** پیاده‌سازی گیت فقط در فایل‌های diagnostics/workflow بود؛ هیچ کد محصول تغییر نکرد.

## ۴. تصمیم نهایی بدون فاز تازه
- **G2 = PARTIAL / BLOCKED INDEPENDENT LARGE MODELS**. پشتیبانی مدل ۱۴ نوع عضو IFC در fixture و اصلاح `IfcSpace` قبلی همچنان معتبر است؛ اما مدل معماری مستقل به محدودیت مثلث و مدل MEP مستقل به Placement خوردند.
- قدم مهندسی اول، **قرارداد Placement تهویه** است: ابتدا نوع دقیق (IfcLocalPlacement, IfcGridPlacement, IfcAxis2Placement3D, map conversion) و معنای transform/offset SI را در همان منبع مستقل به شکل فقط‌خواندنی مشخص کنیم؛ سپس اگر قرارداد قابل اتکایی وجود دارد، Patch محدود و آزمون منفی/مثبت. **نباید با حذف شرط هویت، واحد، Revision یا تغییر تبدیل تصادفی فایل را سبز کنیم.**
- قدم مهندسی دوم، **ظرفیت نمایش مدل معماری** است: طراحی explicit geometry batching/visibility/LOD با نمایان‌کردن وضعیت کامل/ناقص؛ نه افزایش حد ۴۰هزار مثلث به‌صورت حدسی، نه حذف مخفی عضو، نه ساخت مدل هندسی دوم یا متره از viewer.
- G1 کرش Native ویندوز، G3 تعریف/پذیرش P6-6، G4 UAT فیزیکی، G5 AI دارای مجوز و نسخه واحد، طبق ماتریس قبلی باقی هستند. W6 تشخیص تداخل **غیرمسدودکننده** و کارهای خروجی فاز ۷ یا Office فاز ۸ به این فاز منتقل نشدند.
- PR #34 باید Open/Draft/Unmerged بماند؛ **هیچ Merge، Release، EXE، تغییر main، یا ادعای تکمیل فاز ۶** انجام نشود.

## خلاصه وضعیت پروژه و این چت
- نقشه‌راه **۸ فاز ثابت** و پیشرفت رسمی **۸۵٪ بدون تغییر**.
- مورد ۱: ریشه کرش Native هنوز OPEN؛ مورد ۲ و ۳ در دامنه خودکار PASS؛ مورد ۴ ممیزی و NO-GO رسمی ثبت‌شده.
- این نوبت: جست‌وجوی مدل، یافتن دو فایل IFC4 مستقل با مجوز، اجرای واقعی Linux/Windows و ثبت دو محدودیت قابل تکرار در G2 انجام شد. **مسئله اصلی هنوز اصلاح نشده و این گیت باز است.**
