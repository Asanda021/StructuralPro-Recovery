# Phase 19 — Drawing Intelligence

## هدف
اتصال عملی و قابل ممیزی بین منبع نقشه، تشخیص شیت، تشخیص مقیاس، ناحیه/زون،
ابعاد صریح، تشخیص المان مهندسی و اندازه‌گیری هندسی.

## Implementation
- `core/drawing/phase19.py`
- orchestration روی adapterهای موجود و Drawing Intelligence موجود
- حذف داده‌های تکراری پیش از تحلیل
- sheet detection
- scale evidence و fail-closed conversion
- explicit dimension evidence
- zone/region identity
- engineering element recognition
- measurement → element → BOQ-key linkage
- export قابل استفاده برای مراحل بعدی
- هیچ مقدار مهندسی از داده مبهم حدس زده نمی‌شود.

## Fail-Closed Rules
1. نبود مقیاس معتبر → اندازه‌گیری مهندسی خودکار متوقف می‌شود.
2. نبود واحد نقشه → تبدیل به واحد مهندسی متوقف می‌شود.
3. نبود ارتباط source-id بین اندازه‌گیری و المان → لینک BOQ ساخته نمی‌شود.
4. داده تکراری قبل از تحلیل حذف می‌شود، بدون تغییر معنای هندسی.

## Tests
`tests/test_phase19_drawing_intelligence.py` پوشش می‌دهد:
- sheet/zone/dimension detection
- scale و measurement linkage
- duplicate suppression
- missing-scale fail-closed
- missing-unit fail-closed

## Gate
Phase 19 فقط پس از:
Implementation → Tests → CI → Merge → Post-Merge Main Verification
سبز اعلام می‌شود.
