# StructuralPro | فاز ۶ | نتیجه رگرسیون جامع آخرین کد آزموده‌شده

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**PR:** #34، Draft/Open/Unmerged  
**commit آزموده‌شده:** `6d0ee784c1ef58ee13e0dfbe25d858b75e3cb8ee`  
**Workflow:** https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40907806582  
**نتیجه رسمی محدوده:** **ACCEPTED_ALL_ACTIVE_CURRENT_MODULES_NATIVE_LINUX_WINDOWS**. تمام پنج Job، بدون خطا یا Timeout، SUCCESS شدند.

## شمارش JUnit واقعی

| محیط | JUnit tests collected | PASS | FAIL | ERROR | SKIP | Timeout |
|---|---:|---:|---:|---:|---:|---:|
| Linux کامل | ۸۴۵۱ | ۸۴۴۶ | ۰ | ۰ | ۵ | خیر |
| Windows shard 0 | ۲۹۵۱ | ۲۹۴۸ | ۰ | ۰ | ۳ | خیر |
| Windows shard 1 | ۲۶۷۲ | ۲۶۷۱ | ۰ | ۰ | ۱ | خیر |
| Windows shard 2 | ۲۸۲۸ | ۲۸۲۵ | ۰ | ۰ | ۳ | خیر |
| **Windows جمع یکتای سه shard** | **۸۴۵۱** | **۸۴۴۴** | **۰** | **۰** | **۷** | **خیر** |

تطبیق خودکار کل JUnitهای Windows و Linux در **Job verify-full-union = SUCCESS**، **۷۱۵ ماژول فعال**، **۸۴۵۱ مورد یکتا**، بدون مورد مفقود یا تکراری و مانيفست ثابت زیر ثبت شده است:

`7e77a4c82c9fbd62d945a4a7c0844dd3977df44f42bde741456364935dcfc342`

### شواهد قابل بازبینی

- Linux artifact **12912813506**، اصل JSON/JUnit، ۸۴۴۶ PASS، ۵ SKIP، خروجی pytest ۰ و no-timeout.
- Windows shard 0 artifact **12913790846**، ۲۹۴۸ PASS، ۳ SKIP.
- Windows shard 1 artifact **12913157815**، ۲۶۷۱ PASS، ۱ SKIP.
- Windows shard 2 artifact **12912139812**، ۲۸۲۵ PASS، ۳ SKIP.
- Union verification artifact **12913940689**، `broad-union-verified.json` مستقلاً خوانده شد و `verified: true` تأیید شد. نتیجه سه shard کامل Windows با مجموعه Linux برابر است.
- تمام ۵ Job: `conclusion=success`؛ هیچ Exit 124 / توقف در این Workflow ثبت نشده است.

## محدودیت‌های آزمون و گیت‌های مستقل

- این رگرسیون **تمام ۷۱۵ ماژول فعال Current** را آزموده، ولی **۱۵ ماژول Historical/Release Contract** که عمداً توسط `HISTORICAL_TESTS` از این Runner جدا نگه داشته می‌شوند، جزو آمار نیستند. نتیجه سبز این Workflow به معنی صدور اجازه Build/Release نیست.
- ۵ SKIP Linux و ۷ SKIP Windows عمدتاً مربوط به قابلیت‌های خاص سیستم‌عامل و آزمون‌های POSIX/Native هستند. SKIPها مخفی نشده‌اند؛ تفسیر فنی باید براساس دسترسی آن محیط به قابلیت آزموده‌شده باقی بماند.
- Runner در یک منبع موقتی با workflowهای فعال حذف‌شده، بدون اجرای فایل YAML تاریخی و بدون تغییر main/EXE/Release، از کد دقیق HEAD استفاده کرد. `faulthandler_timeout=0` به‌طور صریح حفظ شد.
- اجرای دیگر P5 در [#40907744891](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40907744891) در Linux/Windows SUCCESS شد، ولی جای آزمون UAT واقعی نیست.
- **G1:** سناریوی سابق Native Windows با ۹ اجرای محدود تأیید شده؛ علت ریشه‌ای 0xC0000005 هنوز قطعاً ثابت نشده است.
- **G2:** GUI بارگذاری دسته‌ای IFC روی دو مدل مستقل پذیرفته شده، اما پوشش همه گروه‌های الزامی منابع مستقل هنوز بسته نشده.
- **G4:** Windows UAT انسانی با GPU، DPI، مانیتور دوم و Sleep/Resume هنوز NOT VERIFIED.
- **G5:** تصمیم انتشار یک نسخه نهایی Windows باقی‌مانده؛ مدل AI محلی غیرتجاری و هیچ الزام مجوز تجاری AI ایجاد نمی‌شود.

## خلاصه وضعیت پروژه و چت

**رگرسیون جامع ماژول‌های فعال: ACCEPTED**. فاز ۶ همچنان **PARTIAL** تا پوشش باقیمانده G2، UAT فیزیکی G4 و تصمیم انتشار یک نسخه Windows. پیشرفت رسمی پروژه **۸۵٪** و نقشه‌راه **۸ فاز ثابت**؛ PR #34 بدون Merge. هیچ Build یا Release مجاز نشده است.
