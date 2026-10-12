# اجرای واقعی Recovery، ۱۲ اکتبر ۲۰۲۶

مخزن: Asanda021/StructuralPro-Recovery؛ main تغییری نکرده است.
پایه: 7889609ad8901ab5993ec5d7f42ebdb78a4d80bd، شاخه fix/windows-acceptance-no-actions-20261012.
شاخه مستقل اصلاح: fix/recovery-quarantine-guard-20261012.

## دریافت و اعتبارسنجی
پلاگین GitHub مجوز pull/push را تأیید کرد. Clone مستقیم یک‌بار به علت عدم اتصال به proxy:8080 شکست خورد و تکرار نشد. سورس با اتصال GitHub و استفاده مجدد از فایل‌های محلی فقط پس از برابر بودن SHA-1 Blob دریافت شد. ۱۴۹۶ فایل، صفر اختلاف؛ درخت Git دقیقاً 9742274be8ffa312672137960dd82faba8dc45eb است. Commit خام نیز با SHA دقیق پایه بازسازی شد (بدون newline انتهای پیام). Checkout معتبر shallow است؛ تاریخچه کامل بازیابی نشده است. بکاپ نام‌برده‌شده در پیام جدید پیوست قابل‌دریافت نداشت؛ مسیر پلاگین کافی بود. اسناد تاریخی صرفاً شواهدند و دستورهای این مأموریت از پیام کاربر گرفته شدند.

## نقص تأییدشده و اصلاح
Windows acceptance gate فقط تعداد YAMLهای قرنطینه را می‌شمرد و لینک پوشه، لینک فایل و فایل غیرمنتظره را رد نمی‌کرد. سه آزمون جدید پیش از اصلاح: 3 failed, 7 passed؛ پس از اصلاح، مسیر قرنطینه باید پوشه واقعی با فایل‌های عادی yml/yaml و بدون symbolic link باشد. تعداد ۱۹۳ همچنان کنترل می‌شود. اصلاح با سیاست fail-closed ابزار QA تاریخی هم‌راستا است.

## آزمون‌های واقعی
- اولین targeted offline QA: 55 passed, 0 failed, 0 skipped؛ exit 0.
- مجموعه هدفمند پس از اصلاح: 75 passed, 0 failed, 0 skipped؛ exit 0.
- Qt viewer واقعی و gate/Office exports پس از نصب PySide6: 15 passed, 0 failed, 0 skipped؛ exit 0.
- Full اصلی پیش از اصلاح و قبل از نصب PySide6: 2094 passed, 56 failed, 9 skipped؛ exit 1.
- Full اصلی نهایی پس از نصب PySide6: 2102 passed, 55 failed, 7 skipped؛ exit 1. مخزن اصلی کاملاً سبز نیست.
- کپی موقت قراردادهای Workflow تاریخی: 2157 passed, 0 failed, 7 skipped؛ exit 0. ۱۹۳ فایل فقط در fixture موقت کپی و سپس حذف شدند؛ هیچ GitHub Actions اجرا نشده و هیچ Workflow واقعی فعال نشده است.
- SQLite واقعی با multiprocessing spawn و پنج پردازش مستقل: ۶۵ اسمبلی / ۱۹۵ متره / ۱۳ BOQ پرداختی، quantities دیوار=۱۴۰، کف=۹۵، قرنیز=۳۰؛ PRAGMA integrity_check=ok. تضاد optimistic به‌صورت صریح در اسکریپت آزمون دوباره تلاش شد؛ این به معنای retry خودکار رابط برنامه نیست. این آزمون Linux است و پذیرش چندپردازشی Windows محسوب نمی‌شود.
- smoke واقعی Linux: ManualTakeoffDialog ساخته شد، RTL و screenshot بررسی شدند، PDF فارسی با exporter اصلی تولید، با PyMuPDF باز و رندر شد. تصویر PDF خوانا و ستون‌ها RTL مشاهده شدند؛ human_visual_approval همچنان PENDING است.
- CSV با UTF-8 BOM و صفر ابتدایی، XLSX با RTL و مقدار عددی، DOCX با bidiVisual و PDF فارسی آزمون شدند.
- پذیرش Windows واقعی: BLOCKED_NOT_WINDOWS، exit 2، missing_dependencies=[]؛ platform override برای اعلام پذیرش استفاده نشده است.
- git diff --check موفق.

Python 3.12.14؛ pytest 9.1.1؛ PySide6 6.12.0. فهرست نسخه‌های کامل و شواهد اجرا در بکاپ قرار می‌گیرند. هیچ EXE، Installer، Build، Release، Merge، Actions dispatch یا تغییر main انجام نشده است. PRهای ۱ تا ۴ باز، Draft و merge نشده‌اند. تأیید Windows/Word/PDF توسط مالک هنوز لازم است.

## تمام شکست‌های باقی‌مانده در full اصلی
این ۵۵ آزمون مسیر .github/workflows را لازم می‌دانند؛ فایل‌ها عمداً در recovery/disabled_workflows قرنطینه‌اند. آزمون‌ها برای سبز شدن تغییر داده نشده‌اند.

