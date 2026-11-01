"""Synthetic source boundary for 8-LINE-loss recovery. No private DWG in CI.

A successful DXF import is NOT an engineering or financial acceptance receipt.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from core.cad.optional_strict_python_dwg_provider import (
    StrictPythonDWGError, _validate_native_entity_roster,
)
from core.drawings.dwg_converter import DWGDroppedLineError
from core.drawings.dwg_takeoff import DWGTakeoffEngine


def sample_roster(*, count=8, drift=False, wrong_layer=False, missing=False):
    d = ezdxf.new("R2018")
    d.header["$INSUNITS"] = 6
    d.layers.new("SOURCE-WALL")
    d.layers.new("WRONG")
    model = d.modelspace()
    raw_lines = []
    for i in range(count):
        handle = 0xF100 + i
        a = (float(i), 2.0, 0.0)
        b = (float(i + 3), 6.0, 1.0)
        attrs = {"handle": f"{handle:X}", "layer": "WRONG" if wrong_layer and i == 0 else "SOURCE-WALL"}
        if not missing or i != 0:
            model.add_line(a, (b[0] + 0.1 if drift and i == 0 else b[0], b[1], b[2]), dxfattribs=attrs)
        raw_lines.append(SimpleNamespace(
            handle=handle, dxftype="LINE",
            dxf={"start": a, "end": b, "layer_handle": 0xAA}))
    raw = SimpleNamespace(
        layers=[SimpleNamespace(handle=0xAA, name="SOURCE-WALL")],
        modelspace=lambda: SimpleNamespace(iter_entities=lambda: iter(raw_lines)))
    return raw, d


def test_native_to_dxf_roster_and_exact_line_geometry_and_layers():
    native, d = sample_roster()
    receipt = _validate_native_entity_roster(native, d)
    assert receipt["source_entity_count"] == 8
    assert receipt["line_geometry_verified"] == 8
    assert receipt["line_layers_verified"] == 8
    assert receipt["handle_type_roster_matched"] is True


@pytest.mark.parametrize("problem", ["drift", "wrong_layer", "missing"])
def test_native_roster_refuses_line_loss_changed_geometry_or_layer(problem):
    native, d = sample_roster(**{problem: True})
    with pytest.raises(StrictPythonDWGError):
        _validate_native_entity_roster(native, d)


def setup_import(tmp_path, monkeypatch, *, verified=True, strict_available=True):
    import core.cad.external_dwg_provider_v1 as external
    import core.drawings.dwg_converter as converter
    import core.cad.optional_strict_python_dwg_provider as strict_module

    source = tmp_path / "source.dwg"
    source.write_bytes(b"AC1018_SYNTHETIC_NOT_REAL_DWG")
    out = tmp_path / "recovered.dxf"
    original = sha256(source.read_bytes()).hexdigest()
    native, doc = sample_roster()
    assert _validate_native_entity_roster(native, doc)["line_geometry_verified"] == 8
    doc.saveas(out)
    proof = SimpleNamespace(
        output=out, output_sha256=sha256(out.read_bytes()).hexdigest(),
        source_sha256=original, source_unit="m",
        source_modelspace_verified=verified, line_geometry_verified_count=8,
        line_layer_verified_count=8, skipped_entities=0,
        written_entities=8, total_entities=8)
    monkeypatch.setattr(external, "ACadSharpDWGProvider", lambda: SimpleNamespace(available=False))
    def reject(_):
        raise DWGDroppedLineError(8)
    monkeypatch.setattr(converter, "OfflineDWGConverter", lambda: SimpleNamespace(
        available=True, executable="dwg2dxf", convert=reject))
    monkeypatch.setattr(strict_module, "StrictPythonDWGProvider", lambda: SimpleNamespace(
        available=strict_available, convert=lambda source: proof))
    return source, out


def test_exact_dropped_lines_recovered_by_second_verified_real_dxf_parser(tmp_path, monkeypatch):
    source, out = setup_import(tmp_path, monkeypatch)
    imported = DWGTakeoffEngine().import_file(source)
    assert len([e for e in imported.entities if e.entity_type == "LINE"]) == 8
    assert imported.format == "DWG→DXF (strict recovered missing LINEs)"
    assert imported.conversion["primary_dropped_line_count"] == 8
    assert imported.conversion["line_geometry_verified_count"] == 8
    assert imported.conversion["geometry_approved_for_financial_takeoff"] is False
    assert imported.conversion["legacy_metre_rows_approved"] == 0
    assert not out.exists()


def test_unverified_strict_output_is_deleted_and_never_imported(tmp_path, monkeypatch):
    source, out = setup_import(tmp_path, monkeypatch, verified=False)
    with pytest.raises(RuntimeError, match="تطبیق کامل"):
        DWGTakeoffEngine().import_file(source)
    assert not out.exists()


def test_missing_second_decoder_still_blocks_all_quantities(tmp_path, monkeypatch):
    source, _ = setup_import(tmp_path, monkeypatch, strict_available=False)
    with pytest.raises(DWGDroppedLineError, match="8"):
        DWGTakeoffEngine().import_file(source)
