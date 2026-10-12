# P57 — DWG/DXF Real-World Validation

این فاز قرارداد اعتبارسنجی Evidence برای فایل‌های CAD را اضافه می‌کند. هدف، اثبات‌پذیر کردن زنجیره DWG/DXF → extraction → recognition → quantity است؛ نه ادعای اینکه هر فایل CAD بدون تست واقعی به‌صورت کامل متره می‌شود.

Evidence مورد انتظار:
- فایل واقعی DWG یا DXF و SHA-256 آن
- layerها
- entity/geometryها
- block/insertها
- dimensionها
- text/tagها
- زمان استخراج و منبع

مواردی که باید روی پروژه واقعی کنترل شوند:
1. لایه‌ها و نام‌گذاری آن‌ها
2. LINE/POLYLINE/CIRCLE و سایر هندسه‌ها
3. BLOCK/INSERT و شناسه اعضا
4. DIMENSION و مقدار اندازه‌گذاری
5. TEXT/MTEXT و تگ‌های اعضا
6. duplicateها و geometryهای ناقص
7. ارتباط هندسه با عضو و در نهایت quantity

این فاز هیچ نتیجه واقعی یا Accuracy جعلی تولید نمی‌کند. تست واقعی فقط با فایل‌های واقعی پروژه انجام می‌شود.

Regression این فاز صرفاً سلامت قرارداد و نرم‌افزار را اثبات می‌کند، نه پوشش تمام فرمت‌ها یا همه نرم‌افزارهای تولیدکننده DWG/DXF.
