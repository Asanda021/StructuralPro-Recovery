"""Synthetic anonymous-BLOCK and raw DXF ownership regression, no user CAD in CI."""
from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest

from core.drawings.dwg_source_ownership import (
    locate_raw_dxf_lines,
    compare_raw_and_native_line,
    audit_native_lines_absent_from_dxf_modelspace,
)
from core.drawings.dwg_converter import (
    OfflineDWGConverter, DWGDroppedLineError,
    DWGSourceOwnershipConflictError,
)


def sample(tmp_path, *, count=8):
    d = ezdxf.new("R2018")
    d.header["$INSUNITS"] = 0
    block = d.blocks.new("*U_OWNERSHIP")
    lines = [block.add_line((i+100, i+200, 0), (i+102, i+205, 0))
             for i in range(count)]
    d.modelspace().add_line((0, 0, 0), (2, 2, 0))
    path = tmp_path / "anonymous.dxf"
    d.saveas(path)
    return path, lines, d


def native_source(lines):
    rows = [
        SimpleNamespace(
            handle=int(line.dxf.handle, 16), dxftype="LINE",
            dxf={"start": line.dxf.start, "end": line.dxf.end, "layer_handle": 1})
        for line in lines
    ]
    return SimpleNamespace(
        version="AC1018",
        units=None,
        layers=[SimpleNamespace(handle=1, name="0")],
        modelspace=lambda: SimpleNamespace(iter_entities=lambda: iter(rows)),
    )


def test_anonymous_block_lines_exist_in_raw_dxf_but_not_in_modelspace(tmp_path):
    path, lines, d = sample(tmp_path)
    assert len(list(ezdxf.readfile(path).modelspace())) == 1
    handles = {int(line.dxf.handle, 16) for line in lines}
    found = locate_raw_dxf_lines(path, handles)
    assert len(found) == 8
    assert {item.section for item in found.values()} == {"BLOCKS"}
    assert {item.block_name for item in found.values()} == {"*U_OWNERSHIP"}
    assert {item.owner_handle for item in found.values()} == {
        d.blocks.get("*U_OWNERSHIP").block_record_handle}
    for line in lines:
        item = found[int(line.dxf.handle, 16)]
        witness = SimpleNamespace(dxf={
            "start": line.dxf.start, "end": line.dxf.end, "layer_handle": 1})
        assert compare_raw_and_native_line(item, witness, {1: "0"})


def test_raw_block_conflict_eight_matching_lines_has_no_false_loss(tmp_path):
    path, lines, _ = sample(tmp_path)
    result = audit_native_lines_absent_from_dxf_modelspace(
        path, native_source(lines), {int(line.dxf.handle, 16) for line in lines})
    assert result["status"] == "RAW_DXF_PRESENT_MODELSPACE_OWNERSHIP_UNRESOLVED"
    assert result["raw_found"] == 8
    assert result["raw_geometry_and_layer_verified"] == 8
    assert result["missing_from_raw"] == 0
    assert result["locations"][0][0] == "BLOCKS"


def test_mismatched_raw_geometry_is_not_marked_verified(tmp_path):
    path, lines, _ = sample(tmp_path, count=1)
    witness = native_source(lines)
    bad = SimpleNamespace(
        handle=int(lines[0].dxf.handle, 16), dxftype="LINE",
        dxf={"start": (999, 0, 0), "end": (0, 0, 0), "layer_handle": 1})
    witness.modelspace = lambda: SimpleNamespace(iter_entities=lambda: iter([bad]))
    result = audit_native_lines_absent_from_dxf_modelspace(
        path, witness, {bad.handle})
    assert result["raw_found"] == 1
    assert result["raw_geometry_and_layer_verified"] == 0


def test_actual_absence_not_misreported_as_block_conflict(tmp_path):
    path, lines, _ = sample(tmp_path, count=1)
    result = audit_native_lines_absent_from_dxf_modelspace(
        path, native_source(lines), {0xABCDEF})
    assert result["status"] == "ABSENT_FROM_RAW_DXF"
    assert result["raw_found"] == 0


def test_raw_duplicate_selected_handle_cannot_be_ignored(tmp_path):
    path, lines, _ = sample(tmp_path, count=1)
    handle = lines[0].dxf.handle
    content = path.read_bytes()
    extra = (f"  0\nLINE\n  5\n{handle}\n  8\n0\n"
             f" 10\n0\n 20\n0\n 11\n1\n 21\n1\n").encode()
    assert b"  0\nENDBLK" in content
    path.write_bytes(content.replace(b"  0\nENDBLK", extra+b"  0\nENDBLK", 1))
    with pytest.raises(ValueError, match="Duplicate"):
        locate_raw_dxf_lines(path, {int(handle, 16)})


def test_external_converter_with_anonymous_block_is_blocked_by_ownership_gate(
    tmp_path, monkeypatch,
):
    """Nine native LINEs vs one parsed ModelSpace; eight raw lines are not lost."""
    import importlib.metadata
    import importlib.util
    import sys
    import core.drawings.dwg_converter as converter

    source = tmp_path / "site.dwg"
    source.write_bytes(b"AC1018_SYNTHETIC_NOT_A_REAL_DWG")
    output = tmp_path / "converted" / "site.dxf"
    _, block_lines, doc = sample(tmp_path)
    model_line = next(iter(doc.modelspace()))
    witness = native_source(block_lines + [model_line])

    def run(command, **kwargs):
        output.parent.mkdir(exist_ok=True)
        doc.saveas(output)
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(converter.subprocess, "run", run)
    old_find = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec",
        lambda name: SimpleNamespace() if name == "ezdwg" else old_find(name))
    old_version = importlib.metadata.version
    monkeypatch.setattr(
        importlib.metadata, "version",
        lambda name: "0.17.0" if name == "ezdwg" else old_version(name))
    monkeypatch.setitem(sys.modules, "ezdwg", SimpleNamespace(read=lambda _: witness))

    with pytest.raises(DWGSourceOwnershipConflictError) as captured:
        OfflineDWGConverter("dwg2dxf").convert(source, output.parent)
    evidence = captured.value.evidence
    assert evidence["raw_found"] == 8
    assert evidence["raw_geometry_and_layer_verified"] == 8
    assert evidence["missing_from_raw"] == 0
    assert not output.exists()
    assert not isinstance(captured.value, DWGDroppedLineError)
