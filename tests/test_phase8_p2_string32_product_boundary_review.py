"""Synthetic-only product adapter safety review, never private CAD data.

A native or CLI decoder result does not imply payable quantity acceptance.
"""
from pathlib import Path
from types import SimpleNamespace
import subprocess

import ezdxf
import pytest

from core.drawings.dwg_converter import OfflineDWGConverter, DWGConversionError


def _synthetic_dwg(tmp_path):
    src = tmp_path / "synthetic_only.dwg"
    src.write_bytes(b"AC1018_SYNTHETIC_NOT_A_REAL_DWG")
    return src


def test_patched_cli_exit_zero_and_parseable_dxf_still_veto_financial(tmp_path, monkeypatch):
    src = _synthetic_dwg(tmp_path)
    original = src.read_bytes()

    def fake_run(command, **kwargs):
        assert "-o" in command and command[2].endswith(".dxf")
        doc = ezdxf.new("R2018")
        doc.modelspace().add_line((0, 0), (3, 4))
        doc.saveas(command[2])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = OfflineDWGConverter("experimental_p8p2_dwg2dxf").convert(
        src, tmp_path / "new_output"
    )
    receipt = result.source_coverage
    assert src.read_bytes() == original
    assert result.exit_code == 0
    assert result.financial_veto is True
    assert receipt["financial_quantity_approved"] is False
    assert receipt["converter_integrity_veto"] is True
    native = receipt["libredwg_c_api_diagnostic"]
    assert native["c_api_error_mask_verified"] is False
    assert native["c_api_error_mask"] is None
    assert native["cli_success_is_lossless_conversion_proof"] is False


def test_native_probe_success_without_dxf_cannot_be_used_as_converter(tmp_path, monkeypatch):
    src = _synthetic_dwg(tmp_path)
    def fake_run(command, **kwargs):
        assert "-o" not in command
        # A diagnostic C-API probe returns 0 without producing a DXF.
        return SimpleNamespace(returncode=0, stdout="STRUCTURALPRO_C_API_MASK=4\n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(DWGConversionError, match="DXF"):
        OfflineDWGConverter("structuralpro_libredwg_capi_probe").convert(
            src, tmp_path / "new_output"
        )


def test_converter_candidate_unchanged_default_financial_veto():
    from core.drawings.dwg_converter import ConverterResult
    d = ConverterResult(
        source=Path("synthetic.dwg"),
        output=Path("synthetic.dxf"),
        converter="p8p2_experimental_dwg2dxf",
    )
    assert d.financial_veto is True
