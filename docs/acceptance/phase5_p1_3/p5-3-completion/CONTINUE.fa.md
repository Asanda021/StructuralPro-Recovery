# ادامه دقیق P5-3

آخرین کد آزموده‌شده: `93f936577b8dcd315410d8d6b283cb9c7aeede48`؛ Tree:
`572dd75aa51db405a7e07d595165faa4f65bc473`.

کار Linux/Non-Windows هویت، ACL، مسیر UI، پیوست و Audit انجام شده است. بدون بازنویسی آن، فقط
این گیت‌ها باقی مانده‌اند:

1. اجرای `test_windows_identity_is_read_from_the_live_access_token` و مسیر PySide6 روی Windows
   واقعی؛ ثبت SID/token و file-owner/locking بدون mock.
2. اجرای جامع یکپارچه روی Tree نهایی فقط اگر سیاست/بودجه بعدی اجازه دهد؛ اجرای جامع این مأموریت
   روی Tree قبل از fix انجام شد و هفت شکست محصولی آن با بسته متأثر ۳۹ PASS بسته شدند.
3. ساخت Backup جدید کد نهایی با Manifest/SHA-256 و آزمون بازدریافت؛ Backup Drive فعلی متعلق به
   مبنای پیش از این Commitهای P5-3 است.
4. Microsoft Office واقعی، پذیرش مهندسی و تأیید مالک مستقل.

`test_recovery_live_policy` و ۱۵ ماژول قرارداد تاریخی به‌علت workflow فعال inherited از PR #25
BLOCKED می‌مانند؛ برای سبزسازی، PR #25 یا workflowها تغییر نکنند.

P5-3 تا عبور از Windows Native و شواهد نهایی بالا PARTIAL است. فاز ۶ آغاز نشود؛ Merge/Release/
EXE/Force Push/تغییر main یا PRهای #23–#25 ممنوع است.

