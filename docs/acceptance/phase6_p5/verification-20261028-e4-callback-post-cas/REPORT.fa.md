# P6-5 E4 | قرارداد callback و CAS پس از اجرای مقصد
**تاریخ:** ۲۸ اکتبر ۲۰۲۶ | **PR:** #34 | **حکم:** اصلاح اختصاصی تأییدشده؛ تکمیل دامنه E4 و فاز۶ همچنان PARTIAL

## نقص واقعی و مرز قرارداد
در `app/project_search_panel.py`، پس از صحت‌سنجی رکورد جست‌وجوی SQLite، `on_navigate` و `on_open_model` می‌توانستند **مقدار `False` صریح** بدهند، ولی کد قدیمی همچنان وضعیت موفقیت نمایش می‌داد. همچنین Callback هنگام اجرای پنجره modal/سیگنال Qt ممکن است باعث تغییر `current_digest` پروژه شود؛ بررسی پیش از callback کافی نیست. در خطای مدل IFC، انتخاب قدیمی نیز باقی می‌ماند.

مصرف‌کننده‌های واقعی در `app/main.py` پس از موفقیت بعضی مقصدها `None` می‌دهند؛ تفسیر `None` به شکست قرارداد را می‌شکند، بنابراین فقط `result is False` به معنی رد صریح است. `Exception` مستقل و Digest پس از callback بررسی می‌شوند. هیچ فرض هندسی/BOQ/قیمت/تأیید جدید اضافه نشده.

## آزمون مستقل RED
- Commit تست بدون اصلاح کد: `76610c66067332977762b3326a94da3baec80349` در `tests/test_e4_callback_contract.py`: هشت ترکیب واقعی Qt شامل دو مسیر (رکورد عمومی و IFC) × چهار نتیجه (None موفق، False رد، Exception، تغییر Digest حین callback). گیت‌ها بررسی می‌کنند انتخاب نامعتبر حذف شده، پیام موفقیت کاذب تولید نشده، داده BOQ تغییر نکند.
- [RED CI #40718061692](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40718061692) با checkout همین source روی Windows Server 2022: **۵ FAIL / ۳ PASS / ۰ SKIP** با JUnit اصلی [artifact #12828429125](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40718061692/artifacts/12828429125). پنج شکست واقعی: False رکورد/IFC، Exception IFC و تغییر Digest بعد از callback رکورد/IFC.
- Linux همان RED با متن `..FF.FFF` و **Segmentation fault در cleanup عمومی Qt (`tests/conftest.py:77`)** پایان یافت، `exit=245` و **JUnit تولید نشد**. این اجرا شکست محیطی/Teardown را نیز ثبت می‌کند و **RED کامل مستقل Linux محسوب نمی‌شود**. از آن عدد رسمی نهایی pytest ساخته نشده است.

## اصلاح هدفمند و GREEN
- Commit اجرای اصلاح: [`426c485f16c4938299a9c0415e96dd5ff15d1c1b`](https://github.com/Asanda021/StructuralPro-Recovery/commit/426c485f16c4938299a9c0415e96dd5ff15d1c1b): فقط `app/project_search_panel.py`. `on_navigate` و `on_open_model` اکنون فقط `False is literal` را رد می‌کنند؛ `None` مثل قرارداد قبلی موفق است؛ Digest بعد از callback دوباره کنترل و نتیجه stale/Exception با `invalidate` مسدود می‌شود.
- [GREEN CI #40718625140](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40718625140)، source checkout روی همین SHA قفل شده، **Ubuntu Linux Qt offscreen: ۴۸ PASS / صفر FAIL, ERROR, SKIP** در ۷٫۷۶ ثانیه؛ [JUnit #12828268741](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40718625140/artifacts/12828268741).
- در همان CI، **Windows Server 2022 Qt native: ۴۸ PASS / صفر FAIL, ERROR, SKIP** در ۲۲٫۵۶ ثانیه؛ [JUnit #12829692043](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40718625140/artifacts/12829692043).
- ۴۸ تست *در هر سیستم* شامل هشت تست جدید + ۴۰ تست مسیرهای موجود E4 است؛ شمارش ۹۶ سناریوی مستقل اشتباه است.
- [CI قبلی E4 #40718250946](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40718250946) نیز روی همان کد، Windows/Linux موفق؛ اما بسته ۴۸تایی دلیل پذیرش تغییر جدید است.
- [CI جامع E3–E6 #40718251010](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40718251010) روی source جدید هم اجرا شده و در زمان شروع این گزارش Linux success و Windows in_progress؛ نتیجه نهایی جدا بررسی شود.
- [CI رگرسیون گسترده source جدید #40719136460](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40719136460) با workflow commit `00ccefa944e626a6a2a5bd137fc2dddf79692e27` و pinned checkout کد `426c485...` راه افتاده، **در لحظه گزارش queued**؛ Linux کامل + سه Windows shard + گیت Union با JUnit حقیقی. نتیجه اجرای [#40707200358](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40707200358) روی source قبلی `c10b929...` (۸۴۰۳ testcase/union success) نباید به source جدید تعمیم یابد.

## وضعیت دامنه و محافظت‌ها
- مسیرهای Beam/Column/MEP/Roof/Report بدون قرارداد هویت مقصد تخصصی، DWG فاقد منشأ تبدیل، تخصیص مالکیت مشترک E6 و Crosswalk معکوس فاقد قرارداد، W1/IFC MEP و مدل واقعی GGUF تجاری همچنان BLOCKED/PARTIAL؛ داده یا نسبت ساخته نمی‌شود.
- PR #33 در `c859cebccf83a43e456e73377bb2dea764e00823` Draft/Open/Unmerged و PR #34 Open/Draft/Unmerged؛ API پیش از این عملیات `mergeable=false` روی PR34 نشان داد که بدون مجوز عمداً حل/ادغام نشد. `main` در `9d92fd6236bb2fcaf9a1850a8a26d8a4e03ffe95` ثابت، هیچ Release/EXE/Merge/ForcePush.
- تعداد فازها دقیقا **۸** و پیشرفت ثبت‌شده پروژه **۸۵٪**، بدون افزایش ادعایی.

**خلاصه پروژه و این چت:** نتیجه ۸۴۰۳تایی CI مرجع تأیید شد؛ نقص ۵گانه callback در Windows با JUnit واقعی RED و اصلاح حداقلی GREEN با ۴۸ PASS واقعی Windows و Linux ثبت شد. پذیرش گسترده SHA تازه و گیت‌های تخصصی باقی‌مانده هنوز بازند.
