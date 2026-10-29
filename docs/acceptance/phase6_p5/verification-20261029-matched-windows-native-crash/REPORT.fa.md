# StructuralPro | فاز ۶، اولویت ۵ | مقایسه هم‌محیط ویندوز و بازتولید Access Violation

**تاریخ:** ۲۹ اکتبر ۲۰۲۶  
**حکم:** **Windows RED / ACCESS VIOLATION REPRODUCED**. منشأ Native **NOT PROVEN**؛ P6-5 همچنان **PARTIAL**.

## مأموریت و مبنا
در Run قبلی [#40764179632](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632)، آزمون اصلی پنج‌طبقه بدون پروفایلر روی Windows پس از یک PASS، با `0xC0000005` و بدون JUnit متوقف شد. در [#40814345575](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40814345575) چهار تکرار همان آزمون PASS شدند، ولی پایداری را اثبات نکردند.

برای حذف تفاوت احتمالی میان دو کد/محیط، Workflow تازه `.github/workflows/phase6-windows-matched-native-comparison.yml` در **یک Windows Server 2022 Runner** دو checkout با Commit تاریخی `5fb5c69cec5751bbbecf7018c843c5e921128bb2` و HEAD جاری (در این اجرا `96dac550630855967114c492943f0e7b4c246149`) را بررسی کرد. بسته‌ها تنها **یک بار** نصب شدند، سپس دو اجرای مستقل در هر پوشه انجام شد؛ هر اجرا subprocess تازه داشت. نه کد محصول و نه آزمون اصلاح نشده، `cProfile` استفاده نشد.

## کنترل واقعی یکسان‌بودن سورس
مرحله Git blob equality در خود Windows **PASS** بود و این شش فایل در هر دو checkout یکسان بودند:
- `core/takeoff/manual_formula_register.py`، SHA `4e3750a0e797073d40bacb395e448da4f14b6c56`
- `app/manual_formula_controls.py`، SHA `07e8ce4567eec5122253cd220a49fed6e2e27d9e`
- `core/projects/store.py`، SHA `0aa448bcc0f67bab12c37592f7abf01fd0e1765d`
- `core/platform/revisions.py`، SHA `d878bde85f741b667fd482e9f953bcdd817397e3`
- `tests/test_manual_formula_fivefloor_closure.py`، SHA `f81c979051bcbaaf00015fa411314e28f370b291`
- `requirements.txt`، SHA `96d46b676dddfce7dcd8dccb79150710e4218c8a`

همچنین مقایسه GitHub `5fb5c69...2256ec396...` تأیید می‌کند تفاوت سورس طی بررسی قبلی فقط در Workflow، اسکریپت‌های تشخیصی و اسناد بوده است، نه موتور محصول.

## مشخصات واقعی محیط مشترک
از Artifact `environment.json` ثبت‌شده با `scripts/inspect_windows_native_environment.py` (فرآیند probe مستقل، نه خود فرآیند آزمون):
- Windows Server 2022، build `10.0.20348`؛ Python `3.12.10`، CPython 64-bit
- `PySide6`، `PySide6-Addons`، `PySide6-Essentials` و `shiboken6`: همگی **6.12.0**
- Qt Runtime: **6.12.0**؛ SQLite: **3.49.1**؛ pytest: **9.2.0**
- ifcopenshell `0.9.0.post1`، psutil `7.2.2`؛ وابستگی‌ها یک‌بار برای دو گروه نصب شدند.
- اثرانگشت کتابخانه‌ها بدون افشای مسیر یا محتویات حافظه ثبت شد:
  - `qwindows.dll`: SHA256 `ddd5cf6a96f058cfafcbc901ddeb5df010d755f0716beacfb557f8b27b733afe`
  - `Qt6Core.dll`: SHA256 `f57ed38afd95d0306cca9d88d997f639f70c7628a4f1f064eae291d579487121`
  - `Qt6Widgets.dll`: SHA256 `2f62cbe2869fff4e20df7369c2786e1ec7ec290d5a63d1371b7f70cf06909c3f`
  - `sqlite3.dll`: SHA256 `8daa45684bf6688fca28d956b2e8942f2fa98f656675ce68e6d61dd869848a7a`
- این fingerprint به **همین Run جدید** تعلق دارد؛ از نسخه دقیق wheel/DLL در Run شکست تاریخی ۴۰۷۶۴۱۷۹۶۳۲ شواهد مستقلی نداریم و همسانی تاریخی آن را ادعا نمی‌کنیم. fingerprint فرآیند probe نیز نام DLL خطاکننده را مشخص نمی‌کند.

## نتیجه واقعی چهار تکرار

| Checkout | اجرا | زمان wall | خروجی | JUnit | RSS نمونه‌برداری‌شده MiB |
| --- | ---: | ---: | --- | --- | ---: |
| Historic | ۱ | 150.12s | `0x00000000` | ۱ PASS | 201.695 |
| Historic | ۲ | 135.11s | `0x00000000` | ۱ PASS | 196.957 |
| Current | ۱ | **50.05s** | **`0xC0000005`** | **ندارد** | 106.746 |
| Current | ۲ | 145.14s | `0x00000000` | ۱ PASS | 199.625 |

- `timed_out=false` برای هر چهار اجرا؛ در Run فعلی **سه PASS و یک Access Violation واقعی**.
- شکست جاری در لاگ `current/run-1.log`: `Windows fatal exception: access violation`؛ Frameهای Python هنگام کرش در مسیر `review → selected → rows → load → verified → clean → catalog → deepcopy` قرار داشتند. هم‌زمان در شروع log یک snapshot مربوط به `json.decoder.raw_decode` ثبت شده است. **هیچ‌یک به‌تنهایی عامل Native را ثابت نمی‌کنند**.
- تلاش فقط‌خواندنی ثبت رویداد `Application Error / Event ID 1000` در همین محدوده زمانی به `status=no_matching_event` ختم شد. DLL خطاکننده **NOT IDENTIFIED** است. هیچ Dump، مسیر فایل شخصی، داده خام Event یا محتویات حافظه در Artifact نیست.
- اختلاف runtime بین دو گروه در **این Run** حذف شده، اما متناوب‌بودن کرش به معنی تفاوت ماهوی نسخه فعلی و تاریخی نیست؛ دو PASS تاریخی و یک CRASH جاری ممکن است به خاطر تصادفی‌بودن رخداد باشند و اثبات رگرسیون منتسب به Commit نیست.

## CI و فایل‌های شواهد
- [Run #40821287426](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40821287426): `completed/failure` **به‌درستی**؛ گیت نهایی به خاطر وجود کرش اجازه سبز شدن نداد.
- Artifact: `p6-matched-windows-old-current-native-diagnostic`، ID `12874368747`، ZIP SHA256 `9d83ffbf0e722ca715e9be215fdfc806446fcf7c11a2d6d408531218db945be0`.
- Artifact شامل `environment.json`، دو `summary.json`، JUnitهای معتبر برای سه PASS، خروجی stdout و RSS/CPU نمونه‌ای هر تکرار است.
- هیچ پروفایلر، بهینه‌سازی موتور، تست جایگزین یا اصلاح محصول انجام نشد. موفقیت محدود چهارگانه قبلی همچنان معتبر اما برای تأیید پایداری ناکافی است.

## گام بعدی بدون ایجاد فاز جدید
در **همین P6-5**: بازتولید Native را با دامنه کوچک‌تر و Oracle مستقل بین Qt event-loop/دکمه‌های UI و مسیر Python/SQLite تفکیک کنید. اگر از Debugger استفاده شد، فقط نام ماژول، exception code و backtrace بدون Dump حافظه ذخیره شود؛ هر تغییری در محصول فقط پس از RED→GREEN مستقل، حفظ fail-closed و صحت مقادیر ۷۰ ردیف/۵ طبقه، و regression واقعی در Linux/Windows مجاز است. کاهش هزینه `catalog()`/`verified()` پروژه جداگانه performance داخل P6-5 است و نباید خودکار رفع `0xC0000005` خوانده شود.

## وضعیت پروژه و همین گفت‌وگو
Roadmap **دقیقاً ۸ فاز**، پیشرفت ثبت‌شده **۸۵٪**، P6-5 **PARTIAL**، گیت پایداری ویندوز **RED**. PR #34 باز/Draft/بدون Merge؛ بدون تغییر main، انتشار EXE، Force Push، شروع P6-6 یا فاز ۷. این چت قدم مقایسه Native Windows را اجرا و با کرش واقعی تأیید کرد؛ علت DLL Native همچنان باز است.
