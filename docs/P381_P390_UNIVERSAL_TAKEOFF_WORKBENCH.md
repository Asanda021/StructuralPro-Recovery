# P381-P390 — Universal Multi-Discipline Takeoff Workbench

## هدف
این فاز هسته عمومی متره را از وابستگی به یک رشته خارج می‌کند. StructuralPro برای کل ابنیه/AEC تعریف می‌شود: سازه (بتن و فولاد)، معماری، مکانیک، برق و کارهای سایت/ابنیه جانبی.

## قرارداد عمومی
source → element → takeoff item → review/accept → BOQ

هر آیتم شامل discipline، category، element_type، quantity، unit، source_ids، formula، confidence، revision و status است.

## قابلیت‌های P381-P390
P381 مدل عمومی آیتم متره؛ P382 رشته‌های سازه، معماری، مکانیک، برق و سایت؛ P383 شناسه و fingerprint قطعی؛ P384 ویرایش/افزودن/حذف با کنترل stale state؛ P385 پذیرش/رد و آستانه اعتماد؛ P386 جمع‌بندی رشته‌ای و واحدی؛ P387 حفظ revision/source/formula؛ P388 fail-closed validation؛ P389 regression tests؛ P390 production workflow gate.

## مرز فاز
این فاز موتور تشخیص نقشه یا محاسبات تخصصی هر رشته نیست. محاسبات تخصصی رشته‌ها در لایه‌های بعدی به این workbench متصل می‌شوند.

## اصل
هیچ مقدار بدون منبع پذیرفته نمی‌شود؛ مقدار کم‌اعتماد مستقیماً accepted نمی‌شود؛ مقدار مهندسی هرگز از نبود داده حدس زده نمی‌شود.
