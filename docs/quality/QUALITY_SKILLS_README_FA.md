# StructuralPro | مهارت‌های تخصصی کنترل کیفیت برای Codex و Claude

**نسخه نخست:** 2026-11-02 | **نوع:** instruction-only skills + validator (هیچ تغییر در موتور StructuralPro)

این بسته سه Skill مستقل و مکمل دارد:

1. `structuralpro-architecture-auditor`: معماری، وابستگی، مسئولیت‌ها، کدهای تکراری، API و UI.
2. `structuralpro-engineering-validator`: نقشه واقعی، هندسه، متره، BOQ، قیمت و صورت‌وضعیت، زمان‌بندی و خروجی‌ها.
3. `structuralpro-release-gatekeeper`: تطبیق SHA/CI، پذیرش Windows، مدیریت blocker و گیت انتشار.

## نحوه استفاده با ChatGPT Work / Codex
فایل‌های `.agents/skills/<name>/SKILL.md` را داخل ریشه مخزن قرار دهید. در محیط Codex یا Work که مخزن را به‌عنوان workspace می‌خواند، اسکیل‌های شناخته‌شده قابل استفاده‌اند. نمونه دستور:

`Use $structuralpro-architecture-auditor to audit the exact HEAD of PR #42, read-only, no merge, with evidence-backed findings.`

## نحوه استفاده با Claude Code
فایل‌های `.claude/skills/<name>/SKILL.md` را در ریشه مخزن قرار دهید. بعد از checkout شاخه دارای این فایل‌ها، می‌توانید از مهارت‌ها در Claude Code استفاده کنید؛ نمونه:

`Use /structuralpro-engineering-validator to validate the actual CAD-to-BOQ chain on current approved branch. Do not modify source.`

در محیط claude.ai معمولی می‌توان هر Skill را جداگانه از فایل ZIP همان مهارت در بخش Custom Skills بارگذاری کرد؛ آن بارگذاری با کشف خودکار Skills در Claude Code فرق دارد.

## نحوه اجرای ممیزی پیشنهادی
1. ابتدا Architecture Auditor روی آخرین SHA واقعی PR #42، بدون هیچ تغییر؛ گزارش خطاها و شواهد.
2. سپس Engineering Validator با fixture مجاز و واقعی (فایل خصوصی در GitHub قرار نگیرد)؛ سناریوی منفی و محاسبه مستقل.
3. در انتها Release Gatekeeper فقط شواهد دو گزارش و CI معتبر را ارزیابی و `NO_GO` یا پذیرش محدود اعلام کند.
4. توسعه‌دهنده پس از تصویب موارد مشخص اصلاح کند. بازبین مستقل نتیجه را مجدداً بررسی کند.

## تضمین عدم واگرایی
متن مهارت‌ها بین `.agents/skills` و `.claude/skills` یکسان است. قبل از هر PR اجرا کنید:

`python scripts/validate_quality_skills.py`

این تست فقط ساختار و انطباق مهارت‌ها را بررسی می‌کند؛ **تست سورس، Windows، متره یا انتشار نیست**.

## سیاست پروژه
- فقط ۸ فاز؛ فاز هشتم ۶ اولویت؛ بدون ساخت فاز جدید.
- یک نسخه نهایی Windows.
- هیچ تغییر در main و هیچ Merge/Installer/Release بدون اجازه مالک.
- هیچ داده خصوصی مشتری یا نقشه واقعی در مخزن عمومی.
- وضعیت `P8P2 PARTIAL/NO_GO` و درصد قبلی ۸۹٫۶٪ را بدون شواهد پذیرش به‌روزرسانی نکن.
- اسکیل‌ها **ملاک روند بررسی** هستند، نه جایگزین برای کارشناسی مهندسی و تست بومی.
