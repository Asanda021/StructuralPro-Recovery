# گیت امنیتی E4: رد مسیر نمادین IFC | ۲۸ اکتبر ۲۰۲۶

## منبع و حکم
- مخزن: `Asanda021/StructuralPro-Recovery`، PR #34، شاخه `feature/phase6-p5-workspace-e3-e6-20261027`.
- **SHA واقعی کد و آزمون**: `76969a29d29588b4b0a1b1cbf43a81a319958fdf`، tree `badd492ffc6fdb690a7a70201b30016872deb29f`.
- [GitHub Actions #40654824158](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40654824158)، نتیجه **completed/success** هر دو Job `windows-2022` و `ubuntu-24.04` روی همان SHA.
- حکم محدود: **PASS برای گارد جدید مسیر لینک‌شده عضو IFC**، نه COMPLETE برای E4/P6-5.

## تغییر اجرایی و آزمون
- `app/verified_search_navigation.py::reviewed_member_source`: پیش از خواندن فایل IFC تأییدشده، `is_symlink` خود فایل و تمام اجزای مسیر والد را بررسی و در صورت وجود با خطای فارسی رد می‌کند. کنترل SHA/Revision و بازبینی مستقل چهارطرفه قبلی حفظ شدند.
- `tests/test_phase6_p5_e4_ui.py`: دو سناریوی منفی `file` و `parent` با monkeypatch `Path.is_symlink`، حفظ digest و BOQ و بستن DB. این‌ها **شبیه‌سازی وضعیت symlink** در Qt/CI هستند، نه آزمون ساخت symlink واقعی روی NTFS.
- هیچ داده هندسی، مقدار، نرخ، BOQ، مجوز و مسیر هدایت جدیدی تولید نشد.

## JUnit اندازه‌گیری‌شده از لاگ‌های واقعی CI

| بسته | Linux | Windows |
|---|---:|---:|
| اصلی `p6-p5-*.xml` | 468 PASS | 468 PASS |
| تاریخی `p6-historical-*.xml` | 130 PASS | 130 PASS |
| امنیت `p6-qa-security-*.xml` | 26 PASS | 26 PASS |
| DPI150 | 8 PASS | 8 PASS |
| DPI200 | 8 PASS | 8 PASS |
| FAIL/ERROR/SKIP در همه بسته‌ها | 0 | 0 |
| FutureWarning بسته اصلی `fitz` | 1 | 1 |

- SHA256 JUnit اصلی Linux: `7d1bde79eb4bdd64a26d85c093f43bbb4505339248e6d74463cac4a85381d92d`.
- SHA256 JUnit اصلی Windows: `491bfbc3cc0dbc43856d8bbb8928181efdc1974ac1dd0a2cb96e7a68caa08bb4`.
- Linux JUnit سایر بسته‌ها: historical `7c898352cfd4c0b3056b3872790968edded4b36bc51efb9bc582833906a46904`؛ security `65128d52e6cae29f65feae0f36e38b7d8a09d73770f9a12aff7b7ac47ed929a5`؛ DPI150 `a09274706d05b5488b7ba6c0cbe5e9a5e8dc9f95188cb22a6295b79937ad161b`؛ DPI200 `a1ef685f04b897650d8168097b9a63688a197d08d58e5a680d94844dc00b61cf`.
- Windows JUnit سایر بسته‌ها: historical `90b237e5848192befb9d520afae8eb5e8cacbf21ab3a658186df8fd9244a9802`؛ security `f33036f87bd082b576115b81276e45bfa46cdf08edbb9abeddbcd93a32fd4635`؛ DPI150 `75c36739a285c74153df8590bcd3d13ab8051ecfb7a9593c9754121e43fc53f7`؛ DPI200 `e47c50ee0c6f5936b1e34dbfb3eeb5e869b43c3a23b4e3311536a48644ff2533`.
- Artifacts همین اجرا: `p6-p5-qt-windows` (12802120871) و `p6-p5-qt-offscreen` (12801725648)، در زمان بررسی منقضی نشده بودند.
- DPI تکرار سناریوهای Dock است؛ شمارش نباید به‌عنوان تست یکتای مجزا جمع زده شود.

## مرز و ادامه
- این CI به‌تنهایی اجرای رگرسیون گسترده ۸۳۷۵تایی روی SHA جدید نیست؛ آخرین broad موفق Linux و پنج Windows-only مربوط به SHA قبلی `7cbeac9b...` هستند.
- ناوبری DWG بدون منشأ تبدیل معتبر، handoff تخصصی IFC فاقد قرارداد مستقل، IFC MEP، مالکیت هندسی مشترک E6 و مدل تجاری A2 همچنان `BLOCKED/NOT VERIFIED`.
- QA فیزیکی Windows: مانیتورهای واقعی، GPU/driver، Sleep/Resume و تأیید مهندس مالک همچنان `NOT VERIFIED`.
- PR #33 و #34 `Open/Draft/Unmerged`؛ `main` برابر `9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` در کنترل این نوبت؛ هیچ Merge، ForcePush، Release/EXE یا فاز تازه‌ای انجام نشده است.
- برنامه ثابت: **۸ فاز، پیشرفت ثبت‌شده ۸۵٪**.
