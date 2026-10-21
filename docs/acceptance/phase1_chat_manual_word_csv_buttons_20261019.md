# StructuralPro — فاز ۱ / تکمیل دکمه‌های Word و CSV متره دستی در Chat

- والد و HEAD آزمون‌شده Work: `5a118a967ab95ff5652fc2cf642d4c36e897feb4`.
- شاخه مستقل Chat: `chat/phase1-manual-word-csv-ui-20261019`؛ هیچ تغییر مستقیمی در PR #18 انجام نشده است.
- دو مسیر واقعی رابط: (۱) ریزمتره قابل‌مشاهده در تب ورود تخصصی، (۲) گزارش کامل فرمول دستی در تب کتابخانه/فرمول.
- در `app/manual_takeoff.py` دکمه‌های «خروجی Word ریزمتره» و «خروجی CSV ریزمتره» به `export_visible('docx')` و `export_visible('csv')` متصل شدند. همان صادرکننده مشترک استفاده می‌شود؛ هیچ خروجی یا موتور جدید ایجاد نشده است.
- در `app/manual_formula_controls.py` دکمه‌های «گزارش کامل Word» و «گزارش کامل CSV» به `service.export_manual_formula_report(..., format='docx'/'csv')` وصل شدند؛ این همان API اصلاح‌شده Work در Commit `5a118a967ab95ff5652fc2cf642d4c36e897feb4` است.
- فایل `tests/test_phase1_manual_word_csv_ui_buttons_chat.py` شامل **۴ مورد پارامتری آزمون Qt offscreen** است: کلیک دو قالب در دو مسیر؛ تولید فایل واقعی و بازخوانی DOCX/CSV؛ کنترل وضعیت هشدار و عدم تغییر پروژه، SQLite و BOQ.
- **وضعیت اجرای این چهار تست:** صرفاً ثبت‌شده و نیازمند اجرای Work با PySide6. محیط Chat فعلی PySide6 ندارد؛ هیچ PASS برای آزمون‌های رابط ادعا نمی‌شود.
- آزمون پیشنهادی Work: `QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_phase1_manual_word_csv_ui_buttons_chat.py tests/test_phase1_manual_report_formats.py tests/test_manual_formula_qt_closure.py` و سپس آزمون جامع پس از ادغام صریح در PR #18.
- بدون Merge/Release/EXE/Actions. PR #18 همچنان Draft و در مالکیت Work؛ شاخه Chat صرفاً آماده بررسی و انتقال است.
- پذیرش Windows/Office و بررسی چاپ Excel هنوز باز است؛ ۸ فاز اصلی ثابت‌اند، درصد مدیریتی بدون پذیرش جدید افزایش نمی‌یابد.
