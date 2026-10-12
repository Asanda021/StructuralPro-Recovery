# P29 — Real-World Validation

## هدف
اعتبارسنجی یکپارچه مسیرهای واقعی متره/برآورد محصول روی سناریوهای نماینده کوچک، متوسط و بزرگ، با مقایسه deterministic و evidence-first.

## دامنه
- PDF
- CAD
- Revision
- Takeoff
- BOQ
- Estimate
- Reports
- Excel
- Output PDF
- مقیاس‌های کوچک، متوسط و بزرگ

## اصل مهم
P29 هیچ داده مشتری یا پروژه خصوصی را جعل نمی‌کند. Evidence فعلی از Golden Projectهای repository است و صریحاً با همین عنوان ثبت شده است. نبود evidence یا وضعیت غیر-verified باید gate را قرمز کند.

## سناریوهای فعلی
1. ساختمان بتنی کوچک: مسیر quantity → BOQ → estimate.
2. ساختمان بتنی متوسط: persistence/backup/recovery و recalculation.
3. ساختمان بتنی بزرگ: large collection/pagination و integrity.

## Fail-Closed
هر یک از موارد زیر P29 را قرمز می‌کند:
- نبود یکی از مقیاس‌ها
- نبود یکی از سطوح موردنیاز
- reference یا comparison خالی
- status غیر از \`verified\`
- کمتر از سه سناریوی مستقل

## پذیرش
\`pytest -q tests/test_p29_real_world_validation.py tests/test_priority_35_real_world_golden.py tests/test_priority_29_user_validation.py tests/test_priority_14_real_data_validation.py\`

پس از آن CI کامل و Post-Merge Main Verification باید سبز باشند.

## مرز
P29 فقط validation است و منطق طراحی سازه را تغییر نمی‌دهد.
