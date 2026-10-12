"""Priority 44 — deep application/runtime audit contract."""
from core.platform.runtime_audit import audit_core_runtime

def test_core_runtime_surface_imports_cleanly():
    result = audit_core_runtime()
    assert result["valid"], result["failures"]
    assert result["module_count"] > 20
