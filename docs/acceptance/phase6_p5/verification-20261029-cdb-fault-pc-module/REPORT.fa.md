# StructuralPro | فاز ۶، اولویت ۵ | کالیبراسیون ماژول خطاکننده در Native CDB

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**حکم کنترل:** PASS در باینری مصنوعی مستقل، نه درمان کرش محصول. **P6-5 PARTIAL، Windows stability OPEN و native root cause NOT PROVEN.**

## مبنا
در [Run #40830162891](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40830162891) ساخت باینری `synthetic_fault.exe` با `clang-cl` و `lld-link`، تشخیص second-chance `0xC0000005` و وجود پشته Native **PASS** شد، اما فقط دو فریم سیستم بازیابی شد و **نام ماژول دارای دستورالعمل خطاکننده** هنوز تعیین نشده بود.

## اقدام تشخیصی
- ابزار صرفاً تشخیصی `scripts/diagnostics/p6_native_cdb_trace.py` در شاخه PR #34 اصلاح شد؛ کد محصول و آزمون پنج‌طبقه تغییر نکردند.
- در هنگام وقوع واقعی second-chance AV: `.lastevent`، `.ecxr`، `lm a @rip` برای یافتن ماژول حاوی **Exception PC**، `ln @rip` برای نزدیک‌ترین نماد در صورت دسترسی و `kn 32` برای نمونه‌ای از پشته، اجرا می‌شوند.
- عبارت‌های چاپ‌شده برای هر بخش با marker مستقل مرزبندی شده‌اند؛ parser رشته داخل فرمان echoشده Debugger را به‌جای شواهد خطا نمی‌پذیرد.
- فقط نام محدود `module`، در صورت اثبات نام `module!symbol` و حداکثر ۳۲ نماد پشته به Artifact راه می‌یابند. خروجی خام CDB، آدرس‌ها، رجیسترها، مسیرهای دستگاه، اطلاعات شخصی و Dump حافظه در پوشه موقت حذف می‌شوند.
- کنترل `scripts/diagnostics/p6_native_cdb_control.py` اکنون **فقط در صورت تطبیق نام ماژول PC با `synthetic_fault`** PASS می‌شود. دیدن دو فریم سیستم به‌تنهایی برای PASS کافی نیست.

## شواهد واقعی مستقل
- [GitHub Actions Run #40831618324](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40831618324)، HEAD `1cd0d2cd6a853e24bc81332cac8c99785e739f4b`: **completed / success**.
- Artifact: `p6-native-cdb-synthetic-control-no-dump`، ID `12878966497`، ZIP SHA-256 `b8a9af3d4db3bbec21fecca3d840697fe3bea9dd0617472fb1c519abc3366f9a`.
- اصل `control.json` از Artifact دانلود و بررسی شد.

| معیار | نتیجه |
|---|---|
| کامپایل `clang-cl` و لینک `lld-link` | هر دو کد خروج صفر؛ فایل PE ساخته شد |
| `control_second_chance_marked` | `true` |
| `exception_code_verified` | `true`، `0xC0000005` |
| `pc_module` از `lm a @rip` | **`synthetic_fault`** |
| `pc_module_proven_by_lm_address` | `true` |
| `pc_nearest_symbol` | `null`، نام تابع دقیق بازیابی نشده |
| `native_stack_available` | `true`، دو نماد `kernel32!BaseThreadInitThunk` و `ntdll!RtlUserThreadStart` |
| `timed_out` | `false` |
| `test_control_passed` | **`true`** |
| Dump، خروجی خام CDB، حافظه/رجیستر منتشرشده | **هیچ‌کدام** |

**حد استنتاج:** کنترل فوق **اثبات می‌کند ماژول محل PC واقعی** را با استفاده از نقشه بارگذاری‌شده PE استخراج می‌کنیم. بازیابی تابع خطاکننده همچنان فاقد شاهد است؛ پشته غیرنماددار محصول نباید به‌صورت نماد قطعی معرفی شود. این آزمایش هرگز به‌عنوان Crash جدید StructuralPro محسوب نمی‌شود.

## ادامه کنترل‌شده P6-5
تحت همین parser، تنها آزمون‌های محدود واقعی `integrated` و `dialog_commit` در Windows لازم‌اند. نتیجه باید بر اساس Exit، JUnit و Capture تأییدشده تفسیر شود. PASS بدون Crash به معنای درمان خطای متناوب تاریخی نیست. Runهای قبلی [#40764179632](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632) و [#40821287426](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40821287426) همچنان حاوی `0xC0000005` واقعی هستند.

## خلاصه وضعیت پروژه و این گفت‌وگو
- نقشه‌راه دقیقاً **۸ فاز**، پیشرفت رسمی **۸۵٪** بدون تغییر.
- **فاز ۶، P6-5 PARTIAL**، گیت کلی پایداری Windows باز.
- PR #34 باید Open/Draft/Unmerged باقی بماند؛ بدون Merge، ForcePush، تغییر main، ساخت EXE یا ورود به P6-6/فاز ۷.
- در این چت، استخراج نام ماژول دقیق PC کالیبره شد؛ اصلاح کد محصول انجام نشد و منشأ کرش تاریخی نرم‌افزار همچنان نامعلوم است.


## بازآزمایی واقعی StructuralPro با parser کالیبره‌شده
- [GitHub Actions Run #40831568037](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40831568037)، Source SHA `130b2bb6cb92af707a9bd0832b4004b1b5f2100a`، **completed/success**.
- Artifact `p6-live-native-cdb-exception-no-dumps`، ID `12879670460`، ZIP SHA-256 `45c7cade98fdc5d7c09d2a693c128d328fb42fc96842e05b0d37072acee2b354`.
- فایل‌های اصلی JUnit و `summary.json` هر دو بازو از ZIP واقعی خوانده و شمارش شدند:

| بازو | تکرار ۱ | تکرار ۲ | وضعیت |
|---|---:|---:|---|
| Original Qt + SQLite پنج‌طبقه | ۱۶۰٫۹۷ ثانیه | ۱۴۴٫۵۸ ثانیه | هر دو JUnit **۱ PASS** |
| Real ManualTakeoffDialog Review/Commit ۷۰ ردیف | ۱۳۲٫۸۱ ثانیه | ۱۲۲٫۹۵ ثانیه | هر دو JUnit **۱ PASS** |

در هر چهار اجرا `debugger_exit_code=0`، `timed_out=false`، `junit.total=1`، `passed=1`، و `failure=error=skipped=0` ثبت شده است؛ `second_chance_marker=false`، `native_pc_module=null` چون در این اجرای واقعی هیچ استثنای Native بازتولید نشد. **مقدار null در این Run یعنی رویدادی برای نگاشت ماژول وجود نداشته، نه اینکه ابزار نگاشت ماژول شکست خورده باشد.**

**حکم نهایی پس از دو Run:** ابزار `lm a @rip` با خطای مصنوعی واقعی، نام `synthetic_fault` را به‌درستی نشان داد؛ چهار اجرای موردی StructuralPro بدون کرش و با JUnit معتبر PASS شدند. با توجه به وقوع قطعی `0xC0000005` در Runهای تاریخی، **ROOT CAUSE NOT PROVEN، Windows stability OPEN و P6-5 PARTIAL** بدون تغییر می‌ماند.

## خلاصه به‌روزشدهٔ این صفحه
در این نوبت، نخست نام ماژول PC از یک Crash مصنوعی Native روی Windows با کد `0xC0000005` تأیید شد؛ سپس آزمون مرجع و بازوی Commit پنجره واقعی، مجموعاً چهار PASS واقعی زیر همان parser ثبت کردند. هیچ اصلاح محصول، تغییر main، Merge، ForcePush یا انتشار EXE رخ نداد؛ پیشرفت رسمی پروژه **۸۵٪** و نقشه‌راه **۸ فاز** ثابت است. گام بعدی همان P6-5، تمرکز بر **بازتولید ایمن و محدودِ کرش بدون Debugger همراه با checkpointهای مرزی Read/Review/Commit** است؛ هیچ بهینه‌سازی حدسی `catalog()` یا `verified()` به‌عنوان رفع Native AV پذیرفته نیست.
