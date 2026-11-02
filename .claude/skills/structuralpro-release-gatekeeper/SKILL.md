---
name: structuralpro-release-gatekeeper
description: Enforce evidence-backed StructuralPro Windows release gates across the fixed eight-phase roadmap, PR #42, real CAD/Office QA, CI SHA integrity, data safety, and explicit owner approval. Use before completion claims, merge, installer, EXE or release.
---

# StructuralPro | نگهبان کنترل کیفیت و انتشار

**Immutable safety flags:** `NO_MERGE / NO_MAIN_WRITE / NO_EXE / NO_INSTALLER / NO_RELEASE` تا زمانی که مالک صریحاً مجوز دهد.

## سیاست غیرقابل مذاکره
StructuralPro **فقط یک محصول نهایی Windows** و **۸ فاز ثابت** دارد. فاز هشتم شش اولویت ثابت دارد؛ تعریف فاز ۹، اولویت جدید یا تغییر درصد بدون مصوبه ممنوع. وضعیت تاریخی گزارش‌شده قبل از پذیرش کامل P8/P2 حدود **۸۹٫۶٪** بود؛ عدد جدید فقط پس از اثبات و محاسبه وزنی معتبر و تأیید مالک ثبت شود.

به‌صورت پیش‌فرض **NO_MERGE / NO_MAIN_WRITE / NO_EXE / NO_INSTALLER / NO_RELEASE**. حتی CI سبز، یا این Skill، مجوز عمل به جای مالک نمی‌دهد. صریحاً از مالک برای هر اقدام نشر/ادغام اجازه بگیر. بررسی read-only را بدون انتظار برای اجازه انجام بده؛ عملیات نوشتن خارج از دامنه‌ مجوز فعلی انجام نشود. فایل‌های خصوصی را به مخزن عمومی نبر.

## گیت‌های لازم برای اظهار آمادگی
1. **منشأ واحد:** `repo`, `base`, `head branch`, `full SHA`, worktree clean/dirty، رابطه PRهای زنجیره‌ای و وضعیت Merge/Draft. فقط تست روی **همان SHA نهایی کد** قابل استناد است؛ تغییر code بعد از CI → گیت بازآزمایی.
2. **CI معتبر:** همه jobهای موردنیاز Linux و native Windows، shardها، JUnit union واقعی و کد خروجی بررسی شوند؛ `timeout`, `skip`, `xfail`, `deselected` و flaky tests با دلیل جداگانه گزارش شوند. Job status به‌تنهایی معادل تمام آزمون‌های سبز نیست.
3. **داده:** real SQLite commit/rollback/crash/backup/restore، CAS و source SHA، stale snapshot و حقوق دسترسی؛ test fixtures و دیتابیس بدون تغییر غیرمجاز، خطای P0 صفر.
4. **مهندسی:** CAD واقعی (از جمله مسیر DWG مجاز و object coverage)، PDF/IFC و فایل‌های مستقل، measured quantities و financial reconciliation، 2D/3D/Tree/BOQ، مسیر E2E پنج‌طبقه با تأیید مستقل. Synthetic pass را در ردیف جدا نگه دار.
5. **GUI Windows:** PySide6 روی Windows واقعی، کلیک تمام کنترل‌های اصلی، بستن پنجره هنگام worker، Ctrl/Undo/Redo، DPI، RTL، تم روشن/تاریک، فونت فارسی، و کنترل performance/cancel.
6. **Office / print:** خروجی‌های PDF، XLSX، DOCX، CSV روی برنامه‌های بومی و پیش‌نمایش چاپ بررسی شوند؛ جمع‌ها و Manifest در برابر SQLite/BOQ مستقل کنترل شوند.
7. **AI:** GGUF/model/license hash، local-only behavior، no-guess، human approval gate، fail-closed و prompt injection boundary؛ مدل اختیاری نباید مسیر محاسبات اصلی را تخریب کند.
8. **Product packaging:** بدون نسخه‌های تجاری چندگانه، API مخفی، دکمه بی‌عملکرد یا وابستگی حیاتی آنلاین؛ install/uninstall/update، migration، backup و rollback فقط با اجازه مالک و آزمون واقعی.

## قواعد تصمیم
- `P0` یا `P1` باز، تستِ لازم اجرا نشده، DWG واقعی بدون پذیرش، اختلاف مالی بدون توجیه، تست Windows/Office ناقص یا وضعیت SHA نامعتبر → `NO_GO`.
- CI سبز در دامنه محدود → `PASS_LIMITED`، نه `RELEASE_READY`.
- فقط وقتی همه گیت‌های لازم با شناسه شواهد و تایید مهندس بسته شده باشند، می‌توان وضعیت `TECHNICALLY_READY_FOR_OWNER_REVIEW` داد؛ این **مجوز Release نیست**.
- اگر ابزار برای تست/مدرک وجود ندارد، `NOT_TESTED` و `NO_GO` بده؛ موفقیت نساز.

## خروجی الزام‌آور
گزارش فارسی با `Repo/PR/HEAD SHA`، `Gate matrix (PASS/FAIL/PARTIAL/NOT_TESTED)`، لینک CI دقیق و تعداد واقعی tests، evidence references، blocker P0/P1، موارد قابل تعویق P2/P3 با دلیل، وضعیت ۸ فاز و شش اولویت فاز۸ بدون تغییر دلخواه، حکم صریح `NO_GO/PASS_LIMITED/TECHNICALLY_READY_FOR_OWNER_REVIEW` و `Owner authorization: NOT_REQUESTED/REQUIRED/GRANTED`.

قبل از هر ادعای تکمیل، قرارداد `docs/quality/QUALITY_AUDIT_CONTRACT_FA.md` را اعمال کن؛ اگر موجود نیست، گزارش آن را ثبت کن، حدس نزن.
