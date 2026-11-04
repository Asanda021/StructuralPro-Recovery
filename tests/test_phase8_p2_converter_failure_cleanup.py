"""SYNTHETIC subprocess boundary; real DXF parser validates the output."""
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess

import ezdxf
import pytest

from core.drawings.dwg_converter import OfflineDWGConverter, DWGConversionError


def source(tmp_path):
    path=tmp_path/"نقشه.dwg"
    path.write_bytes(b"AC1018_SYNTHETIC_SOURCE_NOT_A_REAL_DWG")
    return path


def valid_output(path):
    doc=ezdxf.new("R2018")
    doc.modelspace().add_line((0,0),(3,4))
    doc.saveas(path)


@pytest.mark.parametrize("failure", ["exit", "timeout", "oserror"])
def test_partial_output_removed_on_every_converter_failure(tmp_path,monkeypatch,failure):
    src=source(tmp_path);out=tmp_path/"out";out.mkdir()
    keep=out/"unrelated.dxf";keep.write_bytes(b"unrelated user file")
    def run(command,**kwargs):
        Path(command[2]).write_bytes(b"partial converter output")
        if failure=="timeout":raise subprocess.TimeoutExpired(command,1)
        if failure=="oserror":raise OSError("process failed")
        return SimpleNamespace(returncode=1,stderr="failed",stdout="")
    monkeypatch.setattr(subprocess,"run",run)
    with pytest.raises(DWGConversionError):
        OfflineDWGConverter("dwg2dxf").convert(src,out)
    assert not (out/(src.stem+".dxf")).exists()
    assert keep.read_bytes()==b"unrelated user file"


def test_converter_same_bytes_source_replacement_is_rejected(tmp_path,monkeypatch):
    src=source(tmp_path);out=tmp_path/"out"
    def run(command,**kwargs):
        valid_output(command[2])
        other=src.with_suffix(".new");other.write_bytes(src.read_bytes());os.replace(other,src)
        return SimpleNamespace(returncode=0,stderr="",stdout="")
    monkeypatch.setattr(subprocess,"run",run)
    with pytest.raises(DWGConversionError,match="تغییر"):
        OfflineDWGConverter("dwg2dxf").convert(src,out)
    assert not (out/(src.stem+".dxf")).exists()


def test_converter_receipt_cannot_hash_bytes_other_than_parsed_dxf(tmp_path,monkeypatch):
    src=source(tmp_path);out=tmp_path/"out"
    def run(command,**kwargs):
        valid_output(command[2])
        return SimpleNamespace(returncode=0,stderr="",stdout="")
    monkeypatch.setattr(subprocess,"run",run)
    real_read=ezdxf.readfile
    def replacing_reader(path,*args,**kwargs):
        doc=real_read(path,*args,**kwargs)
        Path(path).write_bytes(b"not the bytes that were parsed")
        return doc
    monkeypatch.setattr(ezdxf,"readfile",replacing_reader)
    with pytest.raises(DWGConversionError,match="تغییر|خروجی"):
        OfflineDWGConverter("dwg2dxf").convert(src,out)
    assert not (out/(src.stem+".dxf")).exists()


def test_converter_explicit_decode_errors_do_not_crash_valid_conversion(tmp_path,monkeypatch):
    src=source(tmp_path)
    def run(command,**kwargs):
        assert kwargs["encoding"]=="utf-8"
        assert kwargs["errors"]=="replace"
        valid_output(command[2])
        return SimpleNamespace(returncode=0,stderr="",stdout="")
    monkeypatch.setattr(subprocess,"run",run)
    result=OfflineDWGConverter("dwg2dxf").convert(src,tmp_path/"out")
    assert result.output.is_file()


def test_cleanup_does_not_own_preexisting_files_before_validation(tmp_path):
    out=tmp_path/"out";out.mkdir();(out/"oda").mkdir()
    for folder in (out,out/"oda"):
        (folder/"absent.dxf").write_bytes(b"preexisting owner data")
    with pytest.raises(FileNotFoundError):
        OfflineDWGConverter("dwg2dxf").convert(tmp_path/"absent.dwg",out)
    assert (out/"absent.dxf").read_bytes()==b"preexisting owner data"
    assert (out/"oda"/"absent.dxf").read_bytes()==b"preexisting owner data"


def test_cleanup_does_not_delete_same_stem_file_in_unused_converter_branch(tmp_path,monkeypatch):
    src=source(tmp_path);out=tmp_path/"out";(out/"oda").mkdir(parents=True)
    keep=out/"oda"/(src.stem+".dxf");keep.write_bytes(b"owner data")
    monkeypatch.setattr(subprocess,"run",lambda *a,**kw:SimpleNamespace(returncode=1,stderr="failed",stdout=""))
    with pytest.raises(DWGConversionError):
        OfflineDWGConverter("dwg2dxf").convert(src,out)
    assert keep.read_bytes()==b"owner data"
