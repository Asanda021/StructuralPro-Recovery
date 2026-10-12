from core.platform.cad_measurement_readiness_v1 import MeasurementBackendReadiness
from core.platform.external_dependency_provenance_v1 import (
    DependencyRecord,
    evaluate_dependency_provenance,
)
from core.platform.ifc_quantity_mapping_v1 import IFCQuantityMapping, evaluate_ifc_mapping


def test_measurement_boundary_is_fail_closed_and_stable():
    gate = MeasurementBackendReadiness(True, True, "dwg-1", "pdf-1")
    first = gate.evaluate()
    second = gate.evaluate()
    assert first["ready"] is True
    assert first["fingerprint"] == second["fingerprint"]

    blocked = MeasurementBackendReadiness(False, True, None, "pdf-1").evaluate()
    assert blocked["ready"] is False
    assert "dwg_converter_unavailable" in blocked["reasons"]


def test_ifc_mapping_requires_all_quantity_targets():
    mappings = [
        IFCQuantityMapping("BaseQuantities.NetVolume", "concrete_volume", "m3"),
        IFCQuantityMapping("Pset_Rebar.Weight", "rebar_weight", "kg"),
    ]
    result = evaluate_ifc_mapping(mappings, {"concrete_volume", "rebar_weight", "stock_bar_count"})
    assert result["ready"] is False
    assert result["missing_targets"] == ["stock_bar_count"]

    ready = evaluate_ifc_mapping(
        mappings + [IFCQuantityMapping("Pset_Rebar.StockBars", "stock_bar_count", "count")],
        {"concrete_volume", "rebar_weight", "stock_bar_count"},
    )
    assert ready["ready"] is True


def test_dependency_provenance_is_complete_only_with_source_license_and_checksum():
    records = [
        DependencyRecord("dwg-engine", "1.0", "vendor", "MIT", "abc123"),
        DependencyRecord("pdf-renderer", "2.0", "vendor", "Apache-2.0", "def456"),
    ]
    result = evaluate_dependency_provenance(records, {"dwg-engine", "pdf-renderer"})
    assert result["ready"] is True

    blocked = evaluate_dependency_provenance(
        [DependencyRecord("dwg-engine", "1.0", "", "MIT", "abc123")],
        {"dwg-engine", "pdf-renderer"},
    )
    assert blocked["ready"] is False
    assert "incomplete_dependency_record" in blocked["reasons"]


def test_fingerprints_are_deterministic():
    mapping = [IFCQuantityMapping("Q", "v", "m3")]
    assert evaluate_ifc_mapping(mapping, {"v"})["fingerprint"] == evaluate_ifc_mapping(mapping, {"v"})["fingerprint"]
