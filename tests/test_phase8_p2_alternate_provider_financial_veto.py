"""Synthetic provider receipts do not prove full original-DWG fidelity."""
from hashlib import sha256
from types import SimpleNamespace

import ezdxf
import pytest

from core.drawings.dwg_takeoff import DWGTakeoffEngine, cad_entity_geometry, verify_cad_item


@pytest.fixture(params=['acadsharp', 'strict_python'])
def alternate_document(request, tmp_path, monkeypatch):
    from core.cad import external_dwg_provider_v1 as external
    from core.cad import optional_strict_python_dwg_provider as strict
    from core.drawings import dwg_converter
    source = tmp_path / 'synthetic.dwg'
    source.write_bytes(b'AC1018_SYNTHETIC_NOT_REAL_CAD')
    output = tmp_path / 'synthetic.dxf'
    drawing = ezdxf.new('R2018')
    drawing.header['$INSUNITS'] = 6
    drawing.modelspace().add_line((0, 0), (2, 0), dxfattribs={'layer': 'A-WALL'})
    drawing.saveas(output)
    proof = SimpleNamespace(
        output=output, output_sha256=sha256(output.read_bytes()).hexdigest(),
        source_sha256=sha256(source.read_bytes()).hexdigest(), source_unit='m',
        decoder_version='synthetic', signature='AC1018', total_entities=1,
        written_entities=1, skipped_entities=0, source_unit_code=6,
        source_handle_remaps=(), source_modelspace_verified=True,
        line_geometry_verified_count=1, original_dxf_unit_code=6,
        source_unit_restored_in_dxf=False,
    )
    monkeypatch.setattr(external, 'ACadSharpDWGProvider', lambda: SimpleNamespace(
        available=request.param == 'acadsharp', version='synthetic', convert=lambda _: output))
    monkeypatch.setattr(dwg_converter, 'OfflineDWGConverter', lambda: SimpleNamespace(available=False))
    monkeypatch.setattr(strict, 'StrictPythonDWGProvider', lambda: SimpleNamespace(
        available=True, convert=lambda _: proof))
    return DWGTakeoffEngine().import_file(source)


def test_unverified_alternate_decoder_blocks_all_financial_entrypoints(alternate_document):
    doc = alternate_document
    # Unit, zero skipped ModelSpace entities and exit=0 cannot prove proxy,
    # source revision, or SHX fidelity. This failed on the pre-fix PR head.
    with pytest.raises(ValueError, match='DWG'):
        DWGTakeoffEngine().layer_takeoff(doc, {'A-WALL': {'metric': 'length'}})
    with pytest.raises(ValueError, match='DWG'):
        cad_entity_geometry(doc, doc.entities[0].handle, 'length')
    with pytest.raises(ValueError, match='DWG'):
        verify_cad_item(SimpleNamespace(cad_evidence=None), doc)


def test_unverified_alternate_decoder_preserves_readonly_preview(alternate_document):
    doc = alternate_document
    assert doc.units == 'm'
    assert doc.entities[0].entity_type == 'LINE'
    assert DWGTakeoffEngine().summarize(doc)['entities'] == 1
    assert doc.source_sha256 == doc.conversion['source_sha256']


def test_native_dxf_measurement_candidate_remains_available(tmp_path):
    path = tmp_path / 'native.dxf'
    drawing = ezdxf.new('R2018')
    drawing.header['$INSUNITS'] = 6
    line = drawing.modelspace().add_line((0, 0), (2, 0))
    drawing.saveas(path)
    doc = DWGTakeoffEngine().import_file(path)
    assert cad_entity_geometry(doc, line.dxf.handle, 'length')[2] == pytest.approx(2)
