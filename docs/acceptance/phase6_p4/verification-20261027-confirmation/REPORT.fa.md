## ادامه اجرایی معتبر — ایمنی تأیید و نشست W1، ۲۷ اکتبر ۲۰۲۶

آخرین Commit کد/تست: `f84b593a48ab5e20d22a56149fe3687a512c3f0a`؛ Tree: `40df2edd3c19d4de6a4093405b9204e672a3eff3`.
[CI واقعی 40540215367](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40540215367): **SUCCESS؛ Linux Qt ۱۳۵ PASS، Windows Native Qt ۱۳۵ PASS، صفر FAIL/ERROR/SKIP**. شمارش و hash JUnit از noticeهای تولیدشده از XML واقعی در GitHub خوانده و در `verification-20261027-confirmation/ci-40540215367.json` ذخیره شد. این‌ها همان ۱۳۵ سناریو در دو سیستم‌اند. Linux محلی ۱۳۵ PASS و یک FutureWarning مربوط به fitz دارد؛ شمار هشدار pytest ویندوز جداگانه بازیابی نشد. هشدار Node.js Actions با هشدار pytest یکی نیست.

### اصلاح واقعی و RED → GREEN

۱. `app/beam_detail_panel.py`: پس از پیام native Yes/No، هویت/منبع/W1 دوباره کنترل و Revision پیش از پیام برای CAS ثابت نگه داشته می‌شود. پنج RED پیش از اصلاح نشان دادند تغییر/حذف PDF، تغییر Revision/عضو و Cancel در حلقه مودال می‌توانست ثبت ناخواسته انجام دهد. اکنون BOQ و takeoffs خالی، digest پس از ورود به تأیید ثابت و SQLite پس از Reopen برابرند. Preview تیر طبق قرارداد موجود ممکن است پیش‌نویس را ذخیره کند؛ این آزمون به‌اشتباه آن را عملیات بدون نوشتن معرفی نمی‌کند.

۲. `app/graphical_takeoff.py`: guard فرم به Wizard و شیء پیشنهاد آغازکننده مقید شد. سه RED نشان دادند Preview تازه، Wizard تازه یا خاموش/روشن با همان زمینه، guard ورودی ناتمامِ لغوشده را دوباره معتبر می‌کرد. تغییرات ناتمام حفظ می‌شوند و بدون handoff معتبر قابل ذخیره نیستند. Cancel → Restore پذیرفته‌شده قبلی دوباره ساخته نشد.

۳. آزمون‌های واقعی ستون/MEP به هفت تغییر زمینه (bytes/deletion/revision/project/floor/member/proposal) گسترش یافتند. دکمه Save واقعی، هشدار native، digest، BOQ و Reopen بررسی شدند. این‌ها fixture دستی معتبر با PDF مصنوعی‌اند؛ اثبات استخراج هندسی کمیت از نقشه نیستند. برای حذف منبع در Windows، فقط دسته backend PDF پیش از حذف آزاد می‌شود؛ scene و هویت W1 باقی‌اند. حالت فایلِ همچنان قفل‌شده را حذف موفق معرفی نمی‌کنیم.

۴. `scripts/run_phase6_pytest.py` و `scripts/phase6_acceptance_summary.py` خروجی، کد خروج، timeout، تعداد واقعی JUnit، SHA-256، Commit/Tree و شکست‌های محدود را نگه می‌دارند؛ workflow صرفاً پذیرش موجود را اجرا می‌کند. هیچ build/release فعال نشد.

### شکست‌های میانی و محدودیت شاهد

CI 40537988145 روی Windows در ۱۸۰ ثانیه متوقف شد. CI 40539534485 محل شکست آزمون حذف PDF در Windows را ثبت کرد (۲ PASS، ۱ FAIL پیش از توقف maxfail). پس از اصلاح پیش‌نیاز حذف فایل و مهار خطای callback، اجرای نهایی هر دو سیستم سبز است. نتایج لغوشده یا شکست‌خورده موفق شمرده نشده‌اند.

فرمان کلی `pytest -q` در این شاخه هنگام collection با **۱۵ ERROR** متوقف شد: آزمون‌های historical_contracts عمداً مسیر فعال Actions را رد می‌کنند؛ `full-collection.log/xml` نام تمام موارد را حفظ می‌کنند. آزمون یا guard برای سبزشدن ضعیف نشد؛ این مجموعه کلی PASS نیست. بسته پذیرش مشخص‌شده workflow کامل اجرا شد.

نسخه binary Artifact/JUnit ویندوز به‌علت نیاز مسیر دانلود به login از این محیط دانلود نشده است؛ نام و digest بسته در صفحه CI و hash XML در notice واقعی موجود است. JUnitهای محلی این پوشه واقعی‌اند؛ آن‌ها را XML ویندوز معرفی نمی‌کنیم. REST GitHub از پراکسی 403 داشت؛ خواندن Git/Push و صفحات عمومی CI موفق بود. دامنه api.github.com در draft شبکه افزوده شد ولی این به معنی اعمال/انتشار تنظیمات نیست.

### حکم و ادامه

**P6-4 PARTIAL**: گیت‌های آزموده بالا PASS؛ همه IFCهای پیچیده، تمام ترکیب‌های Save/Preview/Commit/CAS و خطای میانی خانواده‌ها، پذیرش هندسی مستقل، مدل تجاری A2 و UAT فیزیکی Windows هنوز بسته نیستند. وزن GGUF و runtime llama_cpp در محیط فعلی وجود ندارد؛ سابقه مدل تصویری با Qwen Research License مجوز تجاری محصول نیست.

اصلاحات محصول پس از این CI با patch ردیابی‌شده به PR34 منتقل می‌شوند و آنجا مستقل آزموده می‌شوند. PR33 باید Open/Draft/Unmerged بماند. بدون Merge، Force Push، main، Release، EXE، P6-6 یا فاز۷؛ هشت فاز و ۸۵٪ ثبت‌شده ثابت‌اند.

---

