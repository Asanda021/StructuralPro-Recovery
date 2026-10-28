# checkpoint اجرایی P6-4 / P6-5

مبنا: PR #33، `dfb81112f1afe2d3e140665c69ff18b34bf8ff06`.

نقص واقعی: Manifest موتور GGUF مسیر `../outside.gguf` را با هش صحیح معتبر می‌دانست.
آزمون مستقل unittest پیش از اصلاح FAIL و پس از محدودکردن مسیر به ریشه مدل PASS شد.
symlink مستقیم نیز رد می‌شود. این آزمون از bytes صریحاً آزمایشی استفاده می‌کند و اجرای مدل نیست.

اجرای واقعی A2: BLOCKED. در checkout فعلی فقط `models/README.md` وجود دارد؛
`core/ai/model_manifest.json` دارای placeholder SHA/license و commercial_use=false است.
هیچ مدل، mmproj، runtime یا مجوز تجاری/بازتوزیع معتبر در این بررسی تأیید نشد.

نتیجه جدید: ۱ PASS unittest، صفر FAIL/ERROR/SKIP. آزمون Qt و Windows جدید اجرا نشده است.
نتیجه ۴۶ PASS قبلی فقط برای مبنای قبل از این تغییر معتبر است.

P6-4: PARTIAL (W1 قبلی حفظ، A2 واقعی BLOCKED).
P6-5: E3/E4/E5/E6 در این نوبت توسعه یا پذیرش نشده‌اند.
P6-6 منتظر؛ فازهای۷/۸ بدون تغییر؛ پیشرفت وزنی ثبت‌شده همان۸۵٪.
