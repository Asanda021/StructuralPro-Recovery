from core.platform.diagnostics_integrity_v1 import (
    DiagnosticRecord, build_bundle, validate_bundle, verify_bundle, bundle_fingerprint
)

def test_valid_bundle_and_fingerprint():
    b=build_bundle([DiagnosticRecord("E100","error","boom","engine")],
                   "1.0", {"platform":"Windows","python":"3.12"})
    assert validate_bundle(b)==[]
    assert verify_bundle(b)
    assert len(bundle_fingerprint(b))==64

def test_runtime_and_event_order_are_deterministic():
    a=build_bundle([DiagnosticRecord("A","info","a","x"),DiagnosticRecord("B","warning","b","y")],
                   "1.0", {"b":"2","a":"1"})
    c=build_bundle([DiagnosticRecord("A","info","a","x"),DiagnosticRecord("B","warning","b","y")],
                   "1.0", {"a":"1","b":"2"})
    assert a["sha256"]==c["sha256"]

def test_invalid_severity_and_missing_code_fail_closed():
    try: DiagnosticRecord("E","fatal","x","c").canonical()
    except ValueError: pass
    else: assert False
    assert validate_bundle({"schema_version":"v2","app_version":"1","runtime":{}, "events":[{}],"sha256":"0"*64})

def test_tampering_is_detected():
    b=build_bundle([], "1.0", {})
    b["events"].append({"code":"X","severity":"error","message":"tamper","component":"x"})
    assert not verify_bundle(b)

def test_required_app_version():
    try: build_bundle([], " ", {})
    except ValueError: pass
    else: assert False
