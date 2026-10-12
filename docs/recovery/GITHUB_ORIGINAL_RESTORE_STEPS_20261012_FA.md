# StructuralPro — گام بعدی بازیابی مخزن اصلی

**تاریخ:** ۲۰ مهر ۱۴۰۵ / ۱۲ اکتبر ۲۰۲۶  
**حساب مورد بررسی:** `Asanda021`  
**مخزن قدیمی:** `Asanda021/StructuralPro`  
**مخزن جایگزین محفوظ:** `Asanda021/StructuralPro-Recovery`

## ۱. نتیجه جست‌وجوی فعلی

- ابزار رسمی اتصال GitHub برای مخزن قدیمی `404 Not Found` داده است؛ **این به معنی اثبات حذف نیست**.
- جست‌وجوی مخازن مالک `Asanda021` نسخه اصلی را نیافت.
- جست‌وجوی Dropbox متصل برای `StructuralPro`، `bundle` و `481` هیچ نسخه‌ای نشان نداد و پوشه ریشه آن خالی بود.
- آرشیو ۱۰ اکتبر `a07cf...` در Library باقی است اما نسخه کامل تاریخی `main` و `PR #481` نیست.
- در اتصال فعلی ابزار بررسی Deleted repositories و Restore وجود ندارد؛ این کنترل در رابط وب حساب مالک انجام می‌شود.

## ۲. مسیر بازیابی رسمی GitHub — اولویت اول

1. با حساب `Asanda021` وارد `https://github.com/settings/repositories` شوید.
2. بخش **Deleted repositories** را باز کنید.
3. اگر `StructuralPro` را دیدید، Restore را انتخاب و تأیید کنید.
4. GitHub برای برخی مخازن حذف‌شده حداکثر ۹۰ روز امکان Restore می‌دهد؛ مخزن‌های فورک‌شده ممکن است محدودیت داشته باشند.
5. مخزن موجود `StructuralPro-Recovery` را حذف، تغییرنام یا بازنویسی نکنید.

مرجع رسمی: `https://docs.github.com/en/repositories/creating-and-managing-repositories/restoring-a-deleted-repository`

## ۳. پیشگیری از Build/Release ناخواسته پس از بازیابی

بلافاصله پس از Restore، **قبل از هر Push یا Merge** در مخزن قدیمی به `Settings → Actions → General` بروید و مجوز اجرای Workflowهای آن را غیرفعال کنید. ممکن است مخزن قدیمی ۱۹۳ Workflow دارای مسیرهای Build/Release باشد؛ تا قبل از ارزیابی امنیتی آن‌ها را فعال نکنید. وضعیت محافظت شاخه‌ها را بررسی کنید.

## ۴. دستور مقایسه بدون تغییر در دو مخزن — Windows PowerShell

Git و Python 3 را روی سیستم نصب کنید. در یک پوشه امن، از GitHub فقط نسخه mirror بخوانید؛ هیچ Push، Merge، Build یا Release انجام نمی‌شود:

```powershell
git clone --mirror https://github.com/Asanda021/StructuralPro.git StructuralPro-original.git
git clone --mirror https://github.com/Asanda021/StructuralPro-Recovery.git StructuralPro-recovery.git
py -3 .\scripts\compare_git_recovery.py --original .\StructuralPro-original.git --recovery .\StructuralPro-recovery.git --output .\StructuralPro-tree-comparison.json
```

برای خط سوم، اسکریپت همراه این بسته را در پوشه جاری داخل `scripts` قرار دهید. اسکریپت فقط محتوای Git محلی را می‌خواند و گزارش JSON را **بیرون از دو پوشه Git** می‌نویسد.

خروجی: تعداد فایل‌های برابر، متفاوت، فقط در مخزن اصلی، فقط در مخزن بازیابی، تعداد Commitهای قابل دسترس از همه Refها، شاخه‌ها، Tagها و Refهای PR مربوط به #462/#464/#467/#468/#481 در صورت وجود. مقایسه به معنی ادغام خودکار نیست.

## ۵. اگر نام StructuralPro در Deleted repositories نبود

- در حساب‌های GitHub احتمالی دیگر، از جمله حسابی که قبلاً وصل شده بود، بررسی کنید که Repository منتقل یا Rename نشده باشد.
- ایمیل‌های اعلان GitHub برای `Transfer`, `Delete`, `Rename` را بررسی کنید.
- اگر حذف شده و قابل Restore نیست، با GitHub Support ارتباط بگیرید؛ شرایط پشتیبانی وابسته به حساب و وضعیت Repository است.
- در نبود منبع اصلی، فقط Patchها و اسناد موجود را با کنترل دقیق روی شاخه‌های جدا بازسازی کنید، نه با ادعای برگرداندن اصل تاریخچه.

## ۶. مرزهای قطعی

- **main** مخزن بازیابی تغییر داده نشود.
- `PR #1` تا آزمون Windows و تأیید مالک در Draft بماند.
- GitHub Actions قدیمی فعال نشود.
- هیچ فایل اجرایی یا نسخه انتشار تولید نشود.
- برای انتشار عمومی دوباره داده‌ها، Secretها/توکن‌ها/اطلاعات حساس بررسی شوند.