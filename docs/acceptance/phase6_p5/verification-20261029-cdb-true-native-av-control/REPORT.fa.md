# StructuralPro | فاز ۶، اولویت ۵ | اثبات واقعی کالیبراسیون Native CDB

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**حکم این مأموریت:** **CONTROL PASS** برای ساخت Native و تشخیص second-chance Access Violation واقعی، بدون Dump. **علت Crash محصول NOT PROVEN، پایداری Windows همچنان OPEN، P6-5 PARTIAL.**

## مسئله و مرز مأموریت
در [Run #40828521997](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40828521997) کنترل `ctypes.RaiseException` نتوانست second-chance AV معتبر ایجاد کند. در [#40828720527](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40828720527) و [#40829036130](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40829036130) ساخت باینری مستقل در کنترل آزمایشی مسدود شد. ممیزی محدود [#40828947754](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40828947754) نشان داد `Visual Studio`، `vcvars64.bat` و `clang-cl` وجود دارند، اما `cl.exe` در PATH اولیه نیست. از این رو ادعای «نبود کامپایلر روی Runner» مستند نبود.

برنامه آزمایشی باید **خارج از کد محصول** و در فرآیند موقت خود، عمداً در ویندوز Access Violation ایجاد کند. از این مسیر فقط برای اثبات صحت مشاهده Native CDB استفاده می‌شود، نه برای پذیرش محصول.

## اصلاح ابزار، بدون دستکاری StructuralPro
فقط اسکریپت `scripts/diagnostics/p6_native_cdb_control.py` به نسخه جدید با روش ساخت **headerless / no-CRT** تغییر کرد:
- یک فایل C حداقلی، بدون `windows.h`، وابستگی به SDK header، CRT، Qt، Python extension، SQLite یا کد StructuralPro.
- کامپایل مستقیم با `clang-cl.exe` و تولید object؛ لینک مستقل با `lld-link.exe` (با fallback مجاز `link.exe` در صورت نصب).
- `/entry:main`، `/subsystem:console`، `/nodefaultlib`: عدم نیاز به تنظیم پیچیده `vcvars64`، کتابخانه‌های SDK و CRT.
- دسترسی عمدی به آدرس نامعتبر صرفاً در پردازش موقت و **تحت Microsoft CDB**.
- خروجی کامپایلر هرگز به GitHub Artifact منتقل نمی‌شود؛ فقط شناسه ابزار، کد خروج مرحله، وضعیت فایل‌های خروجی و شماره خطاهای ابزار در قالب allowlist ثبت می‌شود.
- خروجی خام Debugger در TemporaryDirectory باقی می‌ماند و پس از خواندن پاک می‌شود. فقط کد استثنا و حداکثر ۲۰ نام `module!symbol` از خروجی پاک‌سازی‌شده نگهداری می‌شود. هیچ Dump، مقدار رجیستر، آدرس حافظه، متن فرمان حاوی مسیر کاربر یا اطلاعات خصوصی آپلود نشده است.

**SHA مرجع دست‌نخورده** در همان شاخه:
- `core/takeoff/manual_formula_register.py`: `4e3750a0e797073d40bacb395e448da4f14b6c56`
- `app/manual_formula_controls.py`: `07e8ce4567eec5122253cd220a49fed6e2e27d9e`
- `tests/test_manual_formula_fivefloor_closure.py`: `f81c979051bcbaaf00015fa411314e28f370b291`

## اجرای واقعی و شواهد
- [GitHub Actions Run #40830162891](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40830162891)، HEAD زمان اجرای کنترل `246113f85f20e0226bf26c90515d248e7e959d00`: **completed / success**.
- Artifact: `p6-native-cdb-synthetic-control-no-dump`، شناسه **`12877844706`**، ZIP SHA-256 **`57b6c66f85599c90a389c06fac5e27bc55d9dd588a8fa559de64216c63e94c5b`**.
- اصل رکورد `control.json` از Artifact دانلود و خوانده شد؛ نه فقط رنگ CI.

| معیار واقعی | نتیجه |
|---|---|
| `compiler` | `clang-cl`، یافت شد |
| `linker` | `lld-link`، یافت شد |
| `compile_return_code` | `0`؛ object ساخته شد |
| `link_return_code` | `0`؛ PE اجرایی ساخته شد |
| `debugger_present` | `true` |
| `timed_out` | `false` |
| `control_second_chance_marked` | `true` |
| `exception_code_verified` | `true`، `0xC0000005` |
| `native_stack_available` | `true` |
| `native_stack_symbols` | `kernel32!BaseThreadInitThunk`، `ntdll!RtlUserThreadStart` |
| `test_control_passed` | **`true`، CONTROL_PASS** |
| `memory_dump_written` / `raw_debugger_logs_uploaded` | `false` |

**حد شواهد Native:** حضور دو نماد سیستم ثابت می‌کند parser بخشی از پشته Native را از خطای واقعی استخراج کرده است. هنوز حضور ماژول `synthetic_fault` در فهرست نمادها ثبت نشده و **اثبات استخراج تابع دقیق faulting module یا یک stack کامل نماددار نیست**؛ رفع این محدودیت در تشخیص آینده باید جداگانه سنجیده شود.

## حکم فنی و قدم بعدی در همان اولویت ۵
۱. **کالیبراسیون ایجاد خطای Native واقعی و ثبت second-chance، کد 0xC0000005 و stack محدود: PASS.**  
۲. **رفع Access Violation متناوب StructuralPro: اثبات نشده**؛ crashهای بدون profiler در [#40764179632](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632) و [#40821287426](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40821287426) همچنان معتبرند.  
۳. قدم بعدی بدون ایجاد فاز جدید: بهبود استخراج نام **ماژول خطاکننده** از آدرس PC در خروجی CDB با روش پاک‌سازی‌شده و کنترل با باینری مصنوعی، سپس فقط تکرار **محدود** سناریوی اصلی زیر Debugger معتبر. در صورت عدم بازتولید، دلیل کرش همچنان باز می‌ماند.  
۴. اصلاحات حدسی به `catalog()` یا `verified()`، تغییر قرارداد ۸۵ خانواده، Merge، ساخت EXE یا Release ممنوع تا شواهد و گیت‌های پذیرش کافی.

## خلاصه پروژه و چت این صفحه
- نقشه‌راه ثابت **۸ فاز** و پیشرفت رسمی **۸۵٪**، بدون تغییر.
- **P6-5 PARTIAL**؛ گیت پایداری Windows همچنان باز؛ P6-6 و فاز ۷ شروع نشده‌اند.
- **PR #34** باید Open/Draft/Unmerged بماند؛ بدون تغییر main و Force Push.
- در این چت مشکل کالیبراسیون از سطح «شکست ساخت برنامه تست Native» به **موفقیت کامپایل/لینک و شناسایی واقعی Access Violation تحت CDB** ارتقا یافت. کد محصول دست‌نخورده است؛ ریشه خطای محصول هنوز نامشخص است.
