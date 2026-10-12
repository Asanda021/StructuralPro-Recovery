from pathlib import Path

import ezdxf
import pytest

from core.cad.ezdxf_provider_v1 import CADProviderError, read_cad, read_dxf


def make_fixture(path: Path) -> None:
    doc = ezdxf.new("R2018")
    doc.layers.add("A-WALL")
    doc.layers.add("A-DOOR")
    msp = doc.modelspace()
    msp.add_line((0, 0), (5, 0), dxfattribs={"layer": "A-WALL"})
    msp.add_lwpolyline([(0, 0), (0, 3), (4, 3)], dxfattribs={"layer": "A-WALL"})
    msp.add_text("DOOR-01", dxfattribs={"layer": "A-DOOR", "insert": (1, 1)})
    doc.saveas(path)


def test_real_dxf_is_parsed_not_mocked(tmp_path):
    path = tmp_path / "sample.dxf"
    make_fixture(path)
    evidence = read_dxf(path)

    assert evidence.dxf_version == "AC1032"
    assert len(evidence.entities) == 3
    assert evidence.layers == ("A-DOOR", "A-WALL")
    assert {e.entity_type for e in evidence.entities} == {"LINE", "LWPOLYLINE", "TEXT"}


def test_dwg_fails_closed_without_authorized_provider(tmp_path):
    path = tmp_path / "sample.dwg"
    path.write_bytes(b"not-a-dwg")
    with pytest.raises(CADProviderError, match="authorized"):
        read_cad(path)


def test_unknown_cad_format_fails_closed(tmp_path):
    path = tmp_path / "sample.xyz"
    path.write_bytes(b"data")
    with pytest.raises(CADProviderError, match="Unsupported CAD"):
        read_cad(path)
