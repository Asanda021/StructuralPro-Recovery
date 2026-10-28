# اصلاح Timeout پنجره Qt شمع — ۲۸ اکتبر ۲۰۲۶

**وضعیت: PARTIAL تا اتمام و بازرسی CI.** کد/آزمون واقعی روی PR34 اعمال و push شده است. SHA آزمون‌شونده `74cc37d68c35a0a113643e7538d9dce3378e3597`؛ workflow روی همان SHA ثابت است. [پذیرش مستقل](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40668037315) و [رگرسیون گسترده](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40668037298) آغاز شده‌اند؛ تا تولید نتیجه نهایی شمار Windows/Linux ادعا نمی‌شود.

در اجرای قبلی [40661082617](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40661082617) گزارش تحویل ثبت کرده Windows در `QMessageBox.exec` خط۱۴۱ و هنگام آزمون واقعی amendment با timeout۱۵۰۰ و exit۱۲۴ و JUnit مفقود مانده است. کد همان محل پنجره هشدار Qt با نام `BoredPileErrorMessage`، عنوان `کنترل دیتایل شمع` و دکمه Ok را می‌سازد. از stack به‌تنهایی اثبات نمی‌شود تایمر ۱۰ms علت قطعی Windows بوده است. درخواست مستقیم دریافت Artifact قبلی از API با Forbidden/credential نامعتبر مواجه شد؛ در این نوبت محتویات بایگانی را مستقیماً بازخوانی نکردیم و ادعای خلاف آن نداریم. [Artifact قبلی](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40661082617/artifacts/12805470944).

بازپخش کنترل‌شده با پنجره واقعی QMessageBox، نمایش تأخیری ۸۰ms و تایمر قبلی ۱۰ms نشان می‌دهد callback پیش از باز شدن پنجره اجرا می‌شود: [RED واقعی exit1](qtfix-old-timer-red.log)، [اسکریپت](qtfix-old-timer-repro.py). این امکان مسابقه را اثبات می‌کند؛ علت دقیق timeout Windows تا نتیجه اجرا هنوز فرضیه است.

تست واقعی با QTimer تکرارشونده و deadline محدود، فعال بودن QMessageBox، نام، عنوان، والد واقعی و دکمه استاندارد مورد انتظار را بررسی کرده و از QTest.mouseClick استفاده می‌کند. برای خطای amendment دکمه Ok و برای تأیید خروج بدون ذخیره دکمه Yes است؛ حالت پنجره غیرمنتظره بدون کلیک دکمه نامرتبط با خطای صریح پایان می‌یابد. انتظار نمایش فرم والد/شمع نیز محدود و به نام اصلی متصل است. در مسیر شکست فقط cleanup کنترل‌شده پنجره اجازه بازگشت pytest می‌دهد و شکست پنهان نمی‌شود. کد محصول، SQLite، CAS، شمار revision، رد مالکیت، BOQ و assertionهای قبلی محفوظ‌اند.

اجرای محلی واقعی Qt offscreen: [۹ PASS، صفر FAIL/ERROR/SKIP](qtfix-targeted.xml)، شامل آزمون جدید تأخیر و پنجره نامرتبط و suiteهای amendment/controller. Windows native و رگرسیون گسترده، تا گزارش مستقل GitHub در این checkpoint NOT VERIFIED است. نه Merge/ForcePush/main/Release/EXE و نه P6-6/فاز۷؛۸فاز و۸۵٪ حفظ است.

## رگرسیون محلی نسخه میانی

رگرسیون جاری محلی روی کد میانی1a37ec0 (پیش از کنترل والد در74cc37d) تکمیل شد:۸۳۷۱PASS،۱FAIL،۰ERROR،۱۰SKIP،۳warning؛۶۰۵٫۱۸ثانیه،بدونtimeout. شکست `tests/test_beam_historical_migration.py::test_migration_two_process_sqlite_cas[False]` از نوع `_queue.Empty` است. اجرای مستقل مجدد همان مورد۱PASS در۰٫۸۰ثانیه داشت؛ این نتیجه جداگانه، شکست full را حذف یا علت قطعی آن را ثابت نمی‌کند. XML/JSON/log اصلی و JUnit بازآزمایی در همین پوشه‌اند. این snapshot جای CI کد نهایی را نمی‌گیرد.

## CI پذیرش نهایی

[CI40668037315](https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/40668037315) SUCCESS: هر سیستم Linux و Windows native،۴۷۳PASS اصلی،۱۳۰تاریخی،۲۶security و۸+۸تکرارDPI، همگی صفرFAIL/ERROR/SKIP؛۱هشدارfitz در اصلی و۰ در دیگر مراحل. نسخه workflow b423fcf و کد/آزمون74cc37d یکسان‌اند؛ این بسته شامل آزمون واقعی شمع اصلاح‌شده است. هش JUnitهای واقعی از notices و artifact metadata در acceptance-ci-measured.json ثبت شده‌اند. رگرسیون گسترده هنوز باید جداگانه تمام شود؛ اینCIجای آن را نمی‌گیرد.