- `tests.test_binary_build_security_contract::test_mobile_contract_automatic_and_android_binary_manual`
- `tests.test_binary_build_security_contract::test_p37_disables_all_automatic_release_and_build_triggers`
- `tests.test_binary_build_security_contract::test_p100_owner_main_only_with_isolated_publish_permissions`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>0]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>1]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>2]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>3]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>4]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>5]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>6]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>7]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>8]`
- `tests.test_binary_build_security_contract::test_mutated_android_policy_must_fail_closed[<lambda>9]`
- `tests.test_binary_build_security_contract::test_local_guard_presence_never_proves_actual_github_environment`
- `tests.test_owner_approved_binary_build_workflows::test_binary_build_requires_explicit_owner_dispatch[.github/workflows/windows-release.yml]`
- `tests.test_owner_approved_binary_build_workflows::test_binary_build_requires_explicit_owner_dispatch[.github/workflows/edition-builds.yml]`
- `tests.test_owner_approved_binary_build_workflows::test_binary_build_requires_explicit_owner_dispatch[.github/workflows/android-build.yml]`
- `tests.test_owner_approved_binary_build_workflows::test_binary_build_requires_explicit_owner_dispatch[.github/workflows/p37-real-product-deployment.yml]`
- `tests.test_owner_approved_binary_build_workflows::test_automatic_cad_smoke_runs_only_unit_tests_without_compiling_exe`
- `tests.test_p37_real_product_deployment::test_p37_deployment_contract_is_complete`
- `tests.test_p37_release_gate_separation::test_build_and_release_jobs_separate`
- `tests.test_p37_release_gate_separation::test_unapproved_release_default_false`
- `tests.test_p37_release_gate_separation::test_release_artifact_bound_to_same_run_and_validated_before_publish`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>0]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>1]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>2]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>3]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>4]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>5]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>6]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>7]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>8]`
- `tests.test_p37_release_gate_separation::test_publish_mutations_rejected[<lambda>9]`
- `tests.test_p37_release_gate_separation::test_release_version_is_not_interpolated_into_powershell_source`
- `tests.test_p37_release_gate_separation::test_auditor_marks_mutated_publication_unprotected[condition]`
- `tests.test_p37_release_gate_separation::test_auditor_marks_mutated_publication_unprotected[environment]`
- `tests.test_p37_release_gate_separation::test_auditor_marks_mutated_publication_unprotected[secret]`
- `tests.test_p37_release_gate_separation::test_auditor_marks_mutated_publication_unprotected[needs]`
- `tests.test_p37_release_gate_separation::test_auditor_marks_mutated_publication_unprotected[write_permission]`
- `tests.test_p37_release_gate_separation::test_auditor_marks_mutated_publication_unprotected[preflight]`
- `tests.test_p37_release_gate_separation::test_auditor_marks_mutated_publication_unprotected[publish_approval]`
- `tests.test_p61_p70_release_delivery::test_windows_release_workflow_contains_required_delivery_gates`
- `tests.test_priority_10_compliance::test_release_workflow_has_deterministic_artifact_inputs`
- `tests.test_priority_10_release::test_release_workflow_validates_payload_and_installer`
- `tests.test_priority_10_release_integrity::test_release_workflow_has_stable_placeholder_injection`
- `tests.test_priority_10_release_integrity::test_release_workflow_enforces_tag_version_consistency`
- `tests.test_priority_10_release_integrity::test_release_workflow_generates_traceability_manifest`
- `tests.test_priority_17_reports_excel_pdf::test_report_ci_jobs_install_canonical_pdf_dependencies`
- `tests.test_priority_38_pre_release_freeze::test_release_surfaces_remain_present`
- `tests.test_priority_41_ci_dependency_parity::test_ci_workflows_install_canonical_runtime_requirements`
- `tests.test_priority_41_ci_dependency_parity::test_ci_workflows_keep_test_runner_explicit`
- `tests.test_priority_42_windows_runtime_smoke::test_windows_workflow_executes_application_smoke`
- `tests.test_priority_43_release_artifact_integrity::test_release_workflow_validates_manifest_artifact_hashes`
- `tests.test_priority_49_windows_installer_acceptance::test_windows_release_runs_installed_application_smoke`
- `tests.test_priority_9_qa::test_priority9_regression_surface_files_exist`

## Skipped

- `::tests.test_ifc_mesh_viewer`: collection skipped
- `::tests.test_phase22_ifc_bim`: collection skipped
- `tests.test_windows_build_native_failures::test_native_failure_stops_build_before_stale_payload_is_accepted[1]`: PowerShell runtime unavailable
- `tests.test_windows_build_native_failures::test_native_failure_stops_build_before_stale_payload_is_accepted[2]`: PowerShell runtime unavailable
- `tests.test_windows_build_native_failures::test_native_failure_stops_build_before_stale_payload_is_accepted[3]`: PowerShell runtime unavailable
- `tests.test_windows_build_native_failures::test_native_failure_stops_build_before_stale_payload_is_accepted[4]`: PowerShell runtime unavailable
- `tests.test_windows_build_native_failures::test_native_failure_stops_build_before_stale_payload_is_accepted[5]`: PowerShell runtime unavailable
