# Priority 19 — Finance & Payment Depth

## هدف
تکمیل لایه مالی پروژه از «ثبت و گزارش» به کنترل عملیاتی پرداخت، بودجه و جریان نقد؛ بدون شکستن API و داده‌های مالی موجود.

## قابلیت‌های جدید
- ثبت پرداخت واقعی با شناسه پایدار PAYxxxxx
- تخصیص پرداخت به سند مالی یا تعهد با شناسه ALCxxxxx
- جلوگیری قطعی از تخصیص بیش از مبلغ پرداخت
- وضعیت مشتق‌شده پرداخت: unallocated / partial / allocated / cancelled
- بودجه‌بندی پروژه به تفکیک کد و دسته
- مقایسه بودجه، تعهد و هزینه واقعی
- تشخیص دسته‌های خارج از بودجه
- کنترل جریان نقد تاریخی/برنامه‌ای بر اساس تاریخ
- نمایش ورود نقد، خروج نقد، تعهدات آتی، خالص نقد و حداقل مانده تجمعی
- snapshot یکپارچه برای داشبورد و کنترل مالی
- خروجی گزارش مالی جدید با قرارداد گزارش‌دهی موجود

## یکپارچگی با نسخه‌های قبلی
- داده‌های commitment_entries, cost_entries, receipt_entries و financial_documents حفظ شده‌اند.
- پرداخت‌های جدید در payment_entries و تخصیص‌ها در payment_allocations ذخیره می‌شوند.
- financial_budget به صورت مستقل نگهداری می‌شود.
- رفتار APIهای قبلی تغییر داده نشده است.
- این مرحله وارد محاسبات سازه‌ای یا طراحی مهندسی نمی‌شود.

## APIهای اصلی
- add_project_payment
- allocate_project_payment
- project_payments
- project_payment_summary
- add_financial_budget_line
- project_budget_control
- project_cash_flow_control
- project_finance_payment_depth_snapshot
- project_finance_payment_depth_report

## کنترل‌های صحت
- مبلغ‌ها باید finite و non-negative باشند.
- شناسه پرداخت و تخصیص یکتا است.
- تخصیص فقط به پرداخت موجود انجام می‌شود.
- مجموع تخصیص یک پرداخت نمی‌تواند از مبلغ پرداخت بیشتر شود.
- لینک سند/تعهد/طرف حساب قبل از ثبت پرداخت بررسی می‌شود.
- کد بودجه تکراری پذیرفته نمی‌شود.
- وضعیت‌های پرداخت محدود و deterministic هستند.

## تست
فایل: tests/test_priority_19_finance_payment_depth.py

سناریوهای پوشش داده‌شده:
- partial/allocated payment
- over-allocation rejection
- budget planned/committed/actual variance
- over-budget detection
- cash-flow cumulative balance
- application persistence
- invalid references
- duplicate budget codes
- duplicate/unknown allocations
- report export
