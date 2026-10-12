import pytest

ezdxf = pytest.importorskip("ezdxf")

from core.cad.phase21 import (
    CadExtractionError,
    artifact_fingerprint,
    extract_dxf,
    extract_cad,
    layer_index,
    validate_extraction,
)


def _sample_dxf() -> bytes:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    layer = doc.layers.new("STRUCT")
    layer.dxf.color = 7
    msp = doc.modelspace()
    msp.add_line((0, 0), (3, 4), dxfattribs={"layer": layer.dxf.name})
    msp.add_circle((10, 10), 2, dxfattribs={"layer": layer.dxf.name})
    msp.add_text("B1", dxfattribs={"layer": layer.dxf.name})
    msp.add_lwpolyline([(0, 0), (2, 0), (2, 2)], dxfattribs={"layer": layer.dxf.name})
    stream = __import__("io").StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def test_dxf_extracts_geometry_layers_blocks_units_and_count():
    result = extract_dxf(_sample_dxf())
    assert result.format == "DXF"
    assert result.units == "mm"
    assert result.object_count == 4
    assert "STRUCT" in result.layers
    assert {e.entity_type for e in result.entities} == {"LINE", "CIRCLE", "TEXT", "LWPOLYLINE"}
    assert any(k == "length" and v == 5.0 for e in result.entities for k, v in e.geometry)


def test_layer_index_and_export_are_deterministic():
    raw = _sample_dxf()
    result = extract_dxf(raw)
    validate_extraction(result)
    index = layer_index(result)
    assert len(index["STRUCT"]) == 4
    payload = result.export_payload()
    assert payload["schema"] == "structuralpro.cad.dwg_dxf.v1"
    assert payload["object_count"] == 4
    assert payload["source_fingerprint"] == artifact_fingerprint(raw)


def test_invalid_or_unitless_dxf_fails_closed():
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 0
    stream = __import__("io").StringIO()
    doc.write(stream)
    result = extract_dxf(stream.getvalue().encode("utf-8"))
    with pytest.raises(CadExtractionError, match="units"):
        validate_extraction(result)


def test_dwg_requires_explicit_backend():
    with pytest.raises(CadExtractionError, match="DWG backend"):
        extract_cad(b"fake-dwg", "DWG")


def test_dwg_backend_is_explicit_and_validated():
    sample = extract_dxf(_sample_dxf())

    def backend(payload: bytes):
        return type(sample)(
            format="DWG",
            version="AC1032",
            units="mm",
            layers=sample.layers,
            blocks=sample.blocks,
            entities=sample.entities,
            source_fingerprint=artifact_fingerprint(payload),
            backend="explicit-dwg-backend",
        )

    result = extract_cad(b"dwg-bytes", "DWG", backend)
    validate_extraction(result)
    assert result.format == "DWG"
    assert result.backend == "explicit-dwg-backend"
