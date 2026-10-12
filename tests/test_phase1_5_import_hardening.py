from pathlib import Path

import ezdxf
import pytest

from core.drawings.dwg_converter import (
    CorruptDWGError,
    DWGConversionError,
    OfflineDWGConverter,
)


class SuccessfulProcess:
    returncode = 0
    stdout = ""
    stderr = ""


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "plan.dwg"
    source.write_bytes(b"AC1032" + b"valid-header-payload")
    return source


def test_converter_rejects_stale_dxf_when_process_writes_nothing(monkeypatch, tmp_path):
    source = _source(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    stale = output / "plan.dxf"
    stale.write_text("stale, invalid output", encoding="utf-8")
    converter = OfflineDWGConverter(executable="dwg2dxf")
    monkeypatch.setattr("core.drawings.dwg_converter.subprocess.run",
                        lambda *args, **kwargs: SuccessfulProcess())

    with pytest.raises(DWGConversionError, match="خروجی تولید نشد"):
        converter.convert(source, output)

    assert not stale.exists()


def test_converter_rejects_invalid_dxf_even_when_process_exits_successfully(monkeypatch, tmp_path):
    source = _source(tmp_path)
    output = tmp_path / "out"
    converter = OfflineDWGConverter(executable="dwg2dxf")

    def fake_run(command, **kwargs):
        Path(command[-1]).write_text("not a DXF", encoding="utf-8")
        return SuccessfulProcess()

    monkeypatch.setattr("core.drawings.dwg_converter.subprocess.run", fake_run)
    with pytest.raises(DWGConversionError, match="خروجی نامعتبر"):
        converter.convert(source, output)
    assert not (output / "plan.dxf").exists()


def test_converter_accepts_a_real_parseable_dxf(monkeypatch, tmp_path):
    source = _source(tmp_path)
    output = tmp_path / "out"
    converter = OfflineDWGConverter(executable="dwg2dxf")

    def fake_run(command, **kwargs):
        doc = ezdxf.new("R2018")
        doc.modelspace().add_line((0, 0), (3, 4), dxfattribs={"layer": "A-STRUCT"})
        doc.saveas(command[-1])
        return SuccessfulProcess()

    monkeypatch.setattr("core.drawings.dwg_converter.subprocess.run", fake_run)
    result = converter.convert(source, output)
    parsed = ezdxf.readfile(result.output)
    assert len(list(parsed.modelspace())) == 1
    assert result.output.name == "plan.dxf"


def test_converter_rejects_bad_dwg_signature_before_launching(monkeypatch, tmp_path):
    source = tmp_path / "bad.dwg"
    source.write_bytes(b"not-a-dwg")
    launched = []
    monkeypatch.setattr("core.drawings.dwg_converter.subprocess.run",
                        lambda *args, **kwargs: launched.append(args))
    with pytest.raises(CorruptDWGError):
        OfflineDWGConverter(executable="dwg2dxf").convert(source, tmp_path / "out")
    assert launched == []


def test_converter_requires_expected_oda_output_not_unrelated_dxf(monkeypatch, tmp_path):
    source = _source(tmp_path)
    output = tmp_path / "out"
    converter = OfflineDWGConverter(executable="ODAFileConverter.exe")

    def fake_run(command, **kwargs):
        odir = Path(command[2])
        unrelated = odir / "other.dxf"
        doc = ezdxf.new("R2018")
        doc.modelspace().add_line((0, 0), (1, 1))
        doc.saveas(unrelated)
        return SuccessfulProcess()

    monkeypatch.setattr("core.drawings.dwg_converter.subprocess.run", fake_run)
    with pytest.raises(DWGConversionError, match="خروجی تولید نشد"):
        converter.convert(source, output)


from core.drawings.dwg_converter import ConverterResult
from core.drawings.dwg_takeoff import DWGTakeoffEngine


def _valid_dxf(path: Path) -> Path:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.modelspace().add_line((0, 0), (3, 4), dxfattribs={"layer": "A-STRUCT"})
    doc.saveas(path)
    return path


def test_product_dwg_import_prefers_acadsharp_bridge_and_cleans_temporary_output(monkeypatch, tmp_path):
    source = _source(tmp_path)
    converted = _valid_dxf(tmp_path / "converted.dxf")

    class Bridge:
        available = True
        def convert(self, _source):
            return converted

    monkeypatch.setattr("core.cad.external_dwg_provider_v1.ACadSharpDWGProvider", Bridge)
    doc = DWGTakeoffEngine().import_file(source)

    assert doc.format == "DWG→DXF (ACadSharp)"
    assert doc.source == str(source)
    assert len(doc.entities) == 1
    assert not converted.exists()


def test_product_dwg_import_uses_offline_converter_only_when_bridge_unavailable(monkeypatch, tmp_path):
    source = _source(tmp_path)
    converted = _valid_dxf(tmp_path / "fallback.dxf")

    class Bridge:
        available = False

    class Offline:
        def convert(self, _source):
            return ConverterResult(source, converted, "oda")

    monkeypatch.setattr("core.cad.external_dwg_provider_v1.ACadSharpDWGProvider", Bridge)
    monkeypatch.setattr("core.drawings.dwg_converter.OfflineDWGConverter", Offline)
    doc = DWGTakeoffEngine().import_file(source)

    assert doc.format == "DWG→DXF (offline converter)"
    assert doc.source == str(source)
    assert len(doc.entities) == 1
    assert not converted.exists()


def test_product_dwg_import_does_not_hide_failure_of_available_acadsharp_bridge(monkeypatch, tmp_path):
    source = _source(tmp_path)

    class Bridge:
        available = True
        def convert(self, _source):
            raise RuntimeError("real conversion failure")

    class MustNotRunOffline:
        def __init__(self):
            raise AssertionError("fallback must not hide an available bridge failure")

    monkeypatch.setattr("core.cad.external_dwg_provider_v1.ACadSharpDWGProvider", Bridge)
    monkeypatch.setattr("core.drawings.dwg_converter.OfflineDWGConverter", MustNotRunOffline)
    with pytest.raises(RuntimeError, match="real conversion failure"):
        DWGTakeoffEngine().import_file(source)
