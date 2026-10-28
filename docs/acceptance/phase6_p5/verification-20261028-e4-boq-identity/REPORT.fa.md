## نتیجه قطعی RED/GREEN دو‌سیستمی | ۲۸ اکتبر ۲۰۲۶

- [RED #40758706644](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758706644) با checkout pinned `26201e31d8c7c2b5bc48642f6f4e8a152ef68d21`: Linux **۵۳ PASS، ۲ FAIL**، Windows **۵۳ PASS، ۲ FAIL**؛ خطاهای مشابه: انتخاب «سقف» به‌جای «کف» و عدم یافتن ردیف دوم. شکست‌ها حفظ شده‌اند، نه حذف یا XFAIL. [JUnit RED Linux #12846683069](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758706644/artifacts/12846683069) و [JUnit RED Windows #12846912834](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758706644/artifacts/12846912834).
- [GREEN #40758937945](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758937945) با checkout دقیق `64d637bfe8522349d78b30431a44527401ff7ce4` و workflow `ae4ee47e20bd16ae7a7c12fcd42e0d2475923ad3`: Linux **۵۵ PASS** (۶٫۳۳ ثانیه) و Windows **۵۵ PASS** (۳۱٫۹۲ ثانیه)، در هر دو محیط **صفر FAIL/ERROR/SKIP**. JUnit اصلی حفظ شد: [Linux #12847492008](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758937945/artifacts/12847492008) و [Windows #12847965802](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758937945/artifacts/12847965802).
- هر ۵۵ testcase در دو OS تکرار شده‌اند؛ ادعای ۱۱۰ سناریوی مستقل نمی‌کنیم. ۲ سناریوی جدید قبلاً واقعاً RED بودند. هیچ فایل آزمون حذف، assertion ضعیف، timeout افزایش، موتور مالی یا هویت ساختگی افزوده نشده است.
- تغییر محصول **فقط** `app/project_search_panel.py`: تطبیق اولویت `id` و `row_id` انتخاب جدول با موتور `search_project`. ردیف جست‌وجوشده همان ردیف نمایشی است؛ مقدار/قیمت/BOQ نوشته نمی‌شود.
- این شواهد، **پذیرش نقص محدود BOQ E4** است؛ پذیرش سراسری E4، E6 و همه ۸۴۲۳ testcase source جدید را به‌تنهایی اثبات نمی‌کند. بسته جامع جدید P6-5 در گیت جدا در GitHub اجرا می‌شود و باید مستقل خوانده شود.
- `main` هنگام این راستی‌آزمایی `9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` و PR #33 `c859cebccf83a43e456e73377bb2dea764e00823` باقی مانده‌اند؛ PR #34 Draft/Open/Unmerged و Merge/Release/EXE انجام نشده است.

# P6-5 E4 | تطبیق هویت ردیف جست‌وجو و جدول BOQ

**تاریخ:** ۲۸ اکتبر ۲۰۲۶. **PR:** #34 Draft/Open/Unmerged. **دامنه:** انتخاب فقط‌خواندنی ردیف BOQ با شناسه ذخیره‌شده، بدون محاسبه و ثبت مالی.

## نقص اثبات‌شده
- `core/search/global_search.py` در `rec()` اول `id` و سپس `row_id` را برای هویت نتیجه BOQ می‌خواند. `app/project_search_panel.py` در `display_verified_boq_row()` ترتیب معکوس داشت (`row_id` قبل از `id`). نتیجه در ردیف‌های دارای هر دو شناسه با مقادیر متفاوت می‌توانست به ردیف **اشتباه** منتهی شود، نه صرفاً خطای نمایش.
- آزمون‌های Qt واقعی در [Commit RED `26201e31d8c7c2b5bc48642f6f4e8a152ef68d21`](https://github.com/Asanda021/StructuralPro-Recovery/commit/26201e31d8c7c2b5bc48642f6f4e8a152ef68d21) دو ردیف کاملاً مصنوعی با `id` و `row_id` متقاطع می‌سازند. نتیجه جست‌وجوی داخلی `ENTRY-01` باید همان «کف طبقه» را انتخاب کند، نه «سقف طبقه».
- [RED CI #40758706644](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758706644): هر دو محیط Linux/Windows **failure**. Linux واقعی: ۲ FAIL، ۵۳ PASS؛ شکست اول `assert 1 == 0` یعنی انتخاب ردیف اشتباه؛ دوم `ValueError` یعنی حتی ردیف دوم به‌علت شناسه ناسازگار پیدا نمی‌شد. JUnit به‌عنوان شکست واقعی محفوظ است: [Linux #12846683069](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758706644/artifacts/12846683069)، [Windows #12846912834](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758706644/artifacts/12846912834).
- تغییر محصول در [Commit `64d637bfe8522349d78b30431a44527401ff7ce4`](https://github.com/Asanda021/StructuralPro-Recovery/commit/64d637bfe8522349d78b30431a44527401ff7ce4) فقط ترتیب سه کلید انتخاب را به `id,row_id,item_id` تبدیل کرد. تطبیق با اولویت `id,row_id` در جست‌وجوی اصلی؛ no new identity inference. هنگام وجود شناسه معتبر داخلی، شناسه چاپی `row_id` فقط alias است؛ مقادیر و قیمت‌ها تغییر نمی‌کنند.
- [GREEN CI #40758937945](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40758937945) با checkout pinned `64d637bfe8522349d78b30431a44527401ff7ce4` در Ubuntu 24.04 و Windows 2022 آغاز شده است. **در زمان این checkpoint در حال اجرا؛ قبولی هنوز ادعا نمی‌شود.**

## حد پذیرش
- آزمون‌ها شامل دو مورد تازه و سایر سناریوهای قبلی E4 (جست‌وجو، Qt، session و callback/CAS) هستند.
- تنها وقتی هر دو Job completed/success و JUnit صفر FAIL/ERROR/SKIP داشته باشند، این **نقص محدود** قابل پذیرش است. CI بزرگ‌تر P6-5 و رگرسیون کل source پس از آن گیت‌های جدا هستند.
- E4 کامل نیست: مقصدهای تخصصی Beam/Column/MEP/Roof و DWG بدون قرارداد حقیقی همچنان BLOCKED. E6 owner sharing و inverse crosswalk، W1، A2 و UAT فیزیکی بازند. هیچ Merge، ForcePush، تغییر main یا Release انجام نشد.

## خلاصه پروژه و چت
گیت GDB bounded با وضعیت `NOT REPRODUCED/ROOT CAUSE UNDETERMINED` و سه JUnit موفق مستند شده است. E4 نقص مغایرت شناسه با RED واقعی دو‌سیستمی اثبات و اصلاح حداقلی ثبت شد؛ پذیرش نهایی منوط به GREEN و CI آینده است. نقشه راه ۸ فاز و ۸۵٪ ثبت‌شده بدون تغییر.
