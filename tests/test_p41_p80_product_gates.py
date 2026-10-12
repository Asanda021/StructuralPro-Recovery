from __future__ import annotations

from pathlib import Path

import pytest

from core.drawings.pdf_takeoff import PDFTakeoffAdapter
from core.drawings.unified_takeoff import UnifiedDrawingTakeoff
from core.drawings.auto_takeoff import detect_scale
from core.pricing.catalog import PriceCatalog, PriceItem
from core.pricing.source_registry import PriceSource, PriceSourceRegistry


ROOT = Path(__file__).resolve().parents[1]


def test_windows_release_contract_is_versioned_and_fail_closed():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert version.count(".") == 2
    script = (ROOT / "packaging" / "build_windows.ps1").read_text(encoding="utf-8")
    assert "Packaged VERSION" in script
    assert "STRUCTURALPRO_SMOKE" in script
    assert "Get-FileHash" in script
    assert "BuildInstaller requested" in script


def test_pdf_scale_parser_never_guesses():
    assert detect_scale("")["status"] == "unknown"
    assert detect_scale("scale 1:100")["scale"] == 100.0
    assert detect_scale("1:100 1:50")["status"] == "ambiguous"


def test_pdf_text_takeoff_is_review_required():
    adapter = PDFTakeoffAdapter()
    candidates = adapter.text_takeoff_candidates([
        type("P", (), {"page": 1, "text": "Wall 4 m", "width": 100.0, "height": 100.0})()
    ])
    assert candidates
    assert all(row["needs_confirmation"] is True for row in candidates)


def test_unknown_dwg_converter_fails_closed(tmp_path, monkeypatch):
    source = tmp_path / "sample.dwg"
    source.write_bytes(b"not-a-dwg")
    monkeypatch.setenv("STRUCTURALPRO_DWG_CONVERTER", "")
    from core.drawings.dwg_converter import OfflineDWGConverter
    converter = OfflineDWGConverter(executable=None)
    if converter.available:
        pytest.skip("machine has an installed converter")
    with pytest.raises(RuntimeError):
        converter.convert(source)


def test_price_source_registry_requires_verifiable_provenance():
    registry = PriceSourceRegistry()
    source = PriceSource(
        year=1404,
        discipline="building",
        title="official dataset",
        publisher="official publisher",
        source_id="official-1404",
        checksum="abc",
        verified=True,
    )
    csv = "year,group,chapter,code,description,unit,unit_price\n1404,A,1,1-1,Concrete,m3,100"
    result = registry.validate_import(source, csv)
    assert result["valid"] is True
    assert result["sha256"]
    assert registry.verify_record(source, "abc") is True


def test_price_catalog_keeps_year_and_code_identity():
    catalog = PriceCatalog([
        PriceItem(1403, "building", "1", "1-1", "Old", "m3", 10),
        PriceItem(1404, "building", "1", "1-1", "New", "m3", 20),
    ])
    assert catalog.get("1-1", 1403).unit_price == 10
    assert catalog.get("1-1", 1404).unit_price == 20
    assert catalog.get("1-1").year == 1404
