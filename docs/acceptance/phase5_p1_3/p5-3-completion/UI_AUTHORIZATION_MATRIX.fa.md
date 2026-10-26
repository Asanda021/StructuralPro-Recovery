# ماتریس مسیرهای UI و کنترل مجوز P5-3

مبنای کنترل: همه نوشتن‌های پروژه، از جمله فراخوانی‌های مستقیم قدیمی UI، در نهایت به
`ProjectStore.save` می‌رسند. principal در این مرز از provider سیستم‌عامل گرفته می‌شود و هیچ
فیلد actor، reviewer، approver یا role در UI principal امنیتی ایجاد نمی‌کند.

| دامنه UI | مسیر نهایی | کنترل قابل اعتماد | Audit/نتیجه |
|---|---|---|---|
| ایجاد پروژه | `StructuralProApp.create_project → ProjectStore.save` | هویت OS؛ سازنده Owner همان پروژه | create + Revision 1 + SHA-256 payload در یک تراکنش |
| بازکردن/فهرست پروژه | `get/list` | عضویت ACL همان پروژه؛ فهرست بر اساس subject فیلتر می‌شود | تلاش open نامجاز ثبت و رد می‌شود |
| متره، BOQ، فهرست‌بها و برآورد | سرویس/پنجره‌ها → `save` | Owner/Admin/Editor؛ محافظ‌های BOQ/Revision قبلی حفظ‌اند | update موفق/ناموفق با actor واقعی |
| تأیید مهندسی/اصلاحیه | commandهای review/approve/apply → `save` | review: Reviewer/Admin/Owner؛ approve/apply: Admin/Owner | role، Revision قبل/بعد و reference ثبت می‌شود |
| صورت‌وضعیت و داده مالی | workflow/ledger command → `save` | تغییر مستقیم فیلدهای مالی برای Editor مسدود؛ عملیات نهایی Admin/Owner | payload کامل/محرمانه در Audit ذخیره نمی‌شود؛ فقط هش |
| زمان‌بندی، منابع و دفتر کارگاه | Workspaceها → service → `save` | Owner/Admin/Editor؛ متن actor UI مجوز نیست | مسیر واقعی `ProjectControlsWorkspace` با QTest آزموده شد |
| پیوست و منشأ | `add_project_document → save` | ACL پروژه + فایل regular غیرsymlink + SHA-256 + منع استفاده مسیر در پروژه دیگر | تغییر/حذف فایل در readback با وضعیت mismatch/unsafe آشکار می‌شود |
| انتساب نقش در صفحه همکاری | `grant_role` | principal جاری باید Owner باشد؛ Admin فقط نقش‌های غیرمدیریتی می‌دهد | رویداد authorize با subject هدف و reference ثبت می‌شود |
| Backup کامل SQLite | `ProjectStore.backup` | برای تمام پروژه‌ها Owner/Admin لازم است | SHA-256 و اندازه Backup در Audit؛ Viewer پیش از تولید فایل رد می‌شود |
| Restore | مسیر ایزوله P5-2 | پیش از جایگزینی، Manifest/SHA/Schema/Revision کنترل می‌شوند؛ UI بازیابی مستقیم فایل فعال ندارد | نتایج مستقل P5-2 حفظ شده‌اند |
| Ribbon/Dashboard | همان dialog/serviceهای بالا | مسیر میانبر مجوز جدید ایجاد نمی‌کند؛ Store مرز مشترک است | رفتار معادل مسیر اصلی |

## مرز اعتماد

- Windows: SID از access token زنده thread/process و مالک فایل از Security Descriptor خوانده می‌شود.
- Linux: effective UID کرنل فقط برای آزمون Non-Windows استفاده می‌شود.
- نام کاربری محیط، نام نمایشی و نقش ComboBox منبع احراز هویت نیستند.
- Administrator محلی می‌تواند باینری یا کل فایل SQLite را جایگزین کند؛ این تهدید با SID به‌تنهایی
  قابل حذف نیست و به‌عنوان محدودیت باقی می‌ماند.

