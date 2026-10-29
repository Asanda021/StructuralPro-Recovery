# StructuralPro | فاز ۶ / G2: اصلاح مستند جهت محورها و شناسایی مانع ظرفیت

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**PR:** [#34](https://github.com/Asanda021/StructuralPro-Recovery/pull/34) (Open/Draft/Unmerged)  
**وضعیت:** **Placement correction ACCEPTED IN BOUNDED SCOPE**؛ **Full G2 BLOCKED / Phase 6 PARTIAL / NO-GO**.

## ۱. قبل از اصلاح: شواهد مستقل RED

[CI تشخیص #40877958569](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40877958569) در Linux و Windows موفق به تشخیص خطا شد. از مدل **IFC4 تهویه منتشرشده RWTH-E3D/DigitalHub** در commit ثابت `36565d529b4dadeca625de2b793d7e16700171e9` و SHA256 منبع `c0a1807875957c4154d45d14a3b5ed480dd3178a5bdc3262302a7eccf76d5cb1` استفاده شد. ۳٬۹۷۱ `IfcLocalPlacement` همگی دارای `IfcAxis2Placement3D` بودند؛ زنجیره حداکثر ۵، بدون چرخه. ۶ محور از تلورانس `1e-24` عبور می‌کردند و **هیچ محوری از `1e-12` عبور نکرد**. قرارداد قبلی `NON_ORTHOGONAL_AXIS_DIRECTIONS` می‌داد. یک `IfcMapConversion` نیز وجود دارد که پشتیبانی از آن مستقل و همچنان اثبات‌نشده است.

شواهد اصلی تشخیص:
- Windows Artifact `12898438660`، ZIP SHA256 `93fabe75583e20f21a60265778a7364fa7d449d349bc62cbec1982e136809a0f`.
- Linux Artifact `12898324368`، ZIP SHA256 `5058bde436524349a3c9d83a5ee9806841d919058f317642945e0dd796f8697b`.

## ۲. Patch مهندسی محدود

فقط `core/drawings/bim_adapter.py` در تابع `placement()` اصلاح شد: خطای عمودنبودن تا `1e-12` برای بردارهای واحد تأییدشده پذیرفته و محور X با تصویر عمودی بر Z و نرمال‌سازی مجدد، همراه با Y حاصل ضرب برداری، به مبنای صلب متعامد تبدیل می‌شود. خطای بزرگ‌تر، دو محور هم‌راستا، طول صفر، Placement نامعتبر، SHA/Revision/Units نامعتبر همچنان fail-closed هستند. **این اصلاح، تبدیل مختصات نقشه‌ای، مدل هندسی تازه، اختیار متره، تغییر SQLite، قیمت، نقشه یا BOQ ایجاد نمی‌کند**.

آزمون جدید `tests/test_phase6_g2_axis_orthogonality.py` شامل ۶ مورد مثبت/منفی، کنترل مبنای متعامد، SHA واقعی، عدم اختیار Quantity و سقف مثلث است.

**CI اصلی اصلاح:** [#40886466903](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40886466903)، Source HEAD `4b127b6263f81c21f33caa015a171f250faa3206`: **۶ تست PASS روی Linux و ۶ تست PASS روی Windows**. در هر دو محیط اجرای مجدد قرارداد اصلی روی همان منبع مستقل: `original_contract=ACCEPTED`, `normalized_error=NONE`, اصالت Git blob و حجم و SHA تأییدشده؛ بدون JUnit مستقل برای probe JSON، و بدون ادعای پذیرش کامل 3D.

شواهد ZIP بازدریافت و JSON مستقل بررسی شدند:
- Linux Artifact `12903315635`، ZIP SHA256 `8c693ae5f1d59e0f6d99b6f33a0eb7b5ef581a3a03a853b844d0c7e269c402b6`.
- Windows Artifact `12903016860`، ZIP SHA256 `ecb8a4e250e545956b042d1655ce0875e797626e2bde57772517b5c5c3a7fa9f`.

## ۳. بازآزمایی مستقل نمایش کامل پس از اصلاح: RED مورد انتظار

[Run #40886865995](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40886865995) در HEAD `61e99aac3e83c0ace44f8f163d21b58107e5f3c7` روی **هر دو محیط completed/failure** است، زیرا سقف ایمنی نمایش **۴۰٬۰۰۰ مثلث** بدون تغییر مانده است.

| مدل منتشرشده | Linux | Windows | نتیجه |
|---|---|---|---|
| معماری، ۹۵۷ عضو / ۶۴ IfcSpace | `CAPACITY_40000_TRIANGLES`، ۱۰٫۱۰ ثانیه | همان، ۱۴٫۱۲ ثانیه | نمایش کامل BLOCKED |
| تهویه، ۱۳۱۰ عضو | `CAPACITY_40000_TRIANGLES`، ۸٫۷۹ ثانیه | همان، ۱۱٫۳۹ ثانیه | Placement گذر کرد؛ هندسه BLOCKED |

تمام فایل‌ها با Git blob و SHA معتبر دریافت شدند؛ هر چهار child با exit 0 و بدون timeout به خطای ظرفیت fail-closed رسیدند؛ CI والد به‌درستی RED است. تعداد دقیق کل مثلث‌ها در این آزمون محدود اندازه‌گیری نشد؛ عدد ۴۰هزار سقف نمایش است، نه اندازه مدل. حتی قبول قرارداد Placement به‌معنای قبول map conversion یا اتصال کل اعضا نیست.

- Linux Artifact `12903041211`، ZIP SHA256 `8f2e9126449941cd3b7a3cf17236230b64549e6539c128aaa55043341cd9be7e`.
- Windows Artifact `12901909499`، ZIP SHA256 `2719fccc76b18bcd428efcf3b053d8d094c604dd484487871727dbbbad16d009`.

## ۴. تصمیم و اقدام فنی مجاز بعدی

**G2 هنوز BLOCKED است**؛ زیرگیت دقت جهت محورها در دامنه آزموده‌شده PASS. قدم بعدی بدون Patch حدسی، سنجش **تعداد مثلث‌ها، بیشینه هر عضو و هزینه حافظه** به‌شکل محدود و فقط aggregate در مدل‌های مستقل است. سپس طراحی بارگذاری تدریجی/فیلتر طبقه و رشته یا LOD باید تضمین کند اعضای حذف/بارگذاری‌نشده واضح و قابل ردیابی‌اند، نه گم‌شده یا قابل متره. سقف ۴۰هزار تا وجود شواهد ظرفیت نباید به‌صورت دلخواه افزایش یابد.

G1 کرش Native `0xC0000005`، G4 UAT واقعی Windows، G5 منشأ مدل AI تجاری، و نبود قرارداد مستقل مصوب برای P6-6 بدون تغییر باقی‌اند. هیچ تست فوق جای رگرسیون گسترده HEAD یا تأیید مالک را نمی‌گیرد. W6 optional و آزمون Office Desktop مربوط به فاز ۸ است، نه گیت جدید فاز ۶.

**خلاصه پروژه و این نوبت:** ۸ فاز مصوب ثابت، پیشرفت رسمی کل پروژه ۸۵٪ بدون افزایش؛ یک Patch کوچک محصول + ۶ آزمون رگرسیون و یک اجرای موفق Windows/Linux، پس از آن اجرای مستقل RED برای شناسایی مانع باقی‌مانده؛ PR #34 باز/پیش‌نویس/ادغام‌نشده. هیچ EXE، Release، تغییر main، Force Push یا شروع فاز ۷.
