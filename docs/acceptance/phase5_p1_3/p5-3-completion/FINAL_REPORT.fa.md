# گزارش نهایی مأموریت تکمیل P5-3

تاریخ: ۴ آبان ۱۴۰۵ / ۲۶ اکتبر ۲۰۲۶

PR #26 همچنان Draft، Open و Unmerged است. آخرین Commit کد آزموده‌شده
`93f936577b8dcd315410d8d6b283cb9c7aeede48` و Tree آن
`572dd75aa51db405a7e07d595165faa4f65bc473` است.

## تصمیم

**P5-3 همچنان PARTIAL است.** کنترل‌های قابل‌اجرای Linux/Non-Windows تکمیل و آزموده شدند،
اما آزمون واقعی Windows access token/SID و مسیر UI روی Windows Native در این محیط در دسترس
نبود. یک mock/test provider جای آن به‌عنوان PASS معرفی نشده است.

## تغییرات محصول

- `core/platform/identity.py`: هویت Windows از access token زنده و SID؛ هویت POSIX از effective
  UID کرنل. متغیر محیطی و متن UI منبع احراز هویت نیستند. مالک فایل legacy در Windows از
  Security Descriptor سنجیده می‌شود.
- `core/projects/store.py`: ACL پروژه‌ای، نقش‌های Owner/Admin/Editor/Reviewer/Viewer، کنترل مرکزی
  همه save/get/list/revision/backup، تفکیک عملیات review/approve/apply، و جلوگیری از تغییر مستقیم
  داده‌های مالی/تأییدشده.
- همان Store، Audit زنجیره‌ای persistent با SHA-256، head/count، trigger منع UPDATE/DELETE و
  کنترل startup دارد. Audit موفق با پروژه در یک تراکنش است؛ شکست Audit، ذخیره را Rollback می‌کند.
- `core/platform/application.py` و `app/main.py`: provider معتبر به برنامه تزریق می‌شود؛ ثبت سند
  واقعی با regular/no-symlink، SHA-256، project binding و تشخیص تغییر/حذف انجام می‌شود؛ انتساب
  نقش صفحه همکاری از ACL ممیزی‌شده می‌گذرد.
- `core/projects/audit.py`: actionهای open/authorize به موتور سالم موجود افزوده شد؛ موتور موازی
  ساخته نشد.

جزئیات مسیرهای UI در `UI_AUTHORIZATION_MATRIX.fa.md` ثبت شده است.

## RED → GREEN

REDهای واقعی شامل نبود مرز هویت، امکان Backup توسط Viewer، نبود SHA پیوست در مسیر واقعی UI،
عدم تشخیص دستکاری persistent Audit هنگام reopen، و امکان تلاش مستقیم Editor روی مجموعه مالی بود.
پس از اصلاح، بسته هدفمند اصلی **۱۱۶ PASS، صفر FAIL/ERROR و یک SKIP Windows** داشت.

رگرسیون جامع روی Commit `a7e432b6cce966b63c498da6a7dfb683cf0fbd64` و Tree
`6ccc88fd4340c18798d722466a496896525d44da` یک‌بار اجرا شد:

- ۷۹۰۴ PASS
- ۸ FAIL
- صفر ERROR
- ۸ SKIP
- ۶۵۹٫۶۴ ثانیه

یک FAIL همان `test_recovery_live_policy` و BLOCKED شناخته‌شده ناشی از workflow فعال inherited
از PR #25 بود. هفت FAIL محصولی عبارت بودند از یک قرارداد متنی UI و شش تعارض با قرارداد no-op
کامل ورودی مهندسی نامعتبر. اصلاح حداقلی روی Commit نهایی انجام شد: ردهای امنیتی/مجوزی همچنان
Audit می‌شوند، اما خطای صرفاً اعتبارسنجی مهندسی هیچ تغییری در پروژه، Revision یا SQLite نمی‌دهد.

بسته دقیق متأثر روی Commit نهایی: **۳۹ PASS، صفر FAIL/ERROR و یک SKIP Windows** در ۲٫۱۶ ثانیه.
طبق محدودیت مأموریت، رگرسیون جامع دوم اجرا نشد؛ بنابراین آمار ۷۹۰۴ را نتیجه کامل Tree نهایی
معرفی نمی‌کنیم. JUnitها:

- `full-final.xml`، SHA-256: `1a95c5f69943fc2e3564eb06a33c8e27b2de5e06e4509cc82e19c64c7fcf660f`
- `post-regression-fix.xml`، SHA-256: `2a1be58f8d9d401192a980271410d87754374dbeff4de767f7dc4d35e1de06df`
- `policy-ui-targeted.xml`، SHA-256: `c1b732d96f8e957ee02e6c9c95661f1b2413bce72a74bf0cb507cfe0fa5cbd37`

محیط: Linux 6.18.55 x86_64، Python 3.12.14، SQLite 3.53.1، pytest 9.1.1،
PySide6 6.12.0 و IfcOpenShell 0.9.0.post1.

## وضعیت ممیزی و Fail-Closed

- principal خالی/نامعتبر، Viewer write، جعل actor UI، self-promotion و cross-project access رد شدند.
- Audit موفق و Revision اتمیک‌اند؛ خطای Audit موفقیت کاذب تولید نمی‌کند.
- حذف/تغییر Audit با trigger مسدود و دستکاری offline در reopen کشف می‌شود.
- هیچ رمز، token یا payload کامل پروژه در Audit ذخیره نمی‌شود؛ actor OS، role، reference، نتیجه،
  Revision و SHA-256 ثبت می‌شوند.
- SID هویت نشست محلی Windows است، نه MFA یا احراز هویت مستقل. Administrator محلی که بتواند
  باینری و کل SQLite را با هم جایگزین کند خارج از این مرز اعتماد است.

## اولویت‌ها و دروازه‌های باز

| اولویت | وضعیت | توضیح |
|---|---|---|
| P5-1 | COMPLETE — Linux/Non-Windows | کنترل‌های قبلی SQLite/transaction تغییر ماهوی نکردند؛ آزمون‌های وابسته سبز ماندند. |
| P5-2 | COMPLETE — Linux/Non-Windows | Backup/Restore قبلی حفظ شد؛ کنترل ACL Backup و ۱۷ آزمون وابسته سبز شدند. |
| P5-3 | PARTIAL | پیاده‌سازی Linux و مسیر واقعی PySide6 تکمیل؛ Windows Native NOT VERIFIED و full suite نهایی پس از fix اجرا نشده است. |

بکاپ Drive قبلی P5-2 با ID `1TMm1YgEfugGXh1Pc0CrwFIrpMcjNAVbu` همچنان شاهد معتبر نسخه
قبلی است، اما Commitهای تازه P5-3 را در خود ندارد؛ آن را بکاپ کد نهایی معرفی نمی‌کنیم.

Windows Native، Microsoft Office واقعی، پذیرش مهندسی پروژه واقعی و تأیید مالک مستقل و بازند.
هیچ Merge، Release، EXE، Force Push، تغییر main/PR23/PR24/PR25 یا Actions دستی انجام نشد.

## وضعیت هشت فاز

فازهای ۱ تا ۳ حفظ شدند. فاز ۴ به‌علت عامل تاریخی ناشناخته SQLite و دروازه‌های مستقل همچنان
PARTIAL است. فاز ۵: P5-1 و P5-2 در Linux کامل و P5-3 PARTIAL است. فازهای ۶، ۷ و ۸ آغاز
نشده‌اند. نقشه‌راه دقیقاً هشت فاز و محصول نهایی یک نسخه کامل Windows باقی مانده است.

