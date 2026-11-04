# StructuralPro | قرارداد مشترک ممیزی مستقل (Quality Audit Contract)

**نسخه:** 1.0، تاریخ ایجاد 2026-11-02. این سند **فرایند** است، نه گزارش موفقیت، و اجرای خودکار تست را تضمین نمی‌کند.

## اصل بنیادین
- حوزه کد: آخرین شاخه منتخب توسعه و HEAD کامل روی `StructuralPro-Recovery`، معمولاً PR #42؛ از `main` برای ادعای نبودن قابلیت در شاخه توسعه استفاده نکن. شاخه/هویت را در زمان اجرا دوباره تأیید کن.
- ۸ فاز ثابت و ۶ اولویت ثابت فاز هشتم. اسکیل‌ها اجازه تغییر roadmap یا درصد پیشرفت را نمی‌دهند.
- فقط یک نسخه Windows. هیچ Merge، تغییر `main`، Release، EXE و Installer بدون تأیید روشن مالک.
- فایل‌های خصوصی DWG/PDF/IFC/XLSX، قیمت‌ها و داده‌های پروژه به مخزن عمومی/Artifacts عمومی/سرویس خارجی نروند.
- تمایز `Code evidence ≠ test evidence ≠ independent engineering acceptance ≠ permission to ship`.

## واژگان وضعیت
| وضعیت | معنا |
| --- | --- |
| IMPLEMENTED_UNVERIFIED | کد دیده شده اما مسیر عملیاتی پذیرش نشده |
| TESTED_ON_EXACT_SHA | خروجی ابزار و آزمون روی SHA دقیق ثبت شده، با محدودیت دامنه |
| PARTIAL | بعضی شروط تحقق دارند، بعضی بازند |
| MISSING | بعد از بررسی دامنه کامل شاهد کافی برای وجود یافت نشد |
| NOT_TESTED | آزمون لازم اجرا نشده یا ابزارش در دسترس نیست |
| CONFLICTING_EVIDENCE | شواهد ناسازگار؛ بررسی مستقل لازم |
| REAL_ENGINEERING_ACCEPTED | انطباق مستقل مقدار/واحد/منبع و تایید مهندس ثبت‌شده |

## شدت نقص
- **P0:** خرابی/تحریف داده و محاسبه مالی/مهندسی، نقص امنیتی جدی، ثبت بدون تأیید.
- **P1:** گردش‌کار اصلی مسدود یا فقدان پذیرش واقعی الزام انتشار.
- **P2:** اشکال مهم با جایگزین امن و محدودیت افشاشده.
- **P3:** بهبود غیرمسدودکننده.

## قالب یافته
```
Finding-ID: SP-QUAL-0001
Severity: P0/P1/P2/P3
Status: IMPLEMENTED_UNVERIFIED/PARTIAL/MISSING/NOT_TESTED/CONFLICTING_EVIDENCE
Repository/Branch/Full_SHA: ...
Source: path/to/file.py:line1-line2 (or exact symbol)
Expected: ...
Actual: ...
Reproduction: exact commands or manual steps; state if NOT_RUN
Evidence: CI/job/artifact/input SHA or NONE
User/engineering impact: ...
Confidence: high/medium/low + reason
Recommended change: proposal only, never silently applied
Acceptance: test + negative test + real Windows/engineering gate if necessary
```

## ماتریس تصمیم انتشار
- `NO_GO` اگر P0/P1 باز، آزمون واقعی ضروری ناقص، شاخه/SHA مبهم، آزمایش Windows یا Office ناقص یا داده مهندسی نامعتبر باشد.
- `PASS_LIMITED` فقط برای دامنه محدود آزموده‌شده.
- `TECHNICALLY_READY_FOR_OWNER_REVIEW` فقط پس از همه گیت‌ها و با سند کامل؛ انتشار منوط به تایید صریح جداگانه مالک است.

## فایل خروجی گزارش پیشنهادی
`docs/quality/reviews/YYYY-MM-DD_<auditor>_<short_sha>.md` فقط پس از کسب اجازه نوشتن در مخزن؛ در غیر این صورت گزارش در گفتگو یا فایل محلی تولید شود. بدون تبلیغ موفقیت خودکار، بدون دستکاری PR #42.
