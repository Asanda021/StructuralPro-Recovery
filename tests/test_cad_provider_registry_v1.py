from pathlib import Path
import ezdxf
import pytest
from core.cad.provider_registry_v1 import provider_info, read_production_cad

def make_dxf(path: Path) -> None:
    doc = ezdxf.new("R2018")
    doc.layers.add("A-WALL")
    doc.modelspace().add_line((0, 0), (5, 0), dxfattribs={"layer": "A-WALL"})
    doc.saveas(path)

def test_dxf_is_a_bundled_authorized_provider(tmp_path):
    path = tmp_path / "drawing.dxf"
    make_dxf(path)
    info = provider_info("dxf")
    evidence = read_production_cad(path)
    assert info.bundled is True
    assert info.authorized is True
    assert info.provider == "ezdxf"
    assert evidence.dxf_version == "AC1032"
    assert len(evidence.entities) == 1

def test_dwg_registry_reports_bundled_authorized_acadsharp_provider(tmp_path):
    path = tmp_path / "drawing.dwg"
    path.write_bytes(b"not-a-dwg")
    info = provider_info("DWG")
    assert info.bundled is True
    assert info.authorized is True
    assert info.provider == "ACadSharp"
    with pytest.raises(ValueError, match="authorized provider"):
        read_production_cad(path)

def test_external_provider_can_be_injected_without_bypassing_boundary(tmp_path):
    path = tmp_path / "drawing.dwg"
    path.write_bytes(b"opaque")
    class Provider:
        def read(self, source):
            assert source == path
            return {"source": str(source), "authorized": True}
    assert read_production_cad(path, dwg_provider=Provider())["authorized"] is True
