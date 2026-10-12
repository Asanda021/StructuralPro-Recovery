# Priority 22 — Performance & Large Projects

## هدف
آماده‌سازی هسته StructuralPro برای پروژه‌های بزرگ بدون تغییر APIهای قبلی.

## پیاده‌سازی
- chunked processing برای پردازش تدریجی داده‌ها
- pagination استاندارد برای لیست‌های بزرگ
- performance snapshot شامل حجم payload و تعداد رکوردهای هر collection
- تشخیص deterministic پروژه بزرگ
- cache لایه persistence برای کاهش parse تکراری JSON، با invalidation هنگام save
- APIهای performance در Application Service

## اصل سازگاری
APIهای قبلی حفظ شده‌اند؛ قابلیت‌های جدید opt-in هستند و داده پروژه را تغییر نمی‌دهند.
