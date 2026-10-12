from pathlib import Path
import pytest
from core.cad.external_dwg_provider_v1 import ACadSharpDWGProvider, DWGConverterConfig, DWGProviderError

def test_acadsharp_provider_fails_closed_when_bridge_is_missing(tmp_path: Path) -> None:
    source = tmp_path / "plan.dwg"
    source.write_bytes(b"DWG-test")
    provider = ACadSharpDWGProvider(DWGConverterConfig(executable=str(tmp_path / "missing-bridge.exe")))
    with pytest.raises(DWGProviderError, match="bridge was not found"):
        provider.read(source)

def test_acadsharp_provider_rejects_non_dwg_input(tmp_path: Path) -> None:
    source = tmp_path / "plan.dxf"
    source.write_text("0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    provider = ACadSharpDWGProvider(DWGConverterConfig(executable="missing-bridge"))
    with pytest.raises(DWGProviderError, match="accepts .dwg only"):
        provider.convert(source)

def test_acadsharp_provider_invocation_is_explicit(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "plan.dwg"
    source.write_bytes(b"DWG-test")
    bridge = tmp_path / "bridge.exe"
    bridge.write_bytes(b"placeholder")
    calls = []
    class Result:
        returncode = 0
        stdout = ""
        stderr = ""
    def fake_run(command, **kwargs):
        calls.append(command)
        Path(command[2]).write_text("0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
        return Result()
    monkeypatch.setattr("core.cad.external_dwg_provider_v1.subprocess.run", fake_run)
    monkeypatch.setattr("core.cad.external_dwg_provider_v1.read_dxf", lambda path: object())
    provider = ACadSharpDWGProvider(DWGConverterConfig(executable=str(bridge)))
    converted = provider.convert(source)
    assert calls
    assert calls[0][0] == str(bridge)
    assert calls[0][1] == str(source.resolve())
    assert calls[0][2].endswith(".dxf")
    assert converted.is_file()
    converted.unlink(missing_ok=True)

def test_dwg_takeoff_reads_polyline_vertex_sequence_from_real_dxf(tmp_path: Path) -> None:
    """Regression: ezdxf POLYLINE.vertices is a sequence, not a method."""
    import ezdxf
    from core.drawings.dwg_takeoff import DWGTakeoffEngine

    source = tmp_path / "polyline.dxf"
    doc = ezdxf.new("R2018")
    doc.modelspace().add_polyline2d(
        [(0, 0), (3, 4), (6, 0)],
        close=True,
        dxfattribs={"layer": "A-STRUCT"},
    )
    doc.saveas(source)

    imported = DWGTakeoffEngine().import_file(source)
    polyline = next(entity for entity in imported.entities if entity.entity_type == "POLYLINE")

    assert polyline.data["points"] == [(0.0, 0.0), (3.0, 4.0), (6.0, 0.0)]
    assert polyline.data["length"] == pytest.approx(16.0)
    assert polyline.data["area"] == pytest.approx(12.0)

def test_dwg_takeoff_keeps_open_polyline_area_zero(tmp_path: Path) -> None:
    import ezdxf
    from core.drawings.dwg_takeoff import DWGTakeoffEngine

    source = tmp_path / "open-polyline.dxf"
    doc = ezdxf.new("R2018")
    doc.modelspace().add_polyline2d(
        [(0, 0), (3, 4), (6, 0)],
        close=False,
        dxfattribs={"layer": "A-STRUCT"},
    )
    doc.saveas(source)

    imported = DWGTakeoffEngine().import_file(source)
    polyline = next(entity for entity in imported.entities if entity.entity_type == "POLYLINE")
    assert polyline.data["length"] == pytest.approx(10.0)
    assert polyline.data["area"] == pytest.approx(0.0)

