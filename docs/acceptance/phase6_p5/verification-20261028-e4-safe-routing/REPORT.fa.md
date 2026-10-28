# پذیرش اصلاح E4: ناوبری امن سند عمومی، ۲۸ اکتبر ۲۰۲۶

## دامنه و نتیجه

**PASS محدود در Linux و Windows native CI** برای جلوگیری از دورزدن قرارداد تخصصی DWG/IFC در مسیر عمومی جست‌وجو، با حفظ مسیر معتبر PDF/DXF.

- مخزن `Asanda021/StructuralPro-Recovery`، PR #34، شاخه `feature/phase6-p5-workspace-e3-e6-20261027`.
- کد و سه آزمون جدید: `caadb784dd199bdeceb6d3b2ab5b180bb2a8bba1`، Tree `55ea24c3656bee8efb1096cee064b470c233a4d6`.
- اصلاح بودجه زمانی CI بدون حذف یا Skip تست: `2eb95e88f034558674591b26b7c35ccd4647ce03`، Runner اصلی pytest از ۴۸۰ به ۷۲۰ ثانیه با سقف Job ۲۰ دقیقه.
- [CI نهایی #40652984455](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40652984455) روی Commit `2eb95e88...`، هر دو Job **completed / success** و Artifactهای `p6-p5-qt-windows` و `p6-p5-qt-offscreen` موجود.
- [CI اولیه #40651721016](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40651721016): Linux موفق، Windows **FAILURE به دلیل timeout ۴۸۰ثانیه‌ای** در حدود ۹۲٪ بسته اصلی؛ JUnit اصلی تولید نشد، پس آن Run را PASS نمی‌نامیم. Historical ۱۳۰، security ۲۶ و DPI ۸+۸ Windows در همان Run جداگانه موفق بودند.

## آزمون‌های CI نهایی

| بسته | Linux offscreen | Windows native |
|---|---:|---:|
| اصلی E3/E4/E5/E6 + W1 + سه سناریوی جدید E4 | ۴۶۶ PASS | ۴۶۶ PASS |
| قراردادهای تاریخی قرنطینه‌شده | ۱۳۰ PASS | ۱۳۰ PASS |
| امنیت تفکیک QA | ۲۶ PASS | ۲۶ PASS |
| Dock در DPI ۱۵۰٪ | ۸ PASS | ۸ PASS |
| Dock در DPI ۲۰۰٪ | ۸ PASS | ۸ PASS |
| FAIL / ERROR / SKIP در هر بسته | ۰ | ۰ |
| هشدار pytest بسته اصلی | ۱ fitz | ۱ fitz |

اعداد بسته‌ها سناریوهای مستقل قابل جمع نیستند، و تکرار DPI نسبت به بسته اصلی همان ۸ سناریوی Dock است.

## تغییر اجرایی

`app/verified_search_navigation.py::prepare_verified_drawing_view` پیش از ساخت پنجره، نوع منبع را کنترل می‌کند: فقط `.pdf` و `.dxf` در مسیر سند عمومی مجازند. `.dwg` بدون قرارداد منشأ تبدیل و `.ifc` بدون بازبینی هندسی مستقل، با خطای صریح fail-closed رد می‌شوند؛ منبع فاقد وجود، مسیر symlink، عدم تطابق SHA و Revision ناقص نیز رد می‌شوند. پس از بازشدن، `viewer.kind` و مسیر واقعی Viewer، SHA دوباره و digest پروژه کنترل می‌شود.

در `tests/test_phase6_p5_e4_ui.py` سه حالت جدید افزوده شد: دو آزمون منفی DWG/IFC با منبع و هش صریح، و یک آزمون مثبت DXF مصنوعی دارای `$INSUNITS=6` که Viewer اصلی CAD را باز می‌کند. هر سه، عدم تغییر BOQ و digest پروژه را کنترل می‌کنند. پوشش قبلی PDF و نشست ذخیره‌شده محفوظ است.

## مرزهای پذیرش

- این گیت تنها **عدم دورزدن مسیر تخصصی در جست‌وجوی سند عمومی** را می‌بندد؛ کل E4 همچنان `PARTIAL` است.
- IFC عضو فقط از `prepare_verified_member_view` و bridge چهارطرفه بازبینی‌شده مجاز است؛ handoff مستقیم نتایج عمومی Beam/Column/MEP/سقف/معماری همچنان بدون قرارداد هویت `BLOCKED` است.
- DWG تا قرارداد تبدیل/منشأ و مدارک معتبر `BLOCKED` است. ساختگی‌کردن تبدیل یا استنتاج هندسی ممنوع.
- E6 مالکیت مشترک/Crosswalk inverse، IFC MEP، A2 تجاری و UAT انسانی Windows همچنان `BLOCKED/NOT VERIFIED` باقی می‌مانند.
- رگرسیون گسترده Linux قبلاً بر کد `7cbeac9b...`، تعداد ۸۳۷۰ PASS + پنج SKIP را ثبت کرد و آن پنج در Windows هدفمند پنج PASS شدند. **اجرای مجدد کل رگرسیون ۸۳۷۵تایی روی Commit جدید `caadb784...` انجام نشده است**؛ موفقیت ۴۶۶تایی، ادعای آن اجرا نیست.
- هیچ Merge، ForcePush، تغییر `main`، Release، EXE، P6-6 یا فاز۷ انجام نشده؛ پروژه دقیقاً هشت فاز و پیشرفت ثبت‌شده ۸۵٪ دارد.

**گام بعدی:** بررسی قرارداد واقعی هویت تخصصی E4 فقط در صورت داشتن مدارک موجود؛ در غیر این صورت گیت‌های فاقد قرارداد باید مسدود بمانند و پذیرش فیزیکی Windows جداگانه ثبت شود.
