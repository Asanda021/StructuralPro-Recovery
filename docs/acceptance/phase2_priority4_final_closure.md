# بستن اولویت ۴ فاز ۲ StructuralPro

قرارداد ثابت: فقط معیارهای A تا G مالک، بدون ورود به اولویت۵ یا تغییر هشت فاز. داده‌ها مصنوعی و صریح‌اند؛ هیچ نقشه مصوب یا امضای واقعی مهندس معرفی نمی‌شوند.

## هویت نسخه

HEAD اولیه `7ebe8505ecffcc1b81995670ba2e576a3ce090e6`؛ PR18 فقط خواندنی `3434f63ee3718f6399bbf06bc8ca7a2c6a835b29`.
کد نهایی GitHub `f0bf3eec998d391ddaf62c81f827f73c9d7913dc`، کاندید محلی آزموده `1524399cd6414729bd2bdd3721ff2b7b45b2dd26`؛ Tree دقیق `7912f377e3d7129f5b247f49a492161b6e91c0f5`.
Commit تحویل حاوی همین گزارش فقط شواهد است و SHA آن از Git قابل خواندن است؛ زیر‌درخت‌های اجرایی/آزمون با کد بالا برابرند. تفاوت SHA محلی و GitHub مربوط به metadata Commit است.

| معیار | وضعیت | شاهد |
|---|---|---|
|A|COMPLETE|Qt event loop timestamps; 10k/50k/100k; cancel/replace/error/close/staged-page; five lifecycle cycles|
|B|COMPLETE|native RTL document dialog; source and evidence SHA; actual unit reference; independent author/reviewer; SQLite/CAS/undo/redo/empty draft|
|C|COMPLETE|array rotation/mirror/nonuniform scale oracle; real DWG MINSERT; native child highlight; parent-child batch/history rejection|
|D|COMPLETE|source-coordinate oracles and explicit negative entity/format matrix|
|E|COMPLETE|TEXT/MTEXT RTL, real rotated Block, native screenshots, DPI 1 and 1.5, disclosed system font fallback|
|F|COMPLETE|real binary AC1032 30m to BOQ then existing immutable amendment 40m; SQLite/reopen/CAS; converted-DXF duplicate red/green|
|G|COMPLETE|full accepted JUnit/tree and separate Dropbox restore receipt|

## تغییرات و معماری حفظ‌شده

یک موتور و یک مسیر مالی: `DWG/DXF → DWGTakeoffEngine → DrawingTakeoffSession → StructuralProApp / ProjectStore → BOQ`.
Parsing و استخراج در subprocess قابل‌لغو QProcess اجرا می‌شود؛ Worker فاقد Qt/نوشتن پروژه است. نتیجه در فایل خصوصی والد تولید و در بسته‌های۱۰۰۰جزئی دریافت می‌شود؛ QGraphicsItemها فقط در رشته اصلی و بسته‌های۱۲۸جزئی ساخته می‌شوند. نقشه قبلی تا موفقیت کامل محفوظ است. درصد ساختگی وجود ندارد: مرحله تحلیل نامعین، سپس تعداد واقعی دریافت/ساخت نمایش داده می‌شود. لغو، تعویض منبع، خطای میانه Parsing و بستن Worker آزموده شدند. کنترل صفحه، نشست، Undo/Redo و BOQ هنگام بارگذاری مسدود است؛ شکست چیزی در SQLite نمی‌نویسد.

مدرک واحد JSON با policy `cad_unit_reference_v1` شامل SHA منبع، واحد، Handle طول مرجع، cad_length، real_length_m، author/reviewer مستقل و reference است؛ path/SHA مدرک در نشست و متره محفوظ است. ضرایب شناخته‌شده با Decimal برای تطبیق مدرک و داده source float با حد نسبی1e-12 کنترل می‌شوند. واحد معلوم فایل تغییر نمی‌کند؛ تعارض و فقدان مدرک Fail-Closed است. تغییر واحد روی متره قبلی ممنوع؛ نشست/اصلاحیه نسخه‌دار مستقل لازم است. حتی پیش‌نویس خالی واحد را پس از بازگشایی حفظ می‌کند.

