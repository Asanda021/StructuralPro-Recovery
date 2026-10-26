# StructuralPro — ادامه بسته‌های باقی‌مانده فاز پنجم در Chat

تاریخ: ۴ آبان ۱۴۰۵ / ۲۶ اکتبر ۲۰۲۶

## دامنه مصوب
مطابق `docs/plans/STRUCTURALPRO_8_PHASE_MASTER_20261020.md` نسخه ۱٫۵، فاز ۵ فقط داده، امنیت و منشأست؛ شمار کل فازها **دقیقاً ۸**. این PR برای ادامهٔ همین فاز است، نه فاز جدید.

- **نسخه واحد Windows:** `ProductEdition.UNIFIED` با همهٔ امکانات موجود و تنظیمات عدم‌دورزدن Marker از طریق Environment؛ Legacy edition adapters برای سازگاری باقی مانده‌اند. هنوز Windows installer قبلی به محصول تک‌نسخه‌ای مهاجرت نشده؛ ادعای انتشار/feature parity نهایی ممنوع.
- **E2 بازیابی جلسه:** استفاده مجدد از `core.platform.autosave` و SHA256 موجود؛ Snapshot فشرده/امنِ نمای سند، عضو، طبقه، تب، فیلتر، zoom و camera، جدا از BOQ. انتشار `os.link` بدون overwrite و cleanup؛ مقابله با خرابی، پروژه/هویت/Revision/منبع متفاوت، داده UI ناامن یا جعلی. `StructuralProApp.save_view_session/restore_view_session` با principal معتبر و سند واقعی پیاده شد. این بخش **زیرساخت داده و بازخوانی** است؛ بازآرایی و اعمال نمای واقعی پنجره‌ها در فاز ۶ طبق نقشه‌راه انجام می‌شود.
- **A1 مجوز/حریم خصوصی AI:** `core/ai/release_gate.py` بررسی صرفاً محلی و بدون network برای وزن GGUF، mmproj و runtime مستقل، SHA256 آنها، مسیر real/no-symlink، فایل واقعی مدرک مجوز با SHA، ادعای تجاری و بازتوزیع، بازبینی حقوقی و تأیید مالک. اجرای پیش‌فرض Unified در `core.ai.local_engine` تا گذر از این گیت **fail closed** است و پاسخ قطعی متره تولید نمی‌کند. قرارداد جدید این ابزار **تصدیق حقوقی مستقل مجوز واقعی نیست**؛ تست با فایل‌های synthetic هیچ مدرک اجازهٔ تجاری برای مدل واقعی فراهم نمی‌کند.

## شواهد
- Run اولیه E2/A1/Unified: [40300423129](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40300423129) موفق، Linux 25 / Windows 7 PASS؛ بدون FAIL.
- اتصال `StructuralProApp` به Store: [40300846782](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40300846782) موفق، Linux 28 / Windows 10 PASS؛ بدون FAIL.
- کنترل مدرک مجوز روی دیسک: [40301024160](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40301024160) موفق.
- اجرای آخرین نسخه‌ی کد: [40301318144](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40301318144)؛ Linux **۲۹ PASS**، نتیجه Windows باید از اجرای واقعی گرفته و پس از پایان تکمیل شود. آزمون جامع ۷۹۰۹ مربوط به PR #26 و قبل از این تغییرات است؛ نسبت‌دادن آن به HEAD جدید ممنوع.

## ریسک‌ها و گیت‌های باز
۱. فایل‌های واقعی مدل/پروجکتور/llama runtime، شواهد مجوز upstream، quantizer و بازتوزیع تجاری و تأیید حقوقی/مالک هنوز دریافت نشده‌اند. **AI تجاری blocked**؛ هیچ مدل یا مجوزی جعل نشود.
۲. ابزارهای legacy edition و اسکریپت‌های بسته‌بندی هنوز در پروژه وجود دارند و مهاجرت نصب واحد نیازمند مرحله بعدی مجاز و Windows acceptance هستند.
۳. E2 پایدارسازی/بازیابی امن داده به سرویس اصلی متصل است؛ نمایش پیام/انتخاب Restore/Discard و چینش واقعی PySide6 به UI فاز ۶ تعلق دارد.
۴. پذیرش مهندسی/Office، تأیید مالک، و تضاد ۱۶ سیاست workflow inherited جدا از این PR باقی‌اند.
۵. کدهای P5-1 تا P5-3 و PRهای #23، #24، #25، #26 یا main تغییر نکرده‌اند. PR #27 Draft، بدون Merge، EXE، Release یا Force Push.

## خلاصه وضعیت پروژه و همین صفحه
فازهای ۱–۳ حفظ؛ فاز ۴ PARTIAL؛ در فاز ۵ بسته‌های قبلی P5-1 و P5-2 در Linux کامل، P5-3 دارای قبولی‌های فنی Linux/Windows و دروازه پذیرش باز؛ بسته‌های تکمیلی Unified/E2/A1 روی PR #27 وارد پیاده‌سازی و تست واقعی شدند. فازهای ۶–۸ شروع نشده‌اند؛ مجموع **۸ فاز ثابت**.
