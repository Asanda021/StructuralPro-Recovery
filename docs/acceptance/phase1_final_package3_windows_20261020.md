# دروازه Windows/Office — بسته سوم، ردیف ۱۱

محیط اجرای این تحویل Linux است. PowerShell و Microsoft Office واقعی در دسترس نیستند. LibreOfficeDev 26.8 alpha فقط بازخوانی سازگار Linux است.
اجرای واقعی `python scripts/windows_acceptance_gate.py --out-dir ../final-package3-evidence/windows --preflight-only` با Exit 2 و `BLOCKED_NOT_WINDOWS` پایان یافت؛ هیچ Windows PASS صادر نشد.

روی Windows واقعی، در checkout دقیق HEAD تحویل و Python دارای وابستگی‌های مخزن، بدون ساخت EXE/Release یا اجرای Actions:

```powershell
git status --short
git rev-parse HEAD
python -m pip check
powershell -NoProfile -File scripts/run_windows_acceptance.ps1 -OutputDir qa/windows-final
python -m pytest -q tests/test_phase1_final_desktop_work.py tests/test_phase1_final_report_pagination_work.py tests/test_phase1_manual_word_csv_ui_buttons_chat.py tests/test_shared_report_persian.py tests/test_phase1_manual_report_formats.py tests/test_phase1_work_six_family_service.py tests/test_phase1_package2_service.py --junitxml=qa/windows-final/regression.xml
python -m app.main
```

در نشست دسکتاپ واقعی، متغیر QT_QPA_PLATFORM=offscreen تنظیم نشود؛ probe آزمون همچنان جداسازی HOME و داده مصنوعی دارد. اجرای انسانی برنامه روی کپی پروژه معتبر و پس از ثبت SHA انجام شود. اسکریپت موجود فقط smoke فنی است، نه تأیید بصری یا طراحی.

| کنترل انسانی | مدرک لازم | مسئول | معیار خروج |
|---|---|---|---|
| Windows و PowerShell | نسخه OS/Python/Qt/PowerShell، stdout/JUnit/Exit و HEAD | QA دسکتاپ | صفر شکست در دامنه اجراشده؛ گزارش جداگانه برای SKIP |
| رابط و فونت | تصاویر در DPI 100/125/150/200٪، اندازه حداقل و بزرگ؛ فارسی، اعداد منفی/اعشاری، مسیر دارای فاصله و فارسی | QA و مالک محصول | همه کنترل‌های لازم در دسترس؛ متن خوانا، بدون برش؛ تأیید مستقل |
| Excel/Word واقعی | نسخه Microsoft Office، فایل‌های خروجی دارای SHA، تصویر تمام Sheetها و صفحات حساس | QA Office و بازبین متره | بازکردن/ویرایش/ذخیره کپی؛ تطبیق مقدار/منبع/فرمول و RTL؛ بدون تغییر فایل مرجع |
| چاپ/PDF | نمایشگر PDF واقعی، پیش‌نمایش چاپ و خروجی چاپی نمونه | QA | متن متصل، صفحه‌بندی و اعداد صحیح؛ بدون برش |
| Exit 135 تاریخی | ورودی، ترتیب کار، stderr، faulthandler/core dump یا dump Windows در صورت وقوع | نگهدارنده Qt | بازتولید و علت ریشه‌ای + آزمون قرمز/سبز؛ عدم وقوع به‌تنهایی رفع نیست |

تم روز/شب، Dock شناور و انیمیشن در نسخه فعلی احراز نشده‌اند. بررسی Windows جای پیاده‌سازی قابلیت مفقود را نمی‌گیرد. این نقص‌های رابط ذیل ردیف ۹ باقی می‌مانند.
هیچ آزمون Windows، Office یا چاپ فیزیکی در این تحویل اجرا نشده است. مالی جدید، قیمت فرضی و مجوز انتشار فعال نمی‌شود.
