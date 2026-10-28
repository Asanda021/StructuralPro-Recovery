# ادامه مستقل

ابتدا HEAD زنده PR #33 را بخوانید. مبنای این checkpoint برابر
`dfb81112f1afe2d3e140665c69ff18b34bf8ff06` بود.

اصلاح موجود را دوباره نسازید: GGUFProductionRuntime مسیر خارج از model_root و symlink مستقیم
را رد می‌کند؛ test_phase6_p4_model_isolation.py یک RED→GREEN واقعی دارد.

ادامه لازم: آزمون‌های قدیمی GGUF و W1/Qt روی اصلاح جدید؛ بررسی مسیر create_engine در برابر
تعویض فایل پس از verification؛ اتصال context/cancel/fallback موجود A2؛ سپس شاخه و PR Draft
مستقل P6-5 و پیاده‌سازی E3 تا E6 با سرویس‌های موجود.

مدل واقعی در checkout موجود نیست و Manifest placeholder است؛ A2 واقعی BLOCKED باقی بماند.
این مانع نباید توسعه E3/E4/E5/E6 را متوقف کند. هیچ‌یک در این checkpoint COMPLETE نیستند.
Merge/Release/EXE/Force Push/main ممنوع؛ فقط۸فاز و یک نسخه کامل Windows.
