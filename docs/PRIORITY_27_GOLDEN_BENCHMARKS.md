# Priority 27 — Golden Projects / Benchmark

هدف این مرحله تبدیل benchmark از فهرست قابلیت‌ها به acceptance gate قابل اجراست.

## Golden Cases
- takeoff-basic
- project-recovery
- estimate-report

هر case دارای شناسه، شرح و کلیدهای خروجی مورد انتظار است. اجرای benchmark deterministic است و در صورت exception یا missing contract key شکست می‌خورد.

## Acceptance
یک مجموعه فقط زمانی ready است که تمام caseهای ثبت‌شده pass شوند. این gate ادعای پوشش کامل محصول را نمی‌کند؛ فقط سناریوهای طلایی تعریف‌شده را اندازه‌گیری می‌کند.

## اصل
Golden benchmark نباید مقدار مهندسی را جعل کند؛ داده واقعی یا fixture معتبر باید توسط هر تست تخصصی فراهم شود.
