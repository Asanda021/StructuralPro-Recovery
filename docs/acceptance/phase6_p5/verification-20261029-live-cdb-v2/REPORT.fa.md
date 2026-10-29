# StructuralPro | فاز ۶، اولویت ۵ | Live CDB Native Crash-Site Diagnosis

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**حکم:** **CDB availability DONE؛ CDB parser v2 self-check DONE؛ چهار اجرای CDB با JUnit صحیح PASS محدود؛ ROOT CAUSE NOT PROVEN؛ Windows stability gate OPEN؛ P6-5 PARTIAL.**

## مبنای فنی و نتیجه معتبر پیشین
- [اجرای Baseline بدون profiler #40764179632](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632) روی Windows: تکرار دوم `0xC0000005` واقعی، بدون JUnit، timeout=false.
- [مقایسه هم‌محیط #40821287426](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40821287426): یک `0xC0000005` واقعی در callback بازبینی فرم با JUnit مفقود، به‌علاوه سه PASS. **خطا متناوب و رفع‌نشده** است.
- [سه مسیر مستقل #40822722934](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40822722934): شش PASS محدود Core+SQLite، Qt و آزمون اصلی.
- [پنجره تولیدی واقعی #40824120352](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40824120352): چهار PASS محدود نمایش/انتخاب در برابر Review/Commit روی ۷۰ ردیف.

## ابزار Native قابل اتکا
- [Capability check #40825569901](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40825569901): GitHub Windows Server 2022، **Microsoft CDB نصب‌شده و قابل استفاده**؛ هیچ نصب یا دانلود Debugger انجام نشده است.
- `scripts/diagnostics/p6_native_cdb_trace.py` از `cdb.exe` با Second-Chance Access Violation event handler (`sxd -c2 ... av`) برای بررسی Live stack استفاده می‌کند. اجرای اصلی Qt و آزمون اصلی **تغییر نکرده‌اند**.
- خروجی خام CDB شامل اطلاعات بالقوه حساس است و صرفاً در پوشه موقت Runner نگهداری می‌شود و پیش از پایان اجرا حذف می‌شود. **هیچ Raw log، dump حافظه، مقادیر register یا مسیر شخصی به Artifact منتقل نمی‌شود**. فقط نام سمبل Native، کد استثنا و JUnit اصلی در صورت وجود ذخیره می‌شود.
- پیکربندی CI در `.github/workflows/phase6-windows-cdb-native-trace.yml`: یک Windows Runner، Python 3.12، Qt native، یک مجموعه وابستگی، دو تکرار از Original 5-floor و دو تکرار `dialog_commit`. کنترل Blob ثابت بودن `manual_formula_register.py`، `manual_formula_controls.py`، `manual_takeoff.py`، `store.py` و `test_manual_formula_fivefloor_closure.py` پیش از اجرای آزمون PASS شد.
- محیط Run نهایی از Artifact: Python **3.12.10**، PySide6 **6.12.0**، Qt **6.12.0**، SQLite **3.49.1**.

## نکته مهم: اعتبارسنجی ابزار و اصلاح false positive
در [Run اولیه CDB #40825726101](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40825726101)، Workflow قرمز شد. **سه JUnit با یک PASS و یک اجرای اصلی بدون JUnit پس از ۴۷٫۴۱ ثانیه** در Artifact واقعی ثبت شدند. در آن نسخه parser صرف وجود رشته `P6_AV_SECOND_CHANCE` را علامت AV می‌شمرد. **CDB خود متن فرمان startup (که همین رشته را دارد) را echo می‌کند**؛ لذا ادعای چهار AV از این ابزار **نامعتبر/false positive** است. فریم‌هایی که آن نسخه استخراج کرده، بدون اثبات فعال‌شدن event handler، به‌عنوان crash-site معتبر تفسیر نمی‌شوند. علت نبود JUnit آن تکرار با شواهد موجود هنوز نامشخص است.

اصلاح ابزار، `standalone_echo_line_v2`:
- فقط خط مستقل چاپ‌شده توسط `.echo` (نه رشته داخل فرمان Debugger) به‌عنوان علامت event پذیرفته می‌شود.
- کد `C0000005` فقط در متن بخش پس از نشانگر بررسی می‌شود.
- Self-check صریحاً رد رشته داخل فرمان و پذیرش خط واقعی مستقل را تأیید می‌کند.
- اصلاح صرفاً در ابزار تشخیصی است؛ کد محصول یا رفتار Qt تغییر نکرد.

## نتیجه نهایی معتبر v2

[CI #40826653304](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40826653304) `completed/success` روی Commit `63d1e2e0a8fa8f49c51ba00f053ec70d211319c9` و Artifact `p6-live-native-cdb-exception-no-dumps`، ID `12877297656`، SHA256 ZIP `3a63dc37410633a34dbaac9ecaaa6e3cb9972d104c4d1473792b145d2d20b0c3`.

| بازو | تکرار | زمان Wall | CDB exit | JUnit | Second-chance AV |
|---|---:|---:|---:|---|---|
| integrated original Qt + SQLite | ۱ | 160.34s | 0 | ۱ PASS، صفر FAIL/ERROR/SKIP | ثبت نشد |
| integrated original Qt + SQLite | ۲ | 152.09s | 0 | ۱ PASS، صفر FAIL/ERROR/SKIP | ثبت نشد |
| dialog_commit واقعی ۷۰ ردیف | ۱ | 143.19s | 0 | ۱ PASS، صفر FAIL/ERROR/SKIP | ثبت نشد |
| dialog_commit واقعی ۷۰ ردیف | ۲ | 146.12s | 0 | ۱ PASS، صفر FAIL/ERROR/SKIP | ثبت نشد |

همه `timed_out=false` و `all_valid=true` برای هر بازوی آزمایش، و `native_stack_symbols=[]` چون هیچ استثنای مدیریت‌نشده ثبت نشده است. **وضعیت موفقیت محدود این Run، با وجود دو Run واقعی شکست قبلی، به معنی رفع Native crash نیست.** اجرای زیر Debugger نیز می‌تواند زمان‌بندی فرآیند را تغییر دهد و نرخ وقوع خطا را عوض کند؛ بنابراین نتیجه مثبت، تضمین پایداری بدون Debugger نیست.

## حکم و گام فنی ثابت بعدی در همین P6-5
- **Native cause NOT PROVEN**؛ DLL عامل `0xC0000005` هنوز مشخص نیست؛ هیچ اصلاح محصول انجام نشد.
- گام بعد: در صورت نیاز تکرار هدفمند Debugger روی مسیر Review/Commit با log محدود و checkpoint بی‌تغییر در مرز UI↔service، یا به‌کارگیری crash-site capture به روش تأییدشده دیگری. هر خروجی با JUnit معتبر و کد خروج بررسی شود. هیچ ادعای حل با `catalog()`/`verified()` صرفاً از روی هزینه CPU یا Stack پایتون مجاز نیست.
- کاهش تکرار `catalog()` و `verified()` فقط با Oracle مستقل، RED→GREEN، حفظ اعتبارسنجی Fail-Closed و سنجش unprofiled قبل/بعد قابل اقدام است؛ مسیر جداگانه در همان P6-5.

## خلاصه پروژه و همین چت
نقشه‌راه دقیقاً **۸ فاز**، پیشرفت رسمی ثبت‌شده **۸۵٪**، P6-5 **PARTIAL**، گیت پایداری Windows **OPEN**. PR #34 باید Open/Draft/Unmerged باقی بماند. بدون Merge، تغییر main، Force Push، EXE/Release یا ورود به P6-6/فاز ۷. در این چت قابلیت CDB واقعی احراز شد، اولین آزمون اجرا و خطای تشخیص false positive شناسایی شد، ابزار تشخیصی اصلاح و چهار PASS واقعی در Run دوم ثبت شدند؛ منشأ Native هنوز اثبات نشده است.
