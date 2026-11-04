"""Synthetic regression: success=0 and modelspace roster are not financial permission.

No original private DWG is embedded in this test.  Synthetic DXF is valid,
but no independent C-API status or complete graph/revision proof is available.
"""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from core.cad.external_dwg_provider_v1 import ACadSharpDWGProvider
from core.drawings.dwg_converter import ConverterResult, OfflineDWGConverter
from core.drawings.dwg_takeoff import DWGTakeoffEngine, cad_entity_geometry, verify_cad_item


@pytest.fixture
def offline_document(tmp_path, monkeypatch):
    source = tmp_path / 'synthetic.dwg'
    source.write_bytes(b'AC1018_SYNTHETIC_NOT_A_VALID_DWG_FILE')
    output = tmp_path / 'synthetic.dxf'
    drawing = ezdxf.new('R2018')
    drawing.header['$INSUNITS'] = 6  # Even an explicit *DXF* metres header cannot prove DWG provenance.
    drawing.modelspace().add_line((0, 0), (2, 0), dxfattribs={'layer': 'A-WALL'})
    drawing.saveas(output)
    def fake_convert(self, path):
        return ConverterResult(
            source=Path(path), output=output, converter='dwg2dxf',
            source_sha256=sha256(Path(path).read_bytes()).hexdigest(),
            output_sha256=sha256(output.read_bytes()).hexdigest(),
            dwg_version='2004', exit_code=0,
            source_coverage={'status':'MATCHED_INDEPENDENT_MODELSPACE_ROSTER',
                             'source_count': 1, 'converted_count': 1,
                             'quantity_approved': False},
        )
    monkeypatch.setattr(ACadSharpDWGProvider, 'available', property(lambda self: False))
    monkeypatch.setattr(OfflineDWGConverter, 'available', property(lambda self: True))
    monkeypatch.setattr(OfflineDWGConverter, 'convert', fake_convert)
    document = DWGTakeoffEngine().import_file(source)
    assert document.units == 'm'
    assert document.entities
    return document


def test_cli_success_and_roster_do_not_authorize_payable_geometry(offline_document):
    receipt = offline_document.conversion
    assert receipt['exit_code'] == 0
    assert receipt['source_coverage']['status'] == 'MATCHED_INDEPENDENT_MODELSPACE_ROSTER'
    assert receipt['geometry_approved_for_financial_takeoff'] is False
    assert receipt['native_decoder_full_object_graph_verified'] is False
    assert receipt['native_decoder_error_mask_verified'] is False
    assert receipt['source_revision_verified'] is False
    assert receipt['requires_independent_original_dwg_oracle'] is True


def test_offline_unsafe_document_remains_visible_but_not_payable(offline_document):
    assert offline_document.entities[0].entity_type == 'LINE'
    assert DWGTakeoffEngine().summarize(offline_document)['entities'] >= 1
    with pytest.raises(ValueError, match='DWG'):
        DWGTakeoffEngine().layer_takeoff(offline_document, {'A-WALL': {'metric': 'length'}})
    with pytest.raises(ValueError, match='DWG'):
        cad_entity_geometry(offline_document, offline_document.entities[0].handle, 'length')
    with pytest.raises(ValueError, match='DWG'):
        verify_cad_item(SimpleNamespace(cad_evidence=None), offline_document)


def test_financial_veto_survives_unit_change_and_false_positive_roster(offline_document):
    # Unit evidence cannot override an explicit converter veto.
    offline_document.units = 'cm'
    offline_document.conversion['source_coverage']['status'] = 'MATCHED_INDEPENDENT_MODELSPACE_ROSTER'
    with pytest.raises(ValueError, match='DWG'):
        DWGTakeoffEngine().layer_takeoff(offline_document, {'A-WALL': {'metric': 'count'}})