MINSERT با هویت پایدار `Handle@row,column/child`، فاصله، دوران، Scale و آینه از همان ezdxf گسترش می‌یابد. چرخه، عمق/تعداد بیش از قرارداد، spacing نامعتبر، واحد متناقض Block و Z نامجاز رد می‌شوند. جمع والد از اجزای مالی مجاز و مستقل است؛ متن مقدار مالی ندارد. انتخاب والد تمام فرزندان قابل نمایش را Highlight می‌کند. پرداخت والد/فرزند هم در یک Batch و هم در سوابق، تغییر کد/عضو/Handle و استفاده دوباره از DXF تبدیل‌شده کنترل می‌شود. سوابق اصلی و اصلاحیه‌های اعمال‌شده در تطبیق منشأ استفاده می‌شوند؛ دفتر موازی، قیمت حدسی یا Schema جدید ساخته نشده است.

CIRCLE/ARC از شعاع و زاویه منبع محاسبه می‌شوند؛ رأس‌های کنترل برای نمایش/هویت‌اند و پاره‌خط جای طول تحلیلی نیست. برداشت تحلیلی و جمع Block از همان دفتر اصلاحیه موجود استفاده می‌کنند؛ اصل takeoff بازنویسی نمی‌شود، بازبینی مستقل و قفل مالی باقی است.

## آزمون‌های واقعی

