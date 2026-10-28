## نتیجه قطعی GDB پس از دانلود Artifactهای اصلی
- [Run #40756726986](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40756726986) در هر دو Job `focus` و `prefix` **completed/success** است. source checkout: `cd855297af657a382c76909eabad7523688148a2`، manifest `e89de674e5fe212c3472b6e629eea6f23dc1fb8617e41ffee7de26524efde54a`.
- [Artifact focus #12847215975](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40756726986/artifacts/12847215975): دو اجرای مستقل با GDB exit=0؛ هر اجرا ۲۲ testcase / ۲۲PASS، صفر FAIL/ERROR/SKIP، بدون Timeout و بدون ptrace block. زمان‌ها ۱۲۵٫۳۷ و ۱۲۲٫۸۲ ثانیه. در هر دو log پیام `Timeout (0:01:00)!` مربوط به diagnostic faulthandler ثبت شده، نه خروج timeout runner.
- [Artifact prefix #12846751153](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40756726986/artifacts/12846751153): ترتیب اصلی تا آزمون مورد اشاره، ۱۶۰ ماژول، ۲٬۸۷۹ testcase / ۲٬۸۷۹ PASS، صفر FAIL/ERROR/SKIP، GDB exit=0، مدت ۲۸۴٫۷۶ ثانیه، بدون Timeout یا ptrace block. پیام faulthandler ۶۰ ثانیه‌ای باز هم دیده شده ولی آزمون به پایان رسیده است.
- فیلد `native_signal_captured=false` در هر سه JSON، `signal_line=null` و هیچ `Program received signal SIGSEGV` در این سه اجرا وجود ندارد. JUnit همه اجراها موجود و اصل ZIPها بررسی شد.
- **حکم مهندسی:** `NOT REPRODUCED` در سه اجرای bounded؛ `ROOT CAUSE UNDETERMINED`. این نه رفع crash را اثبات می‌کند و نه SIGSEGV اصلی را پاک می‌کند. در نبود backtrace، هیچ patch حدسی در Qt انجام نشد.
- نتیجه مأموریت محدود ریشه‌یابی تا این سطح بسته می‌شود، اما ریسک SIGSEGV تاریخی در گیت عمومی P6-5 همچنان `UNRESOLVED` باقی است. فقط اگر crash دوباره رخ دهد، stack بومی/شواهد جدید مبنای اصلاح خواهد بود.

# فاز ۶، P6-5 | تشخیص بومی SIGSEGV نامنظم Linux (مأموریت محدود)

**تاریخ:** ۲۸ اکتبر ۲۰۲۶. **برنامه:** هشت فاز ثابت، ۸۵٪ ثبت‌شده بدون تغییر. **مخزن:** `Asanda021/StructuralPro-Recovery`. **PR هدف:** #34 Draft/Open/Unmerged.

## شاهد اصلی و حکم مستقل
- [CI شکست‌خورده #40749998943](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943) دقیقاً روی source `cd855297af657a382c76909eabad7523688148a2`، Linux با `pytest_exit_code=-11`، `timed_out=false` و JUnit مفقود پایان یافت. گام `verify-full-union` همان run **SKIPPED** بود. سه shard Windows با صفر FAIL موفق بودند.
- [Artifact اصلی Linux #12842899022](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40749998943/artifacts/12842899022) شامل JSON و log واقعی است. ZIP اصلی مستقلاً بازخوانی شد. آخرین آزمون ثبت‌شده در لاگ `tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports` و حدود ۳۴٪ است؛ پیام faulthandler `Timeout (0:01:00)!` همراه ردیف `<frozen posixpath>:405 in join` پیش از قطع ناگهانی خروجی ظاهر می‌شود. این پیام **native backtrace** نیست و مقصر بودن آن تابع یا تست را اثبات نمی‌کند.
- [Linux بازآزمایی کامل موفق #40751958863](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751958863) روی **همان source**: ۸۴۱۸ PASS، ۵ SKIP، صفر FAIL/ERROR، exit=0، timeout=false؛ Union با Windows برابر ۸۴۲۳ testcase یکتا روی ۷۰۷ ماژول. نتیجه شکست پیشین را پاک یا درمان قطعی قلمداد نمی‌کنیم.
- [CI متمرکز قبلی #40751306233](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40751306233) موفق؛ مسیرهای هدفمند به‌تنهایی حادثه را بازتولید نکردند.

## اقدام تشخیصی واقعی همین نوبت
- Workflow تازه `.github/workflows/phase6-linux-native-gdb-capture.yml` در [Commit `58fdc9e`](https://github.com/Asanda021/StructuralPro-Recovery/commit/58fdc9e1155eaaee9ee976c3964dd914bf8c0406) به PR #34 **بدون تغییر محصول، آزمون‌های قبلی، runner یا main** افزوده شد.
- [CI تشخیصی #40756726986](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40756726986) روی checkout دقیق `cd855297...` اجرا شده است، نه HEAD مستندات PR.
- دو job Ubuntu 24.04 / PySide6 Qt offscreen تحت GDB: `focus` با شش ماژول نزدیک حادثه، حداکثر دو اجرای مستقل؛ `prefix` با ترتیب اصلی همه ماژول‌های current تا و شامل آزمون پنج‌طبقه، یک اجرای محدود. هر کدام روی منبع موقت **بدون Workflow فعال** و بدون Git metadata اجرا می‌شوند؛ ۱۹۳ فایل آرشیوی تغییری نمی‌کنند.
- GDB با محدودیت زمانی، `faulthandler` اصلی، `thread apply all bt 35` و `info sharedlibrary` اجرا می‌شود. در صورت وقوع SIGSEGV و پشتیبانی ptrace، `gdb-*.log` و JUnit واقعی، JSON نتیجه/exit و نخستین آزمون در Artifact قرار می‌گیرند. **هیچ core dump یا حافظه خامی Upload نمی‌شود.**
- Workflow عمداً در صورت SIGSEGV واقعی، خطای pytest، ptrace غیرمجاز یا Timeout شکست می‌خورد؛ سبزبودن این تشخیص به‌تنهایی برطرف شدن باگ را اثبات نمی‌کند.

## وضعیت پذیرش و محدوده
- **در زمان ثبت:** هر دو job در حال اجرای آزمون بومی زیر GDB هستند؛ در این checkpoint ادعای بازتولید یا استخراج فریم قطعی نداریم. در صورت پایان موفق و بدون SIGSEGV حکم `NOT REPRODUCED IN THESE BOUNDED RUNS` است و علت ریشه‌ای `UNDETERMINED` باقی می‌ماند.
- هیچ تغییر حدسی Qt، fixture، timeout یا assert انجام نشده است؛ در صورت یافتن native stack، اصلاح فقط پس از شواهد علی انجام شود.
- P6-5 و قراردادهای E4/E6/W1/A2 همچنان PARTIAL/BLOCKED، و UAT دستگاه فیزیکی مستقل است. PR #33 و #34 Open/Draft/Unmerged، `main=9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95`؛ بدون Merge، ForcePush، Rebase، Release، EXE یا شروع P6-6/فاز۷.

## خلاصه وضعیت پروژه و این چت
مأموریت ریشه‌یابی SIGSEGV از مرحله حدس به **آزمون با دیباگر بومی و ثبت شواهد** منتقل شد. نتیجه قطعی فریم با اتمام اجرای مستقل تعیین می‌شود؛ شواهد قبلی Linux موفق و ناموفق هر دو محفوظ‌اند. نقشه راه ۸ فاز، ۸۵٪ پیشرفت ثبت‌شده و گیت P6-5 PARTIAL تغییر نکردند.
