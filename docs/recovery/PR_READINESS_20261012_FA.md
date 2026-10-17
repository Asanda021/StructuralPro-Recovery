# ممیزی آمادگی پنج PR، ۱۲ اکتبر ۲۰۲۶

همه PRها در بررسی زنده Draft، باز و ادغام‌نشده‌اند. main برابر 9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95 است. GitHub mergeable=true تأیید Windows/مهندسی یا مجوز Merge نیست.

SHA زنجیره و merge-baseها برابر مبنای PR بعدی‌اند؛ برای هر پنج مقایسه behind_by=0 و status=ahead است. snapshot انتهایی PR #5 در Worktree مجزا مبنای آزمون کامل بود. ادغام واقعی انجام نشده و baselineهای هر PR جداگانه دوباره اجرا نشده‌اند.

| PR | HEAD | مبنا | وضعیت | دلیل |
|---|---|---|---|---|
| #1 | `321bc02db4aaafd827a091b2ccf0760159b481b2` | `9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` | BLOCKED_ENVIRONMENT | ۱۳ عملیات و BOQ در زنجیره نهایی آزموده شدند؛ ثبت فرم نازک‌کاری روی Windows واقعی هنوز تأیید نشده. |
| #2 | `2eb328362d14e36fc4bfb68cb93d422523edebcc` | `321bc02db4aaafd827a091b2ccf0760159b481b2` | NEEDS_FIX | SQLite guarded writes در Linux موفق؛ مسیر Audit پنجره دستی در PRهای فعلی cache قدیمی را بدون digest ذخیره می‌کند. اصلاح واقعی با دو رگرسیون در شاخه تکمیل جدید ارائه می‌شود؛ پذیرش Windows چندپردازشی هم لازم است. |
| #3 | `657392672d09591c8373d78370ddd6e70b764676` | `2eb328362d14e36fc4bfb68cb93d422523edebcc` | BLOCKED_ENVIRONMENT | DOCX RTL و CSV/XLSX/PDF واقعی موفق؛ نسخه واقعی Windows Office و تأیید بصری مالک در دسترس نیست. |
| #4 | `7889609ad8901ab5993ec5d7f42ebdb78a4d80bd` | `657392672d09591c8373d78370ddd6e70b764676` | BLOCKED_ENVIRONMENT | Gate در Linux با BLOCKED_NOT_WINDOWS و exit 2 متوقف است؛ هیچ جعل پلتفرم انجام نشده. |
| #5 | `732d7c16104bf681a350b39e684d9db98da3881e` | `7889609ad8901ab5993ec5d7f42ebdb78a4d80bd` | READY_FOR_OWNER_REVIEW | اصلاح استاتیک fail-closed Symlink/فایل اضافه با رگرسیون موجود معتبر است؛ این وضعیت اجازه Merge نیست. |

## دامنه و ریسک هر PR

### PR #1

BOQ مرکزی پنج مسیر را تغییر داده و فقط work را پرداختی می‌گیرد؛ procurement/material در متره حفظ می‌شوند. نقش ناشناخته fail-closed، واحد و هویت location/floor مهم‌اند. آزمون‌های finish و AI/drawing/revision در مجموعه کامل اجرا شدند.

فایل‌های تغییرکرده:

- `app/main.py`
- `core/platform/application.py`
- `docs/PR481_RECOVERY_20261012_FA.md`
- `scripts/verify_pr481_windows.ps1`
- `tests/test_finish_recovery_pr481.py`
- `tests/test_finish_takeoff_assemblies.py`

### PR #2

قفل BEGIN IMMEDIATE مقایسه و ذخیره را اتمیک می‌کند؛ optimistic conflict به caller برمی‌گردد. retry صریح فقط در آزمون چندپردازشی استفاده شد و به معنای retry خودکار تمام UI نیست. هم‌زمانی همه سرویس‌های برنامه ادعا نشده است.

فایل‌های تغییرکرده:

- `core/platform/application.py`
- `core/projects/store.py`
- `docs/recovery/OFFLINE_QA_CONCURRENCY_20261012_FA.md`
- `scripts/run_offline_recovery_qa.py`
- `tests/test_recovery_13_finishes_five_floors.py`
- `tests/test_recovery_concurrent_takeoff.py`

### PR #3

table_direction و w:bidi/w:rtl واقعی DOCX جایگزین خاصیت نامعتبر direction شده‌اند. هسته محاسبات تغییر نکرده؛ XML صحیح جای آزمون Office واقعی را نمی‌گیرد.

فایل‌های تغییرکرده:

- `core/reports/exporters.py`
- `docs/recovery/OFFLINE_WORKFLOW_REPORT_QA_20261012_FA.md`
- `scripts/run_quarantined_workflow_qa.py`
- `tests/test_recovery_office_export_contract.py`
- `tests/test_recovery_quarantined_workflow_qa.py`

### PR #4

ساخت UI/PDF از سورس و child process برای جلوگیری از crash Qt؛ تصویر و human_visual_approval=PENDING جای پذیرش مالک نیست.

فایل‌های تغییرکرده:

- `docs/recovery/WINDOWS_ACCEPTANCE_STATUS_20261012_FA.md`
- `scripts/run_windows_acceptance.ps1`
- `scripts/windows_acceptance_gate.py`
- `tests/test_windows_acceptance_gate.py`

### PR #5

فقط type/symlink quarantine check و آزمون‌ها تغییر کردند. محتوای Workflows را عوض نکرد؛ تکمیل جدید برای source policy مانیفست ۱۹۳ فایل را هم می‌سنجد.

فایل‌های تغییرکرده:

- `docs/recovery/RECOVERY_EXECUTION_20261012_FA.md`
- `scripts/windows_acceptance_gate.py`
- `tests/test_windows_acceptance_gate.py`

## تصمیم

هیچ PRی Merge نمی‌شود. پذیرش Windows/Office/فرم نازک‌کاری و تأیید صریح مالک پیش‌شرط‌اند. شاخه جدید روی PR #5 قرار می‌گیرد و اصلاح‌های هم‌زمانی Audit و فارسی‌سازی را همراه سازگاری ایمن تست‌ها ارائه می‌کند.
