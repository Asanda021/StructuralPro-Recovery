# فاز ۶، اولویت ۵ | سازگاری بومی Windows و بازاجرای رگرسیون کامل

**تاریخ:** ۲۸ اکتبر ۲۰۲۶. **گیت رگرسیون کامل:** PARTIAL، تا JUnit و Union جدید.

## اجرای گسترده قدیمی و شکست دقیق
- [CI #40681114708](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40681114708) روی source `cfa33bf7ab439b2336889868d17f948378d6761b` با **completed/failure**:
  - Linux کامل: ۸۳۹۹ جمع‌آوری، **۸۳۹۴ PASS، ۵ SKIP، ۰ FAIL**.
  - Windows shard 0: ۳۰۴۰ جمع‌آوری، **۳۰۲۱ PASS، ۱۶ FAIL، ۳ SKIP**؛ بدون timeout، JUnit موجود. ۳ شکست مربوط به import غیرقابل‌انتقال `resource` در Windows؛ ۱۳ شکست مربوط به تفاوت قفل فایل DB باز و غیرممکن‌بودن rename در Windows.
  - Windows shard 1: ۲۶۸۰ جمع‌آوری، **۲۶۷۷ PASS، ۳ SKIP، ۰ FAIL**، بدون timeout، JUnit موجود.
  - Windows shard 2: ۲۶۷۹ جمع‌آوری، **۲۶۷۷ PASS، ۱ FAIL، ۱ SKIP**؛ شکست مهاجرت legacy فاقد منشأ مالکیت قابل‌اعتماد، با ردشدن به‌وسیله گیت `security audit integrity`. JUnit موجود.
  - `verify-full-union` به دلیل شکست دو shard **SKIPPED**؛ هیچ ادعای تأیید پوشش نهایی وجود ندارد.
- جمع Windows قدیمی: ۸۳۷۵ PASS، ۱۷ FAIL، ۷ SKIP از ۸۳۹۹ آزمون. Linux ۸۳۹۴ PASS و ۵ SKIP؛ اختلاف Skipها ناشی از ضوابط سیستم‌عاملی است و به PASS تبدیل نشده.
- Artifactهای Windows: [بخش ۰](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40681114708/artifacts/12812883342)، [بخش ۱](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40681114708/artifacts/12813995927)، [بخش ۲](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40681114708/artifacts/12813326755). [Linux](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40681114708/artifacts/12814380037).

## اصلاحات واقعی و تأیید هدفمند
- `6921e3212816c41d66be206b5dcc8791f56b19b3`، در `tests/test_phase2_priority4_closure.py`: سنجش حافظه پیک با `GetProcessMemoryInfo` واقعی Windows و `resource` Unix؛ اوراکل اندازه و پاسخگویی CAD حفظ شده.
- `bdb090d06c8e978946a8aa845dde8d71d7c9e1b2`، در `tests/test_phase4_sqlite_dbmoved_safety.py`: آزمون قفل فایل باز در Windows، حفظ آزمون DBMOVED واقعی Unix، آزمون افزوده تزریق کنترل‌شده خطای SQLite 1032 و بررسی fail-closed هر دو سیستم، بدون حذف/Skip/XFail.
- `48a85f5d7ae4a88fe8f092a7e0c27be792bf9b9d`، در `tests/test_phase4_sqlite_open_integrity.py`: مهاجرت legacy فاقد مالکیت تأییدشده در Windows نباید بی‌صدا مجاز شود؛ عملکرد بانک جدید همچنان آزموده می‌شود.
- [CI هدفمند دو‌سیستمی #40683427836](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40683427836) روی همین source: **Linux ۳۱ PASS و Windows native ۳۱ PASS، صفر FAIL/SKIP**؛ هر دو `completed/success` و دارای JUnit/Artifact. این قبولی جای رگرسیون گسترده را نمی‌گیرد.
- [Commit workflow جدید `8d42e3238f7affcc09cb55a27995053d98d3ed7a`](https://github.com/Asanda021/StructuralPro-Recovery/commit/8d42e3238f7affcc09cb55a27995053d98d3ed7a) همه refهای قفل‌شده broad را از `cfa33bf...` به source تأییدشده `48a85f...` تغییر داد.
- [CI گسترده جدید #40683854260](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40683854260): Linux کامل + سه Windows shard + گیت `verify-full-union` اجرا شده اما در لحظه گزارش **in_progress**. فقط با موفقیت همه Jobها و JUnit واقعی و Union معتبر می‌توان گیت را PASS کرد.

## وضعیت مانده
- E4: اصلاح مسیر IFC تک‌مقصدی در [CI #40679324114](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40679324114) هر دو سیستم موفق؛ قرارداد DWG و مسیرهای تخصصی فاقد منشأ معتبر PARTIAL/BLOCKED.
- E6: مالکیت مشترک بتن/آرماتور/پوشش و Crosswalk معکوس بدون گواهی مهندسی BLOCKED؛ از ساخت سهم یا تغییر مالی خودداری.
- W1/MEP IFC: PARTIAL، مدل تجاری GGUF و A2: BLOCKED؛ اولویت ۶ هنوز شروع‌نشده.
- پذیرش تخصصی مجدد #40680927992 روی source میان‌راهی در Windows حدود سقف ۷۲۰ثانیه بدون JUnit پایان یافت، درحالی‌که #40679324114 روی source معتبر قبلی هر دو سیستم success بود. نتیجه قدیمی شکست‌خورده همچنان ثبت است؛ CI broad جای گیت تخصصی جدا را بدون شاهد عوض نمی‌کند.
- PR #33 و #34 Draft، Open، Unmerged، main بدون تغییر؛ هیچ Force Push، Merge، EXE یا Release انجام نشده. نقشه راه ثابت ۸ فاز، پیشرفت ثبت‌شده کل پروژه ۸۵٪.

**خلاصه این چت:** ۱۷ شکست قابل بازتولید در سه shard بررسی شد، اصلاحات سه فایل آزمون و Workflow هدفمند ثبت شدند، ۳۱ آزمون واقعی روی Windows و Linux تأیید شد، رگرسیون جدید روی SHA ثابت آغاز شده است. فاز۶ همچنان PARTIAL تا شواهد جامع.
