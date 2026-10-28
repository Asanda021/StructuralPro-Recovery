# شکست‌های مستقل از تغییرات این مأموریت

هر دو آزمون زیر روی مبنای واقعی PR34، `4bdb13dee92b447d5d5431bfd2ccaa0847d3887f`، در worktree دست‌نخورده `/workspace/StructuralPro-P5` و روی کد جدید تکرار شدند: ۲ FAIL، صفر PASS/ERROR/SKIP. JUnit و لاگ هر دو اجرا در همین پوشه‌اند. این شکست‌ها به PASS تبدیل یا از مجموعه جاری حذف نشده‌اند.

1. `tests/test_master13_desktop_shell_runtime.py::test_actual_shell_navigation_calendar_and_ribbon`: انتظار قدیمی عدم وجود هر `QTreeWidget` در کل پنجره با کنترل‌های موجود محصول ناسازگار است. خط assert در اسکریپت subprocess شکست می‌خورد. app/main.py این مأموریت فقط route نشست E4 را افزوده و ایجاد Tree جدیدی ندارد.
2. `tests/test_phase6_p1_font_diagnostics.py::test_qt_glyph_capability_and_render_diagnostics`: Linux فونت `Noto Sans Arabic` را انتخاب می‌کند؛ raw font حروف فارسی و اعداد را دارد اما حروف لاتین `StructuralPro` را ندارد. متن روی صفحه می‌تواند fallback داشته باشد؛ آزمون raw glyph همچنان واقعاً FAIL است. فونت/ترجیحات P6-1 در محدوده مجاز این مأموریت P6-4/P6-5 بازنویسی نشد.

فایل‌های دو آزمون و app/desktop_preferences.py نسبت به مبنای بالا تغییر نکرده‌اند. این دو نقص/قرارداد قدیمی برای ادامه مستقل ثبت می‌شوند. `baseline-existing-failures.xml` و `broad-existing-failures.xml` شاهد واقعی‌اند. گیت تفکیک امن تاریخی می‌تواند PASS باشد، ولی کل QA جاری به علت این شکست‌ها GREEN نیست.
