# StructuralPro | فاز ۶: پذیرش محدود IFC4 با فهرست کامل اعضا

**تاریخ:** ۲۹ اکتبر ۲۰۲۶
**PR:** https://github.com/Asanda021/StructuralPro-Recovery/pull/34
**حکم:** نمایش انتخابی IFC4 در دامنه محدود PASS؛ گیت کلی G2 همچنان BLOCKED، فاز ۶ PARTIAL، انتشار NO-GO.

## پیاده‌سازی واقعی

- core/bim/ifc.py: ورودی اختیاری selected_global_ids برای تولید هندسه فقط از اعضای انتخاب‌شده منبع IFC اصلی، با سقف ۴۰٬۰۰۰ مثلث، کنترل شناسه‌ها، SHA، Revision و قرارداد BIM. مسیر پیش‌فرض تمام مدل حفظ شد.
- core/drawings/source_mesh3d.py: تطبیق کاتالوگ کل اعضای IFC با فهرست هندسه نمایش‌داده‌شده، SHA، Revision و شمارنده‌های وضعیت؛ مغایرت fail-closed است.
- app/ifc_3d_viewport.py: شمارنده‌های تمام اعضای منبع، نمایش‌داده‌شده، بارگذاری‌نشده و فاقد Representation در پنجره سه‌بعدی نشان داده می‌شوند. نمایش هنوز ابزار تعاملی انتخاب Batch یا بارگذاری تدریجی خودکار ندارد؛ پنجره اصلی Open 3D همچنان full-loader است.
- tests/test_phase6_g2_partial_display_ledger.py: انتخاب محدود، اعضای بدون Representation، انتخاب شناسه جعلی/تکراری، سقف ظرفیت، دستکاری Revision/کاتالوگ، تغییر فایل و UI Qt واقعی.

## پذیرش خودکار Linux / Windows

CI https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40897008517، source SHA: 2269101eb3f48efadb9a0072d9e7fe7d4d959e0e، هر دو Job SUCCESS.

| محیط | PASS | FAIL | ERROR | SKIP |
|---|---:|---:|---:|---:|
| Ubuntu 24.04 Qt offscreen | 14 | 0 | 0 | 0 |
| Windows Server 2022 Qt native | 14 | 0 | 0 | 0 |

مجموع ۲۸ PASS هدفمند است، نه کل تست‌ها. JUnit XML از ZIP واقعی هر دو Artifact بازدریافت و مستقل خوانده شد:
- Windows Artifact 12907566439، ZIP SHA256: 91fff02b2d474ad891460039ff0b1d94bbc663563bf805723cae2ae8ae12d681
- Linux Artifact 12907153296، ZIP SHA256: e55d7cea7f5dad07e310575a19bc917b1bbfe4dfb68aa0f9879551257526a2fe

## مدل‌های مرجع مستقل منتشرشده

منبع RWTH-E3D/DigitalHub، commit ثابت 36565d529b4dadeca625de2b793d7e16700171e9، IFC4، با گواهی حجم/Blob/SHA. این فایل‌ها مدل ساختمان واقعی مشتری محسوب نمی‌شوند.

CI https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40897560690، source SHA a0f59826b9037c0203487605eec09131aef2b8b6، هر دو Job SUCCESS. این آزمون دو اجرای CLI محدود با خروجی JSON است، نه JUnit یا UAT انسانی.

| مدل مستقل | کل اعضا | نمایش داده‌شده | بارگذاری نشده | فاقد هندسه | هندسه انتخاب‌شده |
|---|---:|---:|---:|---:|---|
| معماری IFC4 | 957 | 1 | 948 | 8 | IfcWall، 48 مثلث |
| تهویه IFC4 | 1310 | 1 | 1309 | 0 | IfcDuctSegment، 12 مثلث |

هر دو سیستم داده یکسان داشتند؛ Quantity Authority فعال نشد، MapConversion Supported همچنان false، همه اعضای بارگذاری‌نشده و فاقد هندسه در Ledger صریح ثبت شدند.

Artifacts مستقل:
- Windows 12907672902، ZIP SHA256: f8f39f6145c8d64f5ea2744de936429bdf7fa2b67d97a87c5f0c2aeeb72e95d0
- Linux 12907207839، ZIP SHA256: 2b5c1c8f3bf30db22fc048ba425a8c50fd1dfcaddf0569853a769998ab8ffb94

## محدودیت‌های پذیرش و قدم بعدی

مدل معماری در مجموع ۳۴۰٬۹۰۰ مثلث و تهویه ۱۵۹٬۰۷۲ مثلث دارد؛ مدل کامل هیچ‌کدام در Viewer قبول نشده است. این آزمون فقط یک عضو منتخب را از هر فایل با سقف ۴۰٬۰۰۰ مثلث ثابت نشان می‌دهد. کار لازم بعدی در **همین فاز ۶**: انتخاب تعاملی بر اساس طبقه/رشته، مدیریت Batch و جایگزینی امن آن در Worker و Viewer، پاک‌سازی انتخاب عضو خارج از Batch، هشدار ظرفیت قبل از Commit نمای جدید و تست یکپارچه Qt روی مدل‌های بزرگ. نیازی به فاز تازه نیست.

G1 کرش Native ویندوز، G4 UAT فیزیکی، تصمیم یک نسخه نهایی ویندوز و رگرسیون گسترده همچنان باز هستند. بنا بر تصحیح مالک، AI غیرتجاری و آفلاین است؛ مجوز تجاری مدل AI گیت فاز ۶ نیست. مانیفست GGUF فعلی فقط Placeholder دارد و مدل خارجی آماده‌به‌کار از آن اثبات نمی‌شود؛ نبود مدل واقعی با fallback قاعده‌محور و fail-closed مدیریت می‌شود. W6 اختیاری است؛ Office Desktop و چاپ واقعی به فاز ۸ تعلق دارند. هیچ Merge/Force Push/تغییر main/EXE/Release انجام نشده است.

## خلاصه وضعیت پروژه و این چت

نقشه‌راه دقیقاً ۸ فاز، پیشرفت رسمی ۸۵٪ بدون افزایش. این نوبت انتخاب محدود IFC، ledger کامل، هشدار UI، ۲۸ PASS خودکار و دو مدل مستقل در Linux/Windows با محدوده روشن تأیید شدند؛ **فاز ۶ PARTIAL، G2 هنوز BLOCKED، PR #34 Draft/Open/Unmerged**.
