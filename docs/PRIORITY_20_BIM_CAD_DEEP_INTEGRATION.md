# Priority 20 — BIM / CAD Deep Integration

## هدف
ایجاد یک لایه یکپارچه و قابل اتکا بین مدل‌ها/نقشه‌های IFC، DWG، DXF و جریان متره موجود؛ بدون وابستگی اجباری به موتور خارجی و بدون ورود به طراحی سازه.

## قابلیت‌های اصلی
- Model Source Registry
- شناسه پایدار منبع مدل
- فرمت، revision، discipline، status، units و SHA-256 provenance
- Model Object Registry
- object_id پایدار در کنار source_id
- level / layer / properties / quantities
- جلوگیری از object تکراری
- جلوگیری از منبع تکراری
- کنترل مقدارهای نامعتبر
- inventory بر اساس فرمت و revision
- revision diff:
  - added
  - removed
  - changed
- تبدیل آبجکت‌های BIM/CAD نرمال‌شده به Takeoff Preview
- mapping به price code
- نمایش unmapped objects
- confirmation gate برای mappingهای ناقص
- source provenance در هر ردیف متره
- snapshot/export پایدار

## یکپارچگی با پروژه
Application Service اکنون APIهای زیر را دارد:
- register_model_source
- add_model_object
- project_model_inventory
- project_model_revision_diff
- project_model_takeoff_preview
- project_model_snapshot

اطلاعات در فیلدهای مستقل پروژه:
- model_sources
- model_objects

ذخیره می‌شوند و داده‌های قبلی دست‌نخورده باقی می‌مانند.

## رابطه با قابلیت‌های قبلی
این مرحله لایه integration را تکمیل می‌کند و از adapterهای موجود استفاده می‌کند:
- IFC / IfcOpenShell
- DXF / ezdxf
- DWG capability detection
- Offline DWG conversion
- existing drawing/takeoff pipeline

هسته جدید format-neutral است؛ بنابراین تست‌ها بدون نصب اجباری backendهای سنگین IFC/DWG اجرا می‌شوند.

## تست
فایل:
tests/test_priority_20_bim_cad_deep_integration.py

پوشش:
- duplicate source/object
- inventory
- BIM-to-takeoff mapping
- unmapped confirmation
- revision diff
- invalid quantity/source
- application persistence
- deterministic SHA-256 fingerprint
