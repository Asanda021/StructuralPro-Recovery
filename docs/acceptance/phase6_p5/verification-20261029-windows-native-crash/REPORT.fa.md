# StructuralPro | فاز ۶، اولویت ۵ | پیگیری فوری کرش Native Windows

**تاریخ:** ۲۹ اکتبر ۲۰۲۶؛ **وضعیت:** آزمون تشخیصی اجرا و نتیجه واقعی بررسی شد؛ ریشه Native **NOT PROVEN**، گیت پایداری Windows **OPEN**.

## مسئله و سوابق معتبر
- PR هدف: https://github.com/Asanda021/StructuralPro-Recovery/pull/34 (Open/Draft/Unmerged).
- Baseline قبلی بدون پروفایلر: https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40764179632 روی آزمون اصلی پنج‌طبقه؛ Windows: تکرار نخست PASS (۹۰٫۰۸ ثانیه)، تکرار دوم `0xC0000005` Access Violation (۶۵٫۰۵ ثانیه)، بدون JUnit، نه timeout.
- در لاگ واقعی تکرار دوم، Faulthandler هنگام شکست در مسیر `commit() → verified() → clean() → catalog() → pathlib.read_text()` فریم Python چاپ کرده است؛ **این فریم، نام DLL خطاکننده یا ریشه سیگنال را اثبات نمی‌کند**.
- آزمون‌های پیشین Linux/GDB و آزمایش مرحله‌ای قبلی موفق بوده‌اند؛ این موفقیت‌های محدود شکست Native Windows را پاک نمی‌کنند.

## اجرای تشخیصی جدید
- Workflow: `.github/workflows/phase6-windows-native-access-violation.yml`.
- ابزار صرفاً تشخیصی: `scripts/diagnose_windows_native_crash.py`.
- [GitHub Actions #40814345575](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40814345575) روی Commit `d366e89378f2444d44857d5f9a039340ddf51ba2`: `completed/success`، Windows Server 2022 Native Qt، Python 3.12.10.
- آزمون اصلی بدون ویرایش: `tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports`.
- در هر تکرار یک subprocess جدا، fixture مصنوعی خود آزمون، JUnit واقعی، لاگ اصلی و نمونه‌های زمان/CPU/RSS با ذخیره ماندگار ثبت شد. `cProfile` یا wrapper کد محصول استفاده نشده؛ `PYTHONFAULTHANDLER=1` فقط امکان ثبت خطای native را در صورت وقوع فراهم می‌کند.
- کنترل ثابت‌بودن سه Blob در CI قبل اجرا: `manual_formula_register.py: 4e3750a0e797073d40bacb395e448da4f14b6c56`؛ `manual_formula_controls.py: 07e8ce4567eec5122253cd220a49fed6e2e27d9e`؛ `test_manual_formula_fivefloor_closure.py: f81c979051bcbaaf00015fa411314e28f370b291`.
- Artifact اصلی: `p6-windows-native-faulting-module-diagnostic`، ID `12871443914`، ZIP SHA-256 `3ef6f4b649c07d12480a074ece0ea0430bc834fe4a163a6764d362f35f912359`.
- تنها اطلاعات محدود `Application Error / Event ID 1000` در صورت شکست برای استخراج نام ماژول و Exception Code مجاز بوده است؛ هیچ memory dump یا event خام منتشر نشده.

## نتیجه چهار اجرای Windows اصلی

| تکرار | wall seconds | Exit | JUnit | بیشینه RSS نمونه‌ای (MiB) |
|---|---:|---|---|---:|
| ۱ | 115.11 | `0x00000000` | ۱ PASS، صفر FAIL/ERROR/SKIP | 163.363 |
| ۲ | 115.08 | `0x00000000` | ۱ PASS، صفر FAIL/ERROR/SKIP | 209.168 |
| ۳ | 110.06 | `0x00000000` | ۱ PASS، صفر FAIL/ERROR/SKIP | 158.184 |
| ۴ | 110.08 | `0x00000000` | ۱ PASS، صفر FAIL/ERROR/SKIP | 197.156 |

- مجموع پوشش: **چهار اجرای یک آزمون اصلی**، نه چهار سناریوی مستقل تازه.
- ثبت `overall_green=true` به معنی موفقیت **همین چهار اجرای محدود** است، نه اثبات پایداری بی‌نقص تمام محصول.
- `native_root_cause_proven=false` در Summary اصلی. همه Eventهای هر چهار اجرا `not_queried` بوده‌اند چون کرش جدیدی رخ نداد و شرط جمع‌آوری تنها در شکست فعال می‌شود.
- زمان نمونه‌برداری، اوج واقعی RSS را نشان نمی‌دهد. این اجرا با زمان‌بندی و بار Runner ممکن است نسبت به Baseline قبلی متفاوت باشد؛ نسبت عملکردی مستند برای اثبات اصلاح یا شکست نداریم.

## حکم فنی و گام بعدی ثابت
**Crash NOT REPRODUCED IN THIS RUN؛ ROOT CAUSE NOT PROVEN؛ STABILITY GATE OPEN.**

گام بعد، بررسی مقایسه‌ای Environment و تعامل Native Qt/SQLite/Pluginها بین اجرای قرمز و سبز، و در صورت لزوم آزمون کوچک‌تر با Native debugger و ثبت **فقط نام ماژول، exception، backtrace بدون حافظه** است. بهینه‌سازی `catalog()` و `verified()` با RED→GREEN و Oracle مستقل باید جداگانه دنبال شود و نباید به‌عنوان رفع کرش ادعا شود.

## حفاظت و خلاصه وضعیت پروژه و چت
هیچ فایل کد محصول، تابع محاسبات، JUnit اصلی یا قراردادهای متره تغییر نکرد. تنها اسکریپت/Workflow تشخیصی و این سند به شاخه PR #34 اضافه شدند. PR همچنان Open/Draft/Unmerged؛ بدون Merge/main/ForcePush/EXE/Release یا شروع P6-6 و فاز ۷. نقشه‌راه دقیقاً ۸ فاز و پیشرفت رسمی ثبت‌شده ۸۵٪ است. در این چت گام فوری ریشه‌یابی Windows واقعاً اجرا شد و چهار تکرار Native بدون کرش به ثبت رسیدند؛ علت کرش پیشین هنوز باز است.
