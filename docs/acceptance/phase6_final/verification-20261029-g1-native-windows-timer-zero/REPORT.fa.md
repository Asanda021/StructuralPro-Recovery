# StructuralPro | فاز ۶، مانع ۲ (G1): کنترل کرش Native Windows

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**PR:** https://github.com/Asanda021/StructuralPro-Recovery/pull/34، وضعیت Draft/Open/Unmerged.  
**دامنه تصمیم:** **ACCEPTED_AUTOMATED_NATIVE_EXIT_SCOPE** برای سناریوی کرش قبلی پس از اصلاح سیاست تایمر تشخیص؛ نه اثبات علت ریشه‌ای همه crashها و نه UAT فیزیکی یا انتشار نرم‌افزار.

## ۱. شواهد واقعی خطای تاریخی

- [Run #40845502382](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40845502382) حاوی **Second-chance 0xC0000005** زیر Microsoft CDB بدون JUnit معتبر است. Stack و module آدرس برنامه در **python312!Py_DumpTracebackThreads، python312!Py_AtExit، python312!PyInterpreterState_Delete** ثبت شده است. این، خطای واقعی بوده، نه صرفاً Timeout یا هشدار متنی.
- [Run #40853080441](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40853080441) با ترتیب symmetric **45s / 0 / 0 / 45s** زیر CDB: اولین اجرای ۴۵ثانیه‌ای به AV خورد، دو اجرای صفرثانیه‌ای PASS شدند و اجرای آخر ۴۵ثانیه‌ای PASS شد. **همبستگی/احتمال تداخل watchdog وجود دارد، اما برهان علّی قطعی نیست**.
- faulthandler مربوط به Python با تایمر dump یک watchdog thread می‌سازد؛ غیرفعال‌سازی خود fault handler لازم نیست. در آزمایش جدید fault handler برای خطاهای واقعی روشن ماند، فقط تایمر دوره‌ای صفر بود.

## ۲. اصلاح ایمنی اعمال‌شده

**کد محصول، فرم دستی، موتور محاسبات، SQLite، BOQ، شیوه ذخیره و آزمون اصلی تغییری نکرد.**

- در scripts/diagnose_windows_native_crash.py گزینه faulthandler-timeout با مقادیر **0/45** افزوده شد و **پیش‌فرض به صفر** تغییر کرد. حالت ۴۵ثانیه‌ای فقط با opt-in صریح تشخیصی اجرا می‌شود؛ شاهد تاریخی همچنان قابل بازتولید است. منشأ کرش به‌صورت حدسی به یک فایل محصول نسبت داده نشده است.
- در pytest.ini مقدار صریح **faulthandler_timeout = 0** ثبت شد. این سیاست، faulthandler.enable و PYTHONFAULTHANDLER=1 را غیرفعال نمی‌کند و فقط از رشته timed dump در مسیر معمول CI جلوگیری می‌کند.
- Workflow اختصاصی .github/workflows/phase6-g1-native-exit-acceptance.yml یک مسیر پذیرش با Windows Server 2022، Python 3.12.10، PySide6 6.12.0، اجرای مستقل فرایندها، JUnit واقعی، SQLite PRAGMA integrity_check، CDB معتبر Microsoft و کنترل source hash است. هیچ heap dump، آدرس حافظه، SQL یا رکورد کاربر منتشر نمی‌شود.

## ۳. نتایج اجرای نهایی روی HEAD تنظیمات ایمن

**Source commit آزموده:** 40d8e18326b9c2e80e79f4dc6524dcf527205d16  
**[Run #40905485780](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40905485780):** Completed / **SUCCESS** هر سه Job.

| Job | تعداد اجرای مستقل | JUnit | Native exit | جزئیات |
|---|---:|---|---|---|
| lifecycle | **۴** | ۴ PASS، صفر failure/error | همگی 0x00000000 | 70 ردیف واقعی synthetic؛ checkpoint نهایی ALL_DONE؛ SQLite PRAGMA integrity_check=ok؛ faulthandler فعال و timeout=0 را probe تأیید کرد |
| integrated | **۳** | ۳ PASS، صفر failure/error | همگی 0x00000000 | سناریوی اصلی پنج‌طبقه بدون تغییر؛ UI، ۷۰ ردیف، SQLite، خروجی و آزمون گزارش؛ بدون Timeout یا AV |
| cdb | **۲** | ۲ PASS، صفر failure/error | بدون second-chance AV | CDB امضاشده Microsoft، ماژول خطا/stack در صورت fault فقط allowlist؛ دو مورد با timer zero؛ بدون Timeout |

**جمع: ۹ اجرای واقعی هدفمند، ۹ JUnit صحیح، صفر crash مشاهده‌شده، صفر timeout.** این عدد شامل آزمون‌های Linux یا تمام حدود ۸۰۰۰ تست محصول نیست. دو Runtime Debugger/no-debugger مستقل، کرش تاریخی در حالت timer45 را در تمام محیط‌ها ناممکن نمی‌کند.

Artifactهای واقعی ZIP دانلود و به‌صورت مستقل JSON/JUnit با XML parser خوانده شدند:

| Job | artifact ID | SHA256 ZIP |
|---|---:|---|
| lifecycle | 12912246494 | dc809d161ad56f5e5dee3c5c7a60a77f2ed65d66af4d75e77c731aeecd7a6b1d |
| integrated | 12911153459 | 2fc8ae78eb3fee174e25879d712b2549bd21e7afbd8b2cb8c54105236db5d518 |
| cdb | 12911048959 | 0710a30658c4c4b4abfc1dd0ae62f1ef2be675d3a8188e72a7bd19f2e005559a |

Run کنترلی قبلی [#40903890369](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40903890369) در HEAD قبل از تغییر پیش‌فرض نیز **۹/۹ PASS** بود؛ نتایج بالا به صورت جداگانه روی سیاست نهایی تکرار شدند.

## ۴. دامنه دقیق پذیرش و مواردی که پذیرفته نشد

- G1 **در دامنه سناریوی native Qt/SQLite قبلاً شکست‌خورده با تنظیم ایمن آزمون، ACCEPTED_AUTOMATED** است. این ادعا «اثبات صددرصدی علت ریشه‌ای 0xC0000005» نیست؛ مدل شاهد historical، تداخل dump watchdog را محتمل می‌کند نه قطعی.
- هیچ بهینه‌سازی حدسی روی GUI یا تغییر عملکرد مالی صرفاً برای پنهان‌کردن crash انجام نشده است.
- تمام سخت‌افزارها و GPUها، چندنمایشگر، Sleep/Resume، درایور مشتری و تأیید مالک هنوز در **G4 UAT واقعی Windows = NOT VERIFIED** هستند و نمی‌توان آنها را با این ۹ آزمون جایگزین کرد.
- گیت مستقل G2 تنوع الزامی همه منابع IFC و رگرسیون جامع در HEAD نهایی هنوز بازند. مرحله ۱ GUI batch در دامنه آزموده‌شده تأیید شده است.
- منشأ AI غیرتجاری است و مدل GGUF واقعی از این تست استنتاج نمی‌شود؛ لایسنس تجاری گیت فاز ۶ نیست.
- هیچ Merge، EXE، Release، Force Push، تغییر main یا شروع فاز ۷ انجام نشده است.

## خلاصه وضعیت پروژه و این گفت‌وگو

**نقشه‌راه همان هشت فاز، پیشرفت رسمی ۸۵٪ بدون افزایش.**  
**مانع ۲:** سیاست ایمن timer=0 + پذیرش خودکار ۹ سناریوی Windows تکمیل. **G1 = ACCEPTED_AUTOMATED_NATIVE_EXIT_SCOPE / ROOT_CAUSE_NOT_PROVEN**. فاز ۶ هنوز **PARTIAL**، چون رگرسیون جامع، UAT واقعی و دامنه پوشش G2 کامل نیست. PR #34 همچنان Draft/Open/Unmerged؛ انتشار NO-GO.
