# رگرسیون جاری فاز ۶ روی آخرین کد تأییدشده E4 | ۲۸ اکتبر ۲۰۲۶

## آخرین شاهد رگرسیون کامل اصلاح مودال، Run #40661082617
- **Source SHA آزموده‌شده:** `6990c9259eb23de25cad96a641f57413f6306609`، workflow trigger `e85fcfbdf990e82d89f28e95a1185821af369c7a`؛ قفل source در Checkout و assert فعال است.
- **Linux completed/success** در [Run #40661082617](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40661082617)؛ JUnit/JSON واقعی: **۸۳۸۰ collected، ۸۳۷۵ PASS، ۰ FAIL، ۵ SKIP مختص Windows**؛ `pytest_exit_code=0`، `timed_out=false`، `overall_green=true`.
- Artifact اصلی `p6-broad-current-linux-6990c9259eb2`، ID `12804826259`، حاوی XML/JSON/Log؛ در زمان کنترل موجود و منقضی‌نشده. SHA256 ZIP برابر `b4fbd77b41079ddf5a4e864d14ca61dfb9b6b3f85a016a1f63cfba919fe6219a` در لاگ رسمی.
- **Windows native در لحظه ثبت همچنان in_progress و JUnit نهایی ندارد**؛ PASS، تعداد آزمون و گیت دو‌سیستمی از آن ادعا نشود. نتیجه شکست/timeout قدیمی Run #40656152367 مربوط به کد `76969a29...` است و پاک یا بازنویسی نمی‌شود.
- CI محدود اصلاح روی `6990c925...` با **۴۷۰ PASS هر محیط** در Run #40659709412 موفق شده، اما جای رگرسیون گسترده Windows و UAT فیزیکی را نمی‌گیرد.
- P6-4/P6-5 هنوز PARTIAL؛ قرارداد تخصصی DWG/IFC، E6 مالکیت مشترک، A2 تجاری و UAT واقعی Windows بازند. ۸ فاز و ۸۵٪ رسمی ثابت؛ PR33/34 باز و Draft؛ main بدون تغییر، بدون Merge/ForcePush/Release/EXE.



## پس از اصلاح مودال واقعی: CI محدود دو‌سیستمی موفق
- **کد و تست اصلاح‌شده:** `6990c9259eb23de25cad96a641f57413f6306609`؛ پیام خطای شمع `QMessageBox` واقعی با `DontUseNativeDialog` و `RTL`، آزمون صریح `QTest` با polling کنترل‌شده، بدون حذف/Skip.
- [CI #40659709412](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40659709412): **completed/success** هر دو Job `ubuntu-24.04` و `windows-2022`. هر کدام ۴۷۰ PASS اصلی، ۱۳۰ historical، ۲۶ security، ۸+۸ DPI؛ صفر FAIL/ERROR/SKIP در تمام بسته‌ها. یک هشدار غیرمسدودکننده `fitz` در بسته اصلی. DPI همان آزمون‌های Dock تکراری است.
- JUnit اصلی Linux SHA256 `cb79ed4251c22dc907ea7dc4fbf8b461dd8bbc9245ad912bfdcd2d950e0f9a13` و Windows SHA256 `f55d8295fa57fd0669afd6df36b80444901ba28ffa97fd404ca23dfbf4a4dca5`؛ Artifactها Linux `12803327667` و Windows `12804475174` از همین Run.
- **رگرسیون گسترده روی کد اصلاح‌شده هنوز نهایی نیست**: [Run #40661082617](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40661082617) روی workflow commit `e85fcfbdf990e82d89f28e95a1185821af369c7a`، کد دقیق `6990c925...` را در Linux و Windows native با همان محدودیت ۱۲۰۰/۱۵۰۰ ثانیه آزمون می‌کند. فقط بعد از JUnit/نتیجه دو Job می‌توان PASS/FAIL قطعی داد.
- شکست Run #40656152367 روی کد قدیمی `76969a29...` حفظ و به PASS تبدیل نمی‌شود. UAT فیزیکی Windows، E4 تخصصی بدون قرارداد، E6 مالکیت مشترک، IFC MEP و A2 همچنان بازند؛ نقشه راه ۸ فاز و ۸۵٪ ثابت.


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
