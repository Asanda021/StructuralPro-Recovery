from core.platform.provisioning_readiness_v1 import assess_provisioning, require_provisioning

def test_provisioning_is_explicit_and_deterministic():
    req = {"dwg_converter": True, "price_dataset": True, "gguf_license": True}
    a = require_provisioning(req)
    b = require_provisioning({k: req[k] for k in reversed(req)})
    assert a.ready and a.missing == () and a.fingerprint == b.fingerprint

def test_missing_external_asset_fails_closed():
    r = assess_provisioning({"dwg_converter": False, "price_dataset": True})
    assert not r.ready and r.missing == ("dwg_converter",)
    try:
        require_provisioning({"dwg_converter": False})
    except RuntimeError:
        pass
    else:
        raise AssertionError("missing provisioning must fail closed")
