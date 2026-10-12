from core.platform.diagnostics import DiagnosticEvent, build_support_bundle, validate_support_bundle
def test_support_bundle_is_deterministic_and_valid():
 e=[DiagnosticEvent("E001",details={"path":"/tmp/a","token":"secret"})]
 a=build_support_bundle(e,"1.2.3",{"platform":"Windows"}); b=build_support_bundle(e,"1.2.3",{"platform":"Windows"})
 assert validate_support_bundle(a)==[] and a["sha256"]==b["sha256"]
 assert a["events"][0]["details"]["token"]=="<redacted>"
def test_sensitive_keys_are_redacted_case_insensitively():
 b=build_support_bundle([DiagnosticEvent("E002",details={"API_KEY":"x","Authorization":"Bearer x","safe":"ok"})],"1.0")
 assert b["events"][0]["details"]=={"API_KEY":"<redacted>","Authorization":"<redacted>","safe":"ok"}
def test_invalid_bundle_fails_closed():
 assert validate_support_bundle({})
def test_bundle_excludes_project_and_environment_data():
 b=build_support_bundle([],"1.0",{"platform":"Linux"})
 assert "environment" not in b and "project" not in b and "files" not in b
