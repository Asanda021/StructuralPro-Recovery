"""Drawing/CAD/BIM source integrity acceptance for Priority 54."""
from pathlib import Path
from core.drawings.model_registry import ModelRegistry, ModelSource

def test_priority_54_source_fingerprint_and_metadata_validation(tmp_path: Path):
    source_file = tmp_path / "plan.dxf"
    source_file.write_text("STRUCTURALPRO-SOURCE-01", encoding="utf-8")
    digest = ModelRegistry.fingerprint(source_file)
    registry = ModelRegistry(sources=[ModelSource(id="SRC-1", path=str(source_file), format="dxf", revision="1", sha256=digest)])
    assert registry.source_integrity("SRC-1") == {"source_id":"SRC-1","exists":True,"sha256":digest,"matches_recorded_sha256":True,"format_matches_extension":True,"ok":True}

def test_priority_54_detects_changed_source_and_extension_mismatch(tmp_path: Path):
    source_file = tmp_path / "plan.dwg"
    source_file.write_text("ORIGINAL", encoding="utf-8")
    digest = ModelRegistry.fingerprint(source_file)
    registry = ModelRegistry(sources=[ModelSource(id="SRC-1", path=str(source_file), format="dxf", revision="2", sha256=digest)])
    source_file.write_text("TAMPERED", encoding="utf-8")
    result = registry.source_integrity("SRC-1")
    assert result["matches_recorded_sha256"] is False
    assert result["format_matches_extension"] is False
    assert result["ok"] is False

def test_priority_54_missing_source_is_not_silent(tmp_path: Path):
    missing = tmp_path / "missing.ifc"
    registry = ModelRegistry(sources=[ModelSource(id="SRC-1", path=str(missing), format="ifc", revision="1")])
    result = registry.source_integrity("SRC-1")
    assert result["exists"] is False
    assert result["sha256"] == ""
    assert result["ok"] is False