جامع نهایی: **7510 PASS / 0 FAIL / 0 ERROR / 5 SKIP / Exit0**، مدت 332.313 ثانیه. پنج Skip فقط نبود PowerShell؛ دو هشدار قدیمی record_property/JUnit.

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q -ra --junitxml=/tmp/p4-close/phase2_priority4_closure_accepted.xml
python -m compileall -q core app tests
python -m pip check
git diff --check
```

هر سه بررسی تکمیلی Exit0 دارند. هدفمند مرحله handoff:۱۴۴ PASS؛ هدفمند نهایی منشأ:۱۴۲ PASS و سه مورد حجیم خارج از همان انتخاب، نه SKIP. شمارها هم‌پوشان‌اند و جمع نمی‌شوند. جامع شامل تمام تست‌های جدید، PDF و هندسه/سه سقف قبلی است. هیچ آزمون قدیمی حذف، تضعیف یا Skip اجباری نشد. JUnit و همه شکست‌ها/تلاش‌های میانی با طبقه‌بندی در شواهد باقی‌اند.

## کارایی و پاسخ‌گویی اندازه‌گیری‌شده

| Entity | کل بارگذاری، ثانیه | بیشترین فاصله event loop، میلی‌ثانیه | peak RSS KiB |
|---:|---:|---:|---:|
|10000|0.746|25.32|1284700|
|50000|4.053|338.11|1449828|
|100000|10.195|476.59|1806036|

سقف آزمونی۵۰۰ms با Timer ده‌میلی‌ثانیه‌ای، شامل شروع و پایان بارگذاری، روی میزبان مشترک تعریف شد؛ SLA عمومی نیست. شمار اجزا و طول مرجع `5×N m` در هر سه اندازه برابر است. اجرای جامع قدیمی یک وقفه۵۳۹ms نشان داد؛ آستانه کم نشد و handoff مدل به بسته‌های۱۰۰۰تایی تغییر کرد. پنج چرخه باز/بسته/خطای Parsing، صفر QProcess رهاشده و SQLite/BOQ ثابت دارند؛ RSS ثبت‌شده شامل cache/allocator است و اثبات فقدان هر نشت بلندمدت نیست.

## Oracle و جریان DWG واقعی

DWG باینری مصنوعی AC1032 با ACadSharp3.8.0.0 MIT و .NET8 واقعاً نوشته/خوانده شد. شش خط۳-۴-۵ در آرایه۲×۳ →۳۰m در BOQ؛ اصلاحیه آرایه۲×۴ →۴۰m، اختلاف+۱۰m. اصل takeoffها محفوظ، بستن/بازگشایی برابر، Integrity=ok و ثبت دوم اصلاحیه/CAS کهنه رد شدند. در Qt واقعی، Handle والد،۱۲ Graphic شامل متن/خط، فرم‌های native، بازبین مستقل مصنوعی و تأیید BOQ با کلیک آزموده شدند. DPI واقعی Qt با scale1 و1.5 همان۳۰m دارد؛ Windows تأیید نشده است.

Oracleهای خط۵m، دایره شعاع۲ با محیط/سطح4π، کمان۹۰درجه با طولπ، مربع کوچک در مختصات1e12، واحدهایm/mm/cm/in/ft و Transform آرایه با فرمول مستقل کنترل شدند. خطای جمع آرایه در چهار حالت Scale/آینه/دوران حداکثر حدود7.11e-15m است؛ حد نسبی1e-12 و مختصات مطلق1e-10m ثبت شده‌اند. منابع double هستند؛ ادعای دقت نامحدود یا Decimal مطلق CAD نداریم.

## ماتریس قرارداد Entity و فرمت

| نوع | قرارداد |
|---|---|
|LINE|طول XY از نقاط واقعی؛ قابل ثبت پس از مدرک و بازبینی|
|LWPOLYLINE/POLYLINE|مسیر مستقیم طول و سطح بسته؛ سطح از planar_geometry دقیق موجود، حلقه ساده حداکثر۱۲۸ رأس|
|CIRCLE|طول محیط و سطح تحلیلی از شعاع منبع؛ double متناهی با قرارداد تطبیق نسبی1e-12، بدون تقریب پاره‌خطی مالی|
|ARC|طول تحلیلی قوس؛ کمان باز سطح قابل پرداخت ندارد|
|INSERT/MINSERT|اجزای مستقیم/تحلیلی مجاز، تبدیل واقعی ezdxf، هویت @row,column، عمق۳۲ و سقف۲۵۰هزار expanded؛ جمع غیرهم‌پوشان با مالکیت صریح|
|TEXT/MTEXT|نمایش فارسی و دوران/anchor؛ هیچ مقدار مالی مستقیم ندارد|
|DIMENSION|نمایش متن annotation خود سند؛ placeholder ممکن است باقی بماند؛ فلش/چیدمان کامل و استخراج مالی خارج از قرارداد|
|HATCH|تشخیص/هشدار و منع متره قطعی؛ سطح ظاهری جای حلقه معتبر نیست|
|SPLINE/ELLIPSE/Proxy|تشخیص و منع متره مستقیم؛ نمایش کامل/طول مالی خارج از قرارداد|
|XREF حل‌نشده|علت فارسی صریح؛ داخل بلوک هم تجمیع مالی را مسدود می‌کند|
|bulge|پیش‌نمایش تحلیلی قبلی محفوظ؛ ثبت مالی مستقیم منحنی bulge در این قرارداد مسدود است|
|Binary DXF|تشخیص امضا و رد فارسی پیش از ezdxf؛ نیاز به تبدیل معتبر به DXF متنی|

نسخه DWG آزموده فقط AC1032، DXF متنی R2018/AC1032 و decoder مشخص است. همه نسخه‌ها، Proxy اختصاصی، XREF حل‌نشده، فونت SHX ناموجود و Windows/Office طبق قرارداد مالک خارج از شرط بسته‌شدن‌اند. همه موارد خارج از مسیر مالی، علت مشخص و آزمون منفی دارند. نبود فونت اصلی با جایگزین سیستم و هشدار اعلام می‌شود؛ ابعاد متن وارد کمیت نمی‌شوند. گزارش قابلیت‌ها نخستین۲۰۰ Entity را آشکارا نشان می‌دهد؛ مدل کامل و Handle index حذف نمی‌شوند.

## Commitها و فایل‌ها

- [0f63c8e3](https://github.com/Asanda021/StructuralPro-Recovery/commit/0f63c8e3d327998b297c7178070d647b80872fb0) — Worker، مدرک واحد و قرارداد صریح آرایه
- [f2169c90](https://github.com/Asanda021/StructuralPro-Recovery/commit/f2169c904491ea6275a771b37e3922c4bc83478e) — دایره/کمان، جمع بلوک، فرم واحد و دفتر اصلاحیه موجود
- [5832d87c](https://github.com/Asanda021/StructuralPro-Recovery/commit/5832d87cf386bc7041a63a1224e8c21af826d97c) — حفاظت صحنه مرحله‌ای در برابر تغییر صفحه/نشست
- [f56ae61c](https://github.com/Asanda021/StructuralPro-Recovery/commit/f56ae61c73293d075360200e71ffb26f3c9db388) — دریافت مدل در بسته‌های ۱۰۰۰جزئی و رندر ۱۲۸جزئی
- [f0bf3eec](https://github.com/Asanda021/StructuralPro-Recovery/commit/f0bf3eec998d391ddaf62c81f827f73c9d7913dc) — تطبیق منشأ DWG/DXF با سوابق مالی تاریخی و علت XREF

- `app/graphical_takeoff.py`
- `core/drawings/cad_import_worker.py`
- `core/drawings/dwg_takeoff.py`
- `core/drawings/takeoff_bridge.py`
- `core/drawings/takeoff_session.py`
- `core/drawings/viewer_model.py`
- `core/takeoff/manual_formula_amendments.py`
- `tests/test_phase2_priority4_closure.py`

## بازیابی مستقل

{
  "primary_archive": "/StructuralPro/Backups/StructuralPro_P4_Closure_f0bf3eec_20261021.zip",
  "sha256": "98b76f200167f6077827547674933263c7cb951b82f6e0a6e19bc701a00ff169",
  "manifest_files_verified": 261,
  "git_fsck_exit": 0,
  "code_head": "f0bf3eec998d391ddaf62c81f827f73c9d7913dc",
  "tested_tree": "7912f377e3d7129f5b247f49a492161b6e91c0f5",
  "sqlite_integrity_and_foreign_keys": "PASS",
  "databases": [
    "stress/db/projects.db",
    "derived-green/db/projects.db",
    "ui-final-150/db/projects.db",
    "ui-final-100/db/projects.db",
    "real-dwg-final/db/projects.db"
  ],
  "stored_snapshot_equal": true,
  "dwg_and_exact_converted_bytes_sha_verified": true,
  "signed_stored_paths_rewritten": false,
  "tests": "PASS",
  "targeted": {
    "passed": 145,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "exit_code": 0
  },
  "restored_real_dwg": {
    "synthetic": true,
    "binary_dwg_header": "AC1032",
    "decoder": {
      "provider": "ACadSharp bridge",
      "source_sha256": "70527bc488ba0a942aaa08b4203e0911305c2c7110f95a75b70df1de80de6660",
      "output_sha256": "da389e0a308b4c2cf70637567e85461cf76a9789c03bc41bf3a48219e9758666",
      "decoder_version": "3.8.0.0",
      "exit_code": 0
    },
    "source_sha256": "70527bc488ba0a942aaa08b4203e0911305c2c7110f95a75b70df1de80de6660",
    "original_array_lines": 6,
    "original_oracle_m": 30,
    "revised_array_lines": 8,
    "revised_oracle_m": 40,
    "effective_boq_m": 40,
    "delta_m": 10,
    "original_takeoffs_unchanged": true,
    "reopen_equal": true,
    "integrity": "ok",
    "duplicate_amendment_rejected": true,
    "stale_CAS_rejected": true,
    "exit_code": 0
  },
  "dependencies": "Existing host Python packages and .NET8 runtime reused; managed converter/writer restored from Dropbox archive. No mocked decoder.",
  "evidence_sha256": {
    "restored-targeted.log": "1a6276a5787fb4a728f28247106be0f1137d82aacb8e4d79e3858bc208c62df6",
    "restored-targeted.xml": "6de1b1d3dc99f7d70a431368a86c227cba0bc31c23bfa9ba924bb2ab28c8098a",
    "restored-dwg.log": "c3991567368cb329b4fd14238580566a821848cf1aea4b5ccebe2cf06300dd72",
    "restore-verify.log": "aa563129374dd1458ef56a3fe11102e565e84a40abbcbfffe1ee2dbf016a0ad0"
  }
}

G بر اساس همین رسید واقعی تأیید شد. بکاپ اصلی کد آزموده و داده‌ها را نگه می‌دارد؛ بسته همراه، گزارش نهایی و Git bundle افزایشی Commit شواهد را نگه می‌دارد.

بدون Merge/Force Push/Actions دستی/EXE/Release؛ PR20 باید Open/Draft و PR18 بدون تغییر بماند. اولویت۵ آغاز نشده است.
