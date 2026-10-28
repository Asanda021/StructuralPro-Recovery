# گیت E4: جلوگیری از ناوبری دوبل جست‌وجوی IFC | ۲۸ اکتبر ۲۰۲۶

## دامنه اجرای واقعی
- مخزن: `Asanda021/StructuralPro-Recovery`، شاخه PR #34، Draft/Open/Unmerged؛ هیچ تغییر در main/PR33/Merge/Release.
- **Commit کد و تست**: `69dcdd09aa8963bc694638ea912417b263540608`.
- نقص قابل مشاهده در کد پیشین: دکمه تخصصی «نمای IFC عضو» در `ProjectSearchDialog.open_model`، `open_record()` را صدا می‌زد؛ `open_record` نیز در حضور `on_navigate` ناوبری عمومی را اجرا می‌کرد و سپس مسیر IFC جدا فراخوانی می‌شد. دو مقصد ناخواسته ممکن بود باز شوند.
- اصلاح در `app/project_search_panel.py`: پارامتر `navigate=True` برای مسیر موجود حفظ شده، اما دکمه تخصصی با `open_record(navigate=False)` هویت/نسخه و نمایش فقط‌خواندنی را بازبینی می‌کند و صرفاً `on_open_model` را فراخوانی می‌کند.
- آزمون جدید Qt در `tests/test_phase6_p5_e4_ui.py::test_ifc_button_dispatches_only_verified_model_destination`: منبع عضو IFC بازبینی‌شده موجود، کلیک QTest واقعی، انتظار فقط یک فراخوانی تخصصی، بدون تغییر Digest یا BOQ. نتیجه مستقل همین آزمون تا ثبت JUnit **NOT VERIFIED**؛ وجود Commit به معنی PASS نیست.
- آزمون دو‌سیستمی جدید: [CI #40679324114](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40679324114)، در لحظه تهیه گزارش **in_progress**؛ فقط بعد از نتیجه واقعی هر دو Job و XML پذیرش بدهید.

## گیت‌های معتبر جداگانه و حدود آنها
- روی source قبلی `facbe18af8f051e52cac250410b72f688655f7a9`، [CI تخصصی #40676687306](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40676687306) هر دو Linux و Windows native **completed/success**: هرکدام ۴۹۱ PASS اصلی، ۱۳۰ تاریخی، ۲۶ امنیت، ۸+۸ DPI تکراری، صفر FAIL/ERROR/SKIP؛ تنها هشدار غیرمسدودکننده fitz.
- [CI گسترده #40676687299](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40676687299) روی source قبلی `facbe18...`: Linux **۸۳۸۶ collected / ۸۳۸۱ PASS / ۵ SKIP مختص Windows / ۰ FAIL**؛ Windows در لحظه گزارش **in_progress**. این CI نتیجه کد تازه `69dcdd...` نیست.
- E4 ناوبری PDF/DXF/IFC دارای هویت و مدرک در دامنه قبلی آزموده شده، اما DWG فاقد قرارداد منشأ تبدیل و تمام مسیرهای تخصصی همچنان PARTIAL/BLOCKED. این اصلاح فقط دوشاخه‌بودن کلیک مسیر IFC را برطرف می‌کند.
- E6: Split/Merge و تاریخچه append-only با شواهد مصنوعی مستند و CAS/rollback موجودند؛ مالکیت مشترک بتن/میلگرد/پوشش و Crosswalk معکوس بدون قرارداد معتبر **BLOCKED** باقی می‌مانند. نسبت یا مقدار حدسی نباید ساخته شود.
- W1/IFC MEP: نگاشت مهندسی ناقص **PARTIAL**. A2 GGUF واقعی: وزن/مجوز/منشأ تأییدشده موجود نیست، **BLOCKED**.
- P6-6 هنوز آغاز نشده؛ پذیرش انسانی Windows روی دستگاه مالک در گیت مستقل خود باز است.

## نقطه ادامه و پذیرش
۱. از آخرین SHA واقعی PR #34 و نتیجه GitHub Actions جدید شروع شود؛ هیچ CI قدیمی به Commit تازه تعمیم داده نشود.
۲. در صورت PASS هدفمند E4، فقط همان گیت قابل پذیرش است؛ رگرسیون گسترده روی SHA جدید باید مستقل اجرا شود.
۳. گیت‌های E4/E6/W1/A2 بدون ورودی و قرارداد معتبر FAIL-CLOSED بمانند؛ برای P6-6 یا فاز ۷ کار آغاز نشود.
۴. پس از هر تغییر Implementation → Tests → CI → Evidence → کنترل PR33/PR34/main رعایت شود.

**خلاصه وضعیت پروژه و چت:** گیت E4 ناوبری دوبل اصلاح و آزمون Qt افزوده شد، پذیرش CI نسخه تازه هنوز در جریان است؛ سایر موانع فاز۶ مشخص و بازند. نقشه راه دقیقاً ۸ فاز و پیشرفت ثبت‌شده کل پروژه ۸۵٪ ثابت است.
