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

## Windows native: شکست واقعی و شواهد ریشه‌یابی
- Job `current-suite-windows`: **completed/failure** روی کد `76969a29...`؛ `pytest_exit_code=124`، `timed_out=true` پس از ۱۵۰۰ ثانیه، **هیچ JUnit نهایی تولید نشد**؛ `overall_green=false`. این Run نباید PASS حساب شود.
- ZIP واقعی `p6-broad-current-windows-76969a29d295`، Artifact ID `12803392973`، فقط JSON و لاگ اصلی را دارد. ZIP نیز SHA256 `9f3180b6137c699f534e941706ca66edf95cfb2c834af5690b0720b11784d84f` از GitHub Actions گزارش شد.
- توقف در حدود ۹٪، روی `tests/test_bored_pile_real_qt_stabilization.py::test_real_qt_evidence_save_reopen_preview_cas_and_error`؛ faulthandler بعد از ۶۰ ثانیه Stack را در `app/bored_pile_detail_editor.py::run` و `test...py::click` ثبت کرد. پیام QMessageBox احتمالاً توسط timer تک‌نوبتی ۱۰ms قبل از نمایان‌شدن از دست رفته؛ **این علت هنوز فرضیه است**، اما توقف مودال در لاگ اثبات شده است.
- اصلاح پیشنهادی روی Commit `6990c9259eb23de25cad96a641f57413f6306609`: پیام واقعی Qt با `DontUseNativeDialog` و مسیر RTL/دکمه OK؛ آزمون polling کنترل‌شده تا ۳ ثانیه و افزودن دو تست واقعی Pile به CI دو‌سیستمی #40659709412. **هنوز نتیجه CI اصلاح معلوم نیست** و این Commit را PASS نمی‌نامیم.
- رگرسیون Windows کامل باید پس از تأیید هدفمند، روی SHA جدید مجدداً اجرا شود. هیچ فایل JUnit ساختگی یا PASS برای ۹٪ قبل از توقف ثبت نشده است.

## گیت‌های خارج از این CI
- آزمون فیزیکی Windows روی دو مانیتور، GPU/driver و Sleep/Resume `NOT VERIFIED`.
- E4 ناوبری تخصصی فاقد قرارداد مصوب، DWG provenance، E6 مالکیت مشترک، W1 IFC MEP و A2 تجاری `BLOCKED/NOT VERIFIED`؛ رگرسیون گسترده این موارد را مجاز یا COMPLETE نمی‌کند.
- هشت فاز و پیشرفت ثبت‌شده ۸۵٪ ثابت؛ بدون Merge، ForcePush، Release، EXE، P6-6 یا فاز ۷.
