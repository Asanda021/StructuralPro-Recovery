# StructuralPro | فاز ۷، اولویت ۲ | بسته خروجی واقعی نقشه‌دار

**۳۱ اکتبر ۲۰۲۶** | [PR #36](https://github.com/Asanda021/StructuralPro-Recovery/pull/36)

## محدوده تحویل
کد `core/reports/source_backed_2d_office_bundle.py` تولید واقعی گزارش دفتر فنی را به **صادرکننده‌های موجود** `ProjectReport.export` پیوند می‌دهد. مقدار یا هندسه جدید حدس زده نمی‌شود؛ منبع فقط خروجی Crosswalk تأییدشده SQLite ↔ BOQ از `core/reports/source_backed_2d_overlay.py` است.

برای یک صفحه واقعی و برداشت‌های منتخبِ دارای `BOQ` یکتا، پوشه خروجی شامل:
- `report.pdf` دارای همه جدول‌های فارسی اصلی + یک صفحه تصویر نقشه برداری واقعی
- `report.docx` دارای جداول قبلی و تصویر واقعی نقشه، راست‌به‌چپ
- `report.xlsx` دارای برگه‌های موجود + برگه «نقشه مستند»، تصویر، جدول شناسه عضو/طبقه/BOQ، محدوده چاپ شامل نقشه و تنظیم `fitToHeight=1`
- `report.csv`، خروجی متنی واقعی با UTF-8 BOM، بدون ادعای تصویر داخل CSV
- `overlay.svg` نقشه برداری با برچسب قابل مشاهده عضو و `overlay.png` تصویر حاصل از همان SVG
- `manifest.json` شامل SHA-256 و اندازه تمام ۶ فایل، شناسه پروژه، نسخه پروژه و نشست، هش منبع و پیوندهای مستند `shape ↔ takeoff ↔ BOQ`

## کنترل‌های لازم
- پیش از تولید، `StructuralProApp.open_project` و `ProjectStore.current_digest` و متاداده `_meta.version` کنترل می‌شود.
- تمام خروجی‌ها در پوشه موقت هم‌فایل‌سیستم تولید می‌شوند. پیش از انتشار، digest جاری پروژه، snapshot، قرارداد Crosswalk و هش فایل اصلی دوباره کنترل می‌شوند.
- تغییر حین خروجی، خطای صادرکننده، نبود BOQ معتبر، ابهام ردیف تجمیعی، تغییر SHA، شناسه غیرمجاز یا پوشه مقصد تکراری **Fail-Closed** است؛ هیچ بسته ناقصی منتشر نمی‌شود.
- هیچ‌یک از مسیرهای بانک اطلاعاتی، متره، مالی یا قفل اصلاحیه تغییر نکرده‌اند؛ `quantity_authority=false` و `financial_mutation=false` هستند.
- لیبل داخل SVG به‌عنوان ویژگی **نمایشی** از `member_id` معتبر نمایش داده می‌شود و اختیار اندازه/تأیید جدید ایجاد نمی‌کند.

## شواهد
- [CI اولیه خروجی چهارگانه #41131014911](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41131014911): Linux **۱۳۵ PASS**، فایل‌های واقعی بازخوانی شدند؛ Windows پس از راستی‌آزمایی نهایی تعیین می‌شود.
- [CI اصلاح چاپ Excel #41131137434](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41131137434): دو Job Linux و Windows **SUCCESS**؛ کنترل print area.
- [CI Golden پنج طبقه #41131255692](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41131255692): Linux **۱۳۶ PASS**؛ سناریوی پنج طبقه با فایل PDF پنج صفحه‌ای برداری واقعی در تست و ProjectStore واقعی؛ پنج عضو، پنج ردیف BOQ و پنج بسته مجزای طبقه، کنترل عدم تداخل صفحات، عدم تغییر SQLite.
- [CI با برچسب SVG #41131423252](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41131423252) روی SHA `395b9b3...`: **Linux FAIL با exit 134** در رندر متن QtSvgRenderer بدون QGuiApplication. نتیجه شکست ثبت شد و هیچ Skip/حذف تستی انجام نشد.
- اصلاح: استفاده از **PyMuPDF** موجود برای رندر همان SVG به PNG؛ حذف وابستگی رندر برچسب به QApplication. Commit کد اصلاح‌شده `dc6139f5088eeac349b1aee2435e7ef1f8202f2e`.
- [CI نهایی #41131653006](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41131653006) روی همان SHA: **Windows Native: ۱۳۶ PASS / ۰ FAIL/ERROR/SKIP**؛ **Linux: ۱۳۶ PASS / ۰ FAIL/ERROR/SKIP**. دو Job موفق؛ یک `fitz FutureWarning` قدیمی در هر محیط. شامل تولید واقعی ۶ فایل، بررسی ZIP/DOCX/XLSX/PDF و PNG، Golden پنج‌طبقه و ۱۰ها آزمون صحت منبع و عدم‌دستکاری داده است.

## وضعیت و مرزها
`P7_P2_REAL_OFFICE_BUNDLE=IMPLEMENTED_TARGETED_ACCEPTED`، `P7_P2_FINAL_TARGETED_CI=PASS_WINDOWS_136_LINUX_136`، `P7_P2_OVERALL=PARTIAL` تا تکمیل الزام‌های باقی‌مانده و رگرسیون جامع همان کد.

این Golden **پنج بسته تک‌طبقه از یک پروژه واقعی نرم‌افزاری** است، نه تولید خودکار پلان معماری تمام طبقات؛ برای صدور دسته‌ای در یک بسته چندصفحه‌ای/چندطبقه، نگهداری و نمایش ابعاد و جزئیات هندسی بیشتر، کنترل کیفیت چاپ/فونت واقعی و بررسی Windows/MS Office مرحله پذیرش باقی است. این‌ها تنها در حدود شش اولویت مصوب فاز ۷ و فاز ۸ هستند.

## خلاصه وضعیت پروژه و چت
- فازهای ۱ تا ۵: پذیرش فنی پیشین محفوظ.
- فاز ۶: توسعه/پذیرش خودکار تحویل داده شد؛ آزمون سخت‌افزار و MS Office فیزیکی به فاز ۸ موکول شده، هنوز PASS نیست.
- فاز ۷: اولویت ۱ **AUTO-ACCEPTED** با Linux ۸٬۵۱۰ PASS/۵ SKIP و Windows ۸٬۵۰۸ PASS/۷ SKIP و ۱۲ PASS verify-union در [Run #41127109963](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/41127109963). اولویت ۲ `PARTIAL` و در حال آزمون محصول؛ اولویت‌های ۳ تا ۶ شروع نشده‌اند.
- فاز ۸: شروع نشده. تعداد فازها همان ۸؛ درصد رسمی ۸۵٪ بدون افزایش حدسی.
- PR #34/#35/#36 Draft/Unmerged؛ هیچ Merge، main، EXE یا Release انجام نشده.
