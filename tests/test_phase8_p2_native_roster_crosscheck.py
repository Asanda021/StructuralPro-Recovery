"""Pure negative tests: no private DWG and no proprietary decoder required."""
from dataclasses import dataclass
import pytest
from core.drawings.dwg_native_roster_crosscheck import classify_missing_line, _line_equal

@dataclass
class Raw:
    section: str='BLOCKS'
    block_handle: str='F21'
    block_record_handle: str='F20'
    owner_handle: str='F20'

class Entity:
    def __init__(self, fields):
        self.dxf = fields
class DXF:
    def __init__(self, fields):
        self.dxf = type('Fields',(),{'layer':'L', 'get':fields.get})()
        self.dxf.start=fields['start'];self.dxf.end=fields['end']

@pytest.mark.parametrize('owner,model,raw,geom,expected',[
 (0xF20,2,Raw(),True,'MATCHED_BLOCK_DEFINITION_NOT_DIRECT_MODELSPACE'),
 (0xF20,2,None,True,'ABSENT_FROM_RAW_DXF'),
 (0xF20,2,Raw(),False,'RAW_DXF_GEOMETRY_OR_LAYER_MISMATCH'),
 (2,2,Raw(),True,'DIRECT_MODELSPACE_MISSING_FROM_PARSED_DXF'),
 (None,2,Raw(),True,'NATIVE_OWNERSHIP_UNVERIFIED'),
 (0xF1F,2,Raw(),True,'MODELSPACE_OR_BLOCK_OWNERSHIP_CONFLICT'),
 (0xF20,2,Raw(section='ENTITIES'),True,'MODELSPACE_OR_BLOCK_OWNERSHIP_CONFLICT'),
 (0xF20,2,Raw(owner_handle='F22'),True,'MODELSPACE_OR_BLOCK_OWNERSHIP_CONFLICT'),
 (0xF20,2,Raw(block_record_handle=''),True,'MODELSPACE_OR_BLOCK_OWNERSHIP_CONFLICT'),
 (0xF20,2,Raw(block_handle=''),True,'MODELSPACE_OR_BLOCK_OWNERSHIP_CONFLICT'),
])
def test_fail_closed_owner_classification(owner,model,raw,geom,expected):
    assert classify_missing_line(owner,model,raw,geom)==expected


def test_source_line_geometry_match():
    source=Entity({'start':(1,2,0),'end':(3,4,0),'invisible':0})
    target=DXF({'start':(1,2,0),'end':(3,4,0),'invisible':0})
    assert _line_equal(source,target,'L')


def test_source_line_geometry_mismatch():
    source=Entity({'start':(1,2,0),'end':(3,4,0),'invisible':0})
    target=DXF({'start':(1,2,0),'end':(3,4.1,0),'invisible':0})
    assert not _line_equal(source,target,'L')


def test_source_line_hidden_discrepancy():
    source=Entity({'start':(1,2,0),'end':(3,4,0),'invisible':1})
    target=DXF({'start':(1,2,0),'end':(3,4,0),'invisible':0})
    assert not _line_equal(source,target,'L')


def test_raw_dxf_block_owner_is_preserved(tmp_path):
    from core.drawings.dwg_native_roster_crosscheck import locate_raw_dxf_lines
    p=tmp_path/'source.dxf'
    p.write_text('0\nSECTION\n2\nBLOCKS\n0\nBLOCK\n5\nF21\n330\nF20\n2\n\n0\nLINE\n5\nF22\n330\nF20\n8\n0\n10\n1\n20\n2\n11\n3\n21\n4\n0\nENDBLK\n0\nENDSEC\n0\nEOF\n')
    result=locate_raw_dxf_lines(p,{0xF22})
    assert len(result)==1
    r=result[0xF22]
    assert r.section=='BLOCKS' and r.owner_handle=='F20'
    assert r.block_handle=='F21' and r.block_record_handle=='F20'
    assert r.start==(1.,2.,0.) and r.end==(3.,4.,0.)


def test_raw_dxf_duplicate_line_handle_is_rejected(tmp_path):
    from core.drawings.dwg_native_roster_crosscheck import locate_raw_dxf_lines
    p=tmp_path/'duplicate.dxf'
    repeated='0\nLINE\n5\nF22\n330\nF20\n8\n0\n10\n1\n20\n2\n11\n3\n21\n4\n'
    p.write_text('0\nSECTION\n2\nBLOCKS\n'+repeated+repeated+'0\nENDSEC\n0\nEOF\n')
    with pytest.raises(ValueError,match='Duplicate'):
        locate_raw_dxf_lines(p,{0xF22})


def test_sha_guard_rejects_mismatched_original_before_opening_decoder(tmp_path):
    from core.drawings.dwg_native_roster_crosscheck import audit_native_to_dxf
    dwg=tmp_path/'file.dwg';dxf=tmp_path/'file.dxf'
    dwg.write_bytes(b'AC1018fake');dxf.write_bytes(b'0\nEOF\n')
    with pytest.raises(ValueError,match='Source hash mismatch'):
        audit_native_to_dxf(dwg,dxf,expected_dwg_sha256='0'*64,expected_dxf_sha256='0'*64)

@pytest.mark.parametrize("end", [(4, 5, 6.001), (1e9 + 0.0005, 5, 6)])
def test_source_line_absolute_precision_detects_z_or_large_coordinate_loss(end):
    reference_x = 1e9 if end[0] > 1e8 else 4
    source = Entity({"start": (1, 2, 3), "end": (reference_x, 5, 6)})
    target = DXF({"start": (1, 2, 3), "end": end})
    assert not _line_equal(source, target, "L")
