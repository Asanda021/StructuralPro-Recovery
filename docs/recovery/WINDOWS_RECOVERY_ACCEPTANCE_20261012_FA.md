# بسته پذیرش سورس روی Windows

این بسته Python/PowerShell است؛ EXE، Installer و Release نیست. آزمون Linux پذیرش Windows محسوب نمی‌شود.

روی Windows واقعی، از پوشه سورس استخراج‌شده، وابستگی‌های Python را در venv نصب کنید. برای حفظ اجرای آفلاین، wheelهای معتبر وابستگی‌ها را پیشاپیش در `wheelhouse` تهیه کنید:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --no-index --find-links wheelhouse -r requirements.txt
powershell -NoProfile -File scripts\run_recovery_acceptance.ps1 -OutputDir qa\recovery-windows
```

از جعل platform یا فعال کردن Actions استفاده نکنید. Qt باید روی Desktop واقعی نمایش داده شود؛ برای probe تعاملی، `QT_QPA_PLATFORM=offscreen` یا `minimal` نگذارید. پذیرش خودکار قبلی تصویر offscreen تولید می‌کند؛ probe جدید دکمه‌های واقعی و پنجره قابل نمایش را اجرا می‌کند. کاربر باید نمایش روی صفحه را نیز بررسی کند.

بسته ابتدا نبود Actions و SHA-256 قرنطینه را کنترل می‌کند، مجموعه کامل را اجرا می‌کند، gate موجود را اجرا می‌کند و سپس Preview/Save/هشدار واقعی فارسی، SQLite، CSV، XLSX، DOCX و PDF چندصفحه‌ای را بررسی می‌کند. هم‌زمانی با multiprocessing spawn در مجموعه کامل است. هر خطا اجرای مراحل وابسته را متوقف می‌کند.

خروجی‌های JSON/log و تصاویر تمام صفحات PDF در پوشه خروجی باقی می‌مانند. Word و Excel باید با برنامه واقعی Windows Office باز شوند؛ جهت جدول، متن/فونت فارسی، صفر ابتدایی شناسه، ستون‌ها و جمع مرجع ۷۲۶ برای ۱۲۰ ردیف را بررسی کنید. سازگاری Office و تأیید بصری مالک با parse XML یا رندر Linux اثبات نمی‌شوند.

در محیط این مأموریت Windows و Office موجود نیستند: `BLOCKED_NOT_WINDOWS` و `BLOCKED_ENVIRONMENT`. هیچ PR صرفاً به‌دلیل گذر این آزمون‌ها اجازه Merge ندارد.
