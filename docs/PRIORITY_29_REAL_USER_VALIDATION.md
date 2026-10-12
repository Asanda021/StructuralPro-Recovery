# Priority 29 — Real User Validation

این مرحله یک قرارداد ساختاریافته برای ثبت validation واقعی کاربر ایجاد می‌کند.

## اصل داده
Session فقط شناسه تست، نقش تست‌کننده، workflow، outcome و severity را نگه می‌دارد. اطلاعات شخصی، رمز، کلید مجوز یا داده حساس پروژه بخشی از قرارداد نیست.

## Severity
- info
- blocker

وجود حداقل یک observation و نبود blocker شرط ready-for-beta در سطح session است.

این gate جایگزین تست‌های مهندسی یا پذیرش واقعی Windows نیست؛ آن‌ها باید جداگانه با evidence ثبت شوند.
