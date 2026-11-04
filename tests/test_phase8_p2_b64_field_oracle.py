"""Public synthetic structural tests; no proprietary drawing or record data."""
import pytest

from tools.p8p2_instrument_b64_stage import STAGES
from tools.p8p2_instrument_b64_field_oracle import (
    _FDL_FIELDS, instrument_fdl_spec, instrument_decoder,
)


def _pinned_shape_fixture():
    calls = "\n".join(f"error |= {x} (dat, dwg);" for x in STAGES)
    fixed = "\n".join(
        f"  error = dwg_decode_TEST_{i} (dat, obj);" for i in range(70)
    )
    return (
        "/* for 2004 and 2010+ */\nstatic int\ndecode_R2004\n{\n"
        + calls
        + "\n}\nstatic int\nfiledeplist_private (Bit_Chain *restrict dat, Dwg_Data *restrict dwg)\n{\n}\n"
        + "  error = filedeplist_private (dat, dwg);\n"
        + "int\ndwg_decode_add_object (Dwg_Data *restrict dwg, Bit_Chain *dat,\n"
        + " Bit_Chain *hdl_dat, size_t address)\n{\n"
        + fixed
        + "\n  else if ((error = dwg_decode_variable_type (dwg, dat, hdl_dat, obj)) & DWG_ERR_UNHANDLEDCLASS)\n"
        + "error |= dwg_decode_UNKNOWN_OBJ (dat, obj);\n"
        + "error |= dwg_decode_UNKNOWN_ENT (dat, obj);\n"
        + "added = dwg_decode_add_object (dwg, &obj_dat, &obj_dat, last_offset);\n"
        + "          if (added > 0)\n            error |= added;\n"
        + "}\n/** dwg_decode_unknown\n"
    )


def test_fdl_exact_fields_instrumented_once():
    fields = "\n".join(field for field, _ in _FDL_FIELDS)
    out = instrument_fdl_spec(fields)
    assert out.count("sp_p8p2_fdl_enter (") == len(_FDL_FIELDS)
    assert out.count("sp_p8p2_fdl_complete (") == len(_FDL_FIELDS)
    for _, field in _FDL_FIELDS:
        assert f'sp_p8p2_fdl_enter ("{field}")' in out
        assert f'sp_p8p2_fdl_complete ("{field}")' in out
    assert "source_sha256" not in out


def test_fdl_source_drift_and_reinsertion_rejected():
    base = "\n".join(field for field, _ in _FDL_FIELDS)
    with pytest.raises(ValueError, match="missing or repeated"):
        instrument_fdl_spec(base.replace(_FDL_FIELDS[0][0], "CHANGED"))
    with pytest.raises(ValueError, match="already instrumented"):
        instrument_fdl_spec(instrument_fdl_spec(base))


def test_nested_object_decoder_calls_instrumented_without_changing_result():
    out, count = instrument_decoder(_pinned_shape_fixture())
    assert count == 70
    assert 'SP_P8P2_B64_DECODER=%s' in out
    assert 'SP_P8P2_B64_FDL_LAST=%s|%s' in out
    assert out.count('sp_p8p2_b64_decoded ("TEST_') == 70
    assert 'sp_p8p2_b64_decoded ("variable_type"' in out
    assert 'sp_p8p2_b64_decoded ("UNKNOWN_OBJ"' in out
    assert 'sp_p8p2_b64_decoded ("UNKNOWN_ENT"' in out
    assert 'error |= added;' in out


def test_object_source_anchors_fail_closed():
    x = _pinned_shape_fixture()
    with pytest.raises(ValueError, match="Unexpected pinned decoder call count"):
        instrument_decoder(x.replace("dwg_decode_TEST_0", "no_function"))
    with pytest.raises(ValueError, match="custom class decoder"):
        instrument_decoder(x.replace("dwg_decode_variable_type", "changed"))
