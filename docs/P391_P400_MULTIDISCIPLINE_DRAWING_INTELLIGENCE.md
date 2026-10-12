# P391-P400 — Multi-Discipline Drawing Intelligence

## هدف
یک لایه عمومی برای شناسایی/طبقه‌بندی مستند عناصر نقشه در کل ابنیه: سازه، معماری، مکانیک، برق و سایت.

## قرارداد
منبع نقشه → شواهد صریح → discipline/category/type → confidence → accepted/review/rejected → متره.

### اصول
- فقط شواهد صریح پذیرفته می‌شود.
- نبود شواهد یا مشخصات رشته/نوع، accepted نمی‌شود.
- confidence پایین review است.
- هیچ بعد، اندازه یا مقدار مهندسی از روی حدس تولید نمی‌شود.
- fingerprint و reconciliation برای تغییرات Revision وجود دارد.

## تقسیم P391-P400
P391 مدل طبقه‌بندی عمومی
P392 رشته‌های پنج‌گانه ابنیه
P393 evidence gate
P394 confidence/review gate
P395 deterministic fingerprint
P396 revision reconciliation
P397 fail-closed handling
P398 regression
P399 integration boundary
P400 production CI gate

این فاز موتور OCR/تبدیل DWG یا محاسبات تخصصی نیست؛ آن‌ها فقط با adapter و evidence معتبر به این قرارداد متصل می‌شوند.
