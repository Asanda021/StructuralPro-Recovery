# StructuralPro | P6-5 | کنترل قابلیت ثبت Native CDB و موانع کالیبراسیون
**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**وضعیت قطعی:** CDB برای اجرای آزمون واقعی قابل استفاده است، ولی ثبت استثنای مصنوعی *واقعی* در کنترل مستقل هنوز **تأیید نشده**؛ علت اصلی خرابی محصول **NOT PROVEN**؛ گیت پایداری Windows باز؛ فاز ۶ اولویت ۵ **PARTIAL**.

## نتیجه معتبر اصلی که پیش‌تر به دست آمد
[Run #40826653304](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40826653304) با Debugger و parser اصلاح‌شده `standalone_echo_line_v2`، `completed/success`:
- آزمون کامل اصلی پنج‌طبقه: ۱۶۰٫۳۴ و ۱۵۲٫۰۹ ثانیه، هر اجرا ۱ JUnit PASS، کد خروج صفر.
- فرم واقعی Review/Commit ۷۰ ردیف: ۱۴۳٫۱۹ و ۱۴۶٫۱۲ ثانیه، هر اجرا ۱ JUnit PASS، کد خروج صفر.
- چهار اجرا بدون Timeout، بدون رویداد Native تشخیص‌داده‌شده. Artifact `p6-live-native-cdb-exception-no-dumps`، ID `12877297656`، SHA256 `3a63dc37410633a34dbaac9ecaaa6e3cb9972d104c4d1473792b145d2d20b0c3`.
- کنترل `self-check` parser برای false-positive رد متن فرمان نیز PASS؛ این فقط کنترل منطق parsing است و **به‌تنهایی اثبات نمی‌کند CDB در زمان AV واقعی stack می‌گیرد**.
- شکست‌های قطعی و بدون پروفایلر [#40764179632](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632) و [#40821287426](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40821287426)، با خروجی `0xC0000005` و JUnit مفقود، معتبر و بازند.

## اقدام اجرایی همین مرحله: کالیبراسیون مستقل CDB
هدف بررسی این بود که `scripts/diagnostics/p6_native_cdb_trace.py` در زمان **یک استثنای Native واقعاً رخ‌داده**، صرف‌نظر از وقوع تصادفی خطای StructuralPro، علامت second-chance، کد `C0000005` و stack سمبل‌ها را درست استخراج کند. عملیات فقط در اسکریپت تشخیصی و GitHub Actions، خارج از کد محصول انجام شد.

| Run | اقدام | نتیجه مستند |
|---|---|---|
| [#40828521997](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40828521997) | ایجاد AV مصنوعی از طریق Python/`ctypes.windll.kernel32.RaiseException` در subprocess تحت CDB | **RED**: کنترل، exit=1، بدون علامت second-chance، بدون stack؛ نمی‌توان ادعا کرد AV مدیریت‌نشده تولید شده است |
| [#40828720527](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40828720527) | تلاش برای کامپایل برنامه C کوچک با ابزار Visual Studio شناسایی‌شده از طریق `vswhere` | **BLOCKED**: `BLOCKED_NO_TRUSTED_MSVC_COMPILER`، باینری آزمون ساخته نشد؛ بنابراین کرش کنترل هم اصلاً اجرا نشد |
| [#40828947754](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40828947754) | ممیزی فقط‌خواندنی قابلیت کامپایلر Windows | **PASS**: `visual_studio_detected=true`، `vcvars64_present=true`، `clangcl_on_unmodified_path=true`، `clang_on_unmodified_path=true`، `cl_on_unmodified_path=false` |
| [#40829036130](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40829036130) | اصلاح مسیر کشف VS و افزودن fallback `clang-cl` | همچنان **BLOCKED**: `BLOCKED_NO_TRUSTED_MSVC_COMPILER`؛ یعنی کامپایل از ابزار موجود در این اسکریپت اثبات نشد |

**توضیح مهم درباره بلوکه‌شدن:** وجود `vcvars64` و `clang-cl` از Run ممیزی ثابت است. عبارت `BLOCKED_NO_TRUSTED_MSVC_COMPILER` در کد کنترل چند حالت را یکجا جمع می‌کند: عدم کشف، عدم راه‌اندازی محیط یا خطای compilation/link. به همین دلیل **نباید از آن نتیجه گرفت که Runner واقعاً فاقد کامپایلر است**. چون خروجی کامپایل برای حفظ حریم خصوصی نگهداری نشده، علت دقیق build failure از این شواهد قابل تشخیص نیست. این نتیجه یک نقص در **ابزار کنترل** است، نه خطای محصول.

هیچ Dump، رجیستر، آدرس حافظه، فایل خام Debugger یا داده شخصی در Artifactها منتشر نشد. کنترل مصنوعی هیچ فایل محصول یا داده آزمایشی مهندسی را تغییر نداد.

## حکم پذیرش و قدم بعدی مشخص در همین P6-5
- **Native root cause: NOT PROVEN؛ Windows stability gate: OPEN.**
- ابزار CDB برای اجرای آزمون اصلی و پارس کنترل‌شده خروجی‌های موفق قابل استفاده است، ولی **درستی ثبت crash-site واقعی هنوز کنترل مستقل PASS نگرفته**.
- قبل از تکرارهای پرهزینه محصول، لازم است در یک CI کوتاه فقط مرحله compiler/link `clang-cl` در محیط VC بررسی شود و **نوع خطای build به‌صورت یک کد مرحله‌ای پاک‌سازی‌شده** نگهداری شود. سپس با یک فرآیند مصنوعی Native و خروج واقعی `C0000005`، CDB و sanitizer با معیارهای Marker/Exception/Stack آزمایش شوند. فقط پس از PASS این کنترل، تکرارهای محدود اصلی زیر CDB برای عیب‌یابی فنی قابل اتکاتر خواهند بود.
- این یک گام تشخیصی در **اولویت ۵ همان فاز ۶** است؛ اضافه‌کردن فاز جدید یا بهینه‌سازی حدسی `catalog()/verified()` مجاز نیست. ادعای RED→GREEN برای محصول مطرح نیست.

## وضعیت پروژه و همین گفت‌وگو
Roadmap **۸ فاز ثابت**، پیشرفت رسمی ثبت‌شده **۸۵٪**؛ `P6-5 PARTIAL`. PR #34 باید Draft/Open/Unmerged بماند. بدون تغییر main، بدون Merge، ForcePush، EXE/Release یا شروع P6-6 و فاز ۷. در این گفت‌وگو Run موفق CDB v2 تأیید شد، آزمون کنترل AV واقعی با شواهد قرمز/مسدود اجرا شد و وجود ابزارهای VS/LLVM روی Runner مستقل تأیید شد. **منشأ Native محصول هنوز نامعلوم است**.
