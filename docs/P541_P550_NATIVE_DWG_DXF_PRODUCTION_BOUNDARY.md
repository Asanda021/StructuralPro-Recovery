# P541-P550 — Native DWG/DXF Production Boundary

## هدف
ایجاد مرز تولید و تبادل CAD برای DWG/DXF به‌صورت deterministic و evidence-first.

## دامنه
- ثبت Project / Revision / Source / Discipline / External ID
- ثبت فرمت و نسخه CAD
- fingerprint دقیق فایل بر اساس بایت‌های واقعی artifact
- fingerprint متادیتای canonical
- round-trip verification با fail-closed behavior
- نرمال‌سازی metadata بدون تفسیر مهندسی

## محدودیت عمدی
این لایه از روی فایل CADِ opaque هندسه، ابعاد، لایه‌های مهندسی، متره، تعداد یا مقادیر طراحی را حدس نمی‌زند. تولید یا تحلیل هندسی واقعی باید در لایه اختصاصی CAD parser/renderer و با evidence قابل ردیابی انجام شود.

## معیار پذیرش
1. fingerprint فایل برای payload یکسان deterministic باشد.
2. رکورد canonical برای داده یکسان fingerprint یکسان بدهد.
3. تغییر artifact یا identity باعث شکست round-trip شود.
4. نسخه ناشناخته DXF fail-closed شود.
5. هیچ مقدار مهندسی یا هندسی اختراع نشود.
