# StructuralPro | فاز ۶، مورد ۳ | پذیرش عملکرد، ذخیره و بازیابی و Qt ویندوز

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**حکم:** مورد ۳ در محدوده **آزمون‌های عملکردی خودکار تعیین‌شده** COMPLETE / ACCEPTED؛ **فاز ۶ به‌صورت کلی هنوز PARTIAL** است. علت کرش متناوب Native ویندوز، UAT مالک و Office دسکتاپ واقعی در این مأموریت اثبات نشده‌اند.

## مبنا و محدودیت دامنه
در این نوبت، Workflows موجود را ممیزی کردیم؛ [Run #40867888956](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40867888956) قبلاً P6-5 E3/E4/E5/E6 را در Linux/Windows با موفقیت اجرا کرده بود و [Run #40868683095](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40868683095) نیز ۴۲ PASS در Windows و ۴۲ PASS در Linux برای انتخاب چهارطرفه مستند داشت. اما ارزیابی مشترک **همان Source SHA جاری**، همراه با بکاپ/بازیابی و PDF/XLSX/DOCX/CSV و مقیاس‌های مختلف Windows Qt، وجود نداشت.

بدون دستکاری Oracle اصلی یا کد محصول، دو فایل تخصصی اضافه شد:
- `scripts/diagnostics/p6_phase6_final_acceptance_gate.py` برای بررسی مستقل XML اصلی هر گروه، حداقل پوشش، وجود نام تک‌تک ماژول‌های مورد انتظار، صفر SKIP/FAIL/ERROR و نبود JUnit مفقود؛ fail-closed.
- `.github/workflows/phase6-final-functional-acceptance.yml` برای اجرای آزمون روی **آخرین Source SHA** در Linux و Windows. در Windows از `QT_QPA_PLATFORM=windows`، `PYTHONFAULTHANDLER=1` و `faulthandler_timeout=0` استفاده شد (تایمر دوره‌ای خاموش، ثبت خطاهای مرگبار روشن). سناریوهای DPI ۱۵۰٪ و ۲۰۰٪ جداگانه اجرا شدند.

## CI واقعی و نتایج قابل حسابرسی
[Run #40870775780](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40870775780) در commit مبنای آزمایش **`7f39ebd00eddb29cc54f04027c2d75473cdd2c53`**: هر دو Job **completed/success**. نسخه کد در همه فایل‌های JUnit یکسان است. هر دو ZIP شواهد دانلود و **JSON گیت و XML هر گروه مستقلاً بازخوانی شد**.

| حوزه آزمون | Linux | Windows | معنای پوشش |
|---|---:|---:|---|
| UI / P1 و 3D / P2 و اتصال چهارسویه / P3، E2 و E5 | ۵۰ PASS | ۵۰ PASS | Qt واقعی/مستند، انتخاب، ابزارها، نما، نشست سه‌بعدی و پنجره‌های شناور |
| عملیات P4 و P5 شامل E3/E4/E6 | ۲۷۵ PASS | ۲۷۵ PASS | ویزارد پروژه، جست‌وجو، CAS، تاریخچه IFC، Undo/Redo و جلوگیری از تغییر نامعتبر |
| پایداری اطلاعات و گزارش‌ها | ۲۲ PASS | ۲۲ PASS | Backup/Restore، رد خرابی SQLite، DOCX/CSV/XLSX/PDF و بررسی داده و RTL |
| SQLite مختص Windows | اجرا نشده در Linux | ۲ PASS | قفل فایل و بازگشایی واقعی بانک در NTFS |
| Qt Windows در DPI ۱۵۰٪ | خارج از دامنه Linux | ۱۰ PASS | پنجره‌ها، Ribbon و Dock در مقیاس ۱۵۰٪ |
| Qt Windows در DPI ۲۰۰٪ | خارج از دامنه Linux | ۱۰ PASS | پنجره‌ها، Ribbon و Dock در مقیاس ۲۰۰٪ |
| **مجموع** | **۳۴۷ PASS** | **۳۶۹ PASS** | **۷۱۶ PASS** |

در **تمام گروه‌ها**: `failed=0`، `errors=0`، `skipped=0` و JUnit معتبر است. هیچ آزمون مفقود یا پوشش ماژول ناقص گزارش نشده است. گیت‌های هر دو سیستم `all_required_suites_pass=true` داشتند.

شواهد:
- [Windows Artifact #12895373560](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40870775780/artifacts/12895373560)، ZIP SHA256 **`cc01a643efe5188689f550f98edc28a769e3fb95815e7b63627e6f8850d65518`**. JUnitهای `views=50`، `operations=275`، `persistence=22`، `win-db=2`، `win-dpi150=10`، `win-dpi200=10` و تصاویر واقعی `p6-p1-win32-dark.png`، `p6-p1-win32-light.png` و E5 Dock.
- [Linux Artifact #12896196654](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40870775780/artifacts/12896196654)، ZIP SHA256 **`e7a1017661d4a78c4eb77b432cd68f0d5512907718cce4a04223c18ec870ce66`**، JUnitهای `views=50`، `operations=275`، `persistence=22` و تصاویر E5 Dock.

**سخت‌گیری گیت:** هر مرحله آزمون برای حفظ شواهد حتی هنگام شکست می‌تواند ادامه یابد، اما مرحله پایانی با `exit 1` هرگونه فقدان JUnit، skip، fail، error، آزمون کمتر از حداقل یا عدم حضور ماژول برنامه‌ریزی‌شده را رد می‌کند. این روش جلوی «سبز شدن ظاهری به‌سبب نبود XML» را می‌گیرد.

## حدود پذیرش و ریسک‌های باز
۱. آزمون‌های فعلی **پروژه نمونه/Fixture واقعی در محیط نرم‌افزار و داده‌های مصنوعی مهندسیِ آزمون‌شده** را بررسی کرده‌اند، نه UAT انسانی با همه مدارک یک پروژه تجاری.  
۲. خروجی‌های PDF/XLSX/DOCX/CSV از نظر ساختار، RTL، وجود داده‌ها و امنیت محتوای خطرناک تست شدند. **بازکردن دستی در Microsoft Office دسکتاپ واقعی، رندر چاپ فیزیکی و ممیزی دیداری تمام صفحات** در این اجرای CI اثبات نشده‌اند.  
۳. خطای Native متناوب تاریخی `0xC0000005` در بررسی‌های P6-5 قبلاً رخ داده است. دو PASS محدود بدون تایمر ۴۵ثانیه‌ای در [#40866225297](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40866225297) و این مجموعه PASSها **علت تاریخی را ثابت یا رفع نمی‌کنند**. بنابراین **Windows native stability gate همچنان OPEN**؛ پذیرش نهایی کل فاز ۶ یا Release از این نتیجه مجاز نیست.  
۴. تست‌ها همه حالات ممکن یا همه خانواده‌ها و انواع IFC موجود در دنیا را پوشش نمی‌دهند؛ فقط ماژول‌های صریح در Workflow ارزیابی شده‌اند.  
۵. هیچ Merge، ForcePush، تغییر main، ساخت EXE یا Release در این مأموریت انجام نشده است.

## تصمیم اجرایی و خلاصه پروژه/چت
- **مورد ۱** از فهرست فاز ۶: آزمایش محدود تشخیصی Windows انجام شده؛ ریسک ریشه کرش Native باز.
- **مورد ۲**: اتصال 2D↔3D↔Tree↔BOQ در دامنه هویت تأییدشده، قبلاً با ۸۴ PASS پذیرفته شد.
- **مورد ۳ در این چت:** **COMPLETE در محدوده عملکرد خودکار**؛ ۷۱۶ PASS و صفر خطا/Skip، با Source SHA واحد، شواهد مستقل، Qt واقعی Windows و کنترل Backup/Restore/Exports.
- **مورد ۴ و گیت کلی فاز ۶:** هنوز باقی است؛ بستن رسمی فاز به وضعیت پایداری Native، دامنه P6-6 و UAT نیاز دارد. **بدون اضافه‌کردن فاز جدید.**
- پیشرفت رسمی کل StructuralPro **۸۵٪** و نقشه‌راه **۸ فاز ثابت** باقی ماند.
- PR #34 باید **OPEN/DRAFT/UNMERGED** بماند. گزارش صرفاً شواهد پذیرش محدود است و مجوز انتشار نیست.
