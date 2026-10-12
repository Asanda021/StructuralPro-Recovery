# P401-P410 — Universal Automated Building Takeoff

## هدف
تبدیل خروجی‌های معتبر تشخیص/متره به یک aggregation واحد برای کل ابنیه، بدون اختلاط واحدها و بدون ساخت مقدار جدید از حدس.

## رشته‌ها
Structural (concrete/steel), Architectural, Mechanical, Electrical, Site.

## قرارداد
source/evidence → accepted quantity record → discipline/category/unit aggregation → BOQ

### قابلیت‌ها
P401 قرارداد رکورد متره معتبر
P402 تجمیع چندرشته‌ای
P403 تفکیک واحدها
P404 حفظ منبع و فرمول
P405 fingerprint قطعی
P406 revision delta
P407 fail-closed
P408 regression
P409 integration boundary
P410 production CI

این فاز «اتوماسیون» را در orchestration و aggregation تعریف می‌کند؛ تشخیص هندسه، OCR، DWG/IFC و فرمول‌های تخصصی باید evidence معتبر تولید کنند و این لایه چیزی را حدس نمی‌زند.
