# رگرسیون جاری فاز ۶ روی آخرین کد تأییدشده E4 | ۲۸ اکتبر ۲۰۲۶

## مبنا
- مخزن: `Asanda021/StructuralPro-Recovery`؛ PR #34، Open/Draft/Unmerged.
- **کد محصول و تست واقعاً اجراشده:** `76969a29d29588b4b0a1b1cbf43a81a319958fdf`؛ محافظ تغییر SHA در هر دو Job فعال.
- تغییر workflow فقط: `06f8aeae438a62daeb5fcdd518c9de05695cd079`.
- [GitHub Actions #40656152367](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40656152367) با دو Job مستقل Linux Qt offscreen و Windows native. ۱۹۳ workflow تاریخی در staging قرنطینه می‌شوند؛ اجرای workflow تاریخی، build، release، merge یا تغییر main در این workflow وجود ندارد.

## نتیجه قطعی Linux
- Job `current-suite-linux`: `completed/success`.
- `source_sha=76969a29d29588b4b0a1b1cbf43a81a319958fdf`، `pytest_exit_code=0`، `timed_out=false`، `overall_green=true`.
- JUnit: **۸۳۸۰ collected / ۸۳۷۵ PASS / ۰ FAIL / ۵ SKIP**؛ آن پنج آزمون فقط روی Windows معنی دارند، PASS خوانده نمی‌شوند.
- شواهد واقعی `phase6-broad-current.{xml,json,log}` در Artifact `p6-broad-current-linux-76969a29d295`، GitHub artifact ID `12802725582`، در زمان ثبت منقضی نشده است.
- قبلی روی `7cbeac9b...` برابر ۸۳۷۰ PASS + ۵ SKIP از ۸۳۷۵ بود؛ این نتیجه جدید ۸۳۸۰ مورد را روی کد جدید آزموده و نباید با اجرای قدیمی ترکیب شود.

## Windows native: هنوز گیت باز
- Job `current-suite-windows`: در لحظه این ثبت **in_progress** و بدون JUnit نهایی؛ PASS/FAIL/SKIP یا زمان پایان نامعلوم است.
- پس از اتمام فقط با لاگ/JUnit اصلی و SHA source نتیجه این بخش به‌روز شود. اگر timeout یا failure یا artifact مفقود بود، صریحاً `FAILED/NOT VERIFIED` درج شود، نه PASS.

## گیت‌های خارج از این CI
- آزمون فیزیکی Windows روی دو مانیتور، GPU/driver و Sleep/Resume `NOT VERIFIED`.
- E4 ناوبری تخصصی فاقد قرارداد مصوب، DWG provenance، E6 مالکیت مشترک، W1 IFC MEP و A2 تجاری `BLOCKED/NOT VERIFIED`؛ رگرسیون گسترده این موارد را مجاز یا COMPLETE نمی‌کند.
- هشت فاز و پیشرفت ثبت‌شده ۸۵٪ ثابت؛ بدون Merge، ForcePush، Release، EXE، P6-6 یا فاز ۷.
