import pytest

from core.iran.data import (
    AdjustmentIndex,
    IranDataRegistry,
    default_iran_sources,
)


def test_default_official_iran_source_metadata_is_provenance_only():
    registry = IranDataRegistry()
    for source in default_iran_sources():
        registry.register_source(source)
    source = registry.source(1404, "ابنیه")
    assert source is not None
    assert source.verified is True
    assert "سازمان برنامه و بودجه" in source.publisher
    assert source.circular_number == "۱۴۰۳/۷۷۴۹۴۸"


def test_missing_adjustment_index_fails_closed():
    registry = IranDataRegistry()
    result = registry.apply_adjustment(1000, year=1405, quarter=1, discipline="ابنیه")
    assert result["status"] == "missing_index"
    assert result["base_amount"] == 1000


def test_adjustment_import_is_traceable_and_does_not_fabricate_values():
    registry = IranDataRegistry()
    csv_text = "year,quarter,discipline,index\n1405,1,ابنیه,1.25\n"
    result = registry.import_adjustment_csv(
        csv_text, source_id="official:test", source_url="https://example.invalid/source",
        provisional=True,
    )
    assert result["rows"] == 1
    out = registry.apply_adjustment(1000, year=1405, quarter=1, discipline="ابنیه")
    assert out["status"] == "ok"
    assert out["adjusted_amount"] == pytest.approx(1250)
    assert out["provisional"] is True
    assert out["source_id"] == "official:test"


def test_adjustment_index_validation():
    with pytest.raises(ValueError):
        AdjustmentIndex(1405, 5, "ابنیه", 1.0, "source")
    with pytest.raises(ValueError):
        AdjustmentIndex(1405, 1, "ابنیه", -1.0, "source")
