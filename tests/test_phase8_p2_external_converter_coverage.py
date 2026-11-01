"""SYNTHETIC decoder/subprocess boundaries; real DXF parsing and coverage gates.

Motivation: a real local LibreDWG conversion of private source returned exit 0
while omitting 8 source LINEs. The private source is never a CI fixture.
"""
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from core.drawings.dwg_converter import OfflineDWGConverter,DWGConversionError
from core.drawings.dwg_takeoff import DWGTakeoffEngine,cad_entity_geometry


def setup(tmp_path,monkeypatch,*,missing=False,wrong_type=False,source_units='meters',dxf_unit=6):
    import ezdwg
    source=tmp_path/'source.dwg';source.write_bytes(b'AC1018_SYNTHETIC_DECODER_BOUNDARY_NOT_REAL_DWG')
    def run(command,**kwargs):
        d=ezdxf.new('R2018');d.units=dxf_unit
        e=d.modelspace().add_line((0,0),(3,4))
        d.saveas(command[2])
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr('core.drawings.dwg_converter.subprocess.run',run)
    sample=ezdxf.new('R2018').modelspace().add_line((0,0),(3,4))
    handle=int(sample.dxf.handle,16)
    rows=[SimpleNamespace(handle=handle,dxftype='CIRCLE' if wrong_type else 'LINE')]
    if missing:rows.append(SimpleNamespace(handle=handle+1,dxftype='LINE'))
    raw=SimpleNamespace(version='AC1018',units=source_units,
                        modelspace=lambda:SimpleNamespace(iter_entities=lambda:iter(rows)))
    monkeypatch.setattr(ezdwg,'read',lambda path:raw)
    return source


def test_success_exit_with_missing_source_handle_is_rejected(tmp_path,monkeypatch):
    source=setup(tmp_path,monkeypatch,missing=True)
    with pytest.raises(DWGConversionError,match='پوشش|موجودیت|جزء'):
        OfflineDWGConverter('dwg2dxf').convert(source,tmp_path/'out')
    assert not (tmp_path/'out/source.dxf').exists()


def test_same_count_but_changed_source_type_is_rejected(tmp_path,monkeypatch):
    source=setup(tmp_path,monkeypatch,wrong_type=True)
    with pytest.raises(DWGConversionError,match='پوشش|موجودیت|جزء'):
        OfflineDWGConverter('dwg2dxf').convert(source,tmp_path/'out')


@pytest.mark.parametrize('source_units,dxf_unit',[(None,6),('millimeters',6)])
def test_external_converter_may_not_invent_or_change_declared_units(tmp_path,monkeypatch,source_units,dxf_unit):
    source=setup(tmp_path,monkeypatch,source_units=source_units,dxf_unit=dxf_unit)
    with pytest.raises(DWGConversionError,match='واحد'):
        OfflineDWGConverter('dwg2dxf').convert(source,tmp_path/'out')


def test_matching_independent_roster_has_explicit_receipt_without_quantity_approval(tmp_path,monkeypatch):
    source=setup(tmp_path,monkeypatch)
    receipt=OfflineDWGConverter('dwg2dxf').convert(source,tmp_path/'out')
    assert receipt.source_coverage['status']=='MATCHED_INDEPENDENT_MODELSPACE_ROSTER'
    assert receipt.source_coverage['source_count']==1
    assert receipt.source_coverage['converted_count']==1
    assert receipt.source_coverage['quantity_approved'] is False


def test_unsupported_3dface_is_retained_with_reason_instead_of_crashing_import(tmp_path):
    d=ezdxf.new('R2018');d.units=6
    face=d.modelspace().add_3dface([(0,0,0),(1,0,0),(1,1,2),(0,1,0)])
    p=tmp_path/'face.dxf';d.saveas(p)
    doc=DWGTakeoffEngine().import_file(p)
    assert len(doc.entities)==1 and doc.entities[0].entity_type=='3DFACE'
    assert doc.entities[0].data['unsupported_measurement']
    with pytest.raises(ValueError):cad_entity_geometry(doc,face.dxf.handle,'area')
