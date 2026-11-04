"""Public synthetic tests only: no real CAD, hashes or proprietary receipts."""
import pytest

from tools.p8p2_instrument_b64_stage import (
    STAGES, instrument_pinned_decoder, patch_100k_guard,
)


def _fixture():
    calls = "\n".join(f"  error |= {name} (dat, dwg);" for name in STAGES)
    return (
        "/* for 2004 and 2010+ */\nstatic int\n"
        "decode_R2004 (Bit_Chain *restrict dat, Dwg_Data *restrict dwg)\n{\n"
        + calls +
        "\nadded = dwg_decode_add_object (dwg, &obj_dat, &obj_dat, last_offset);\n"
        "          if (added > 0)\n"
        "            error |= added;\n}\n"
    )


def test_pinned_r2004_section_wrapping_is_diagnostic_only():
    result = instrument_pinned_decoder(_fixture())
    assert result.count("SP_P8P2_B64_STAGE") == 1
    assert result.count("SP_P8P2_B64_OBJECT_RETURN") == 1
    assert result.count("sp_p8p2_b64_stage (") == len(STAGES) + 1
    assert "error |= added;" in result
    assert "return returned;" in result
    assert "sp_p8p2_obj_b64_seen++ < 16" in result
    assert "DWG_ERR_VALUEOUTOFBOUNDS" in result


def test_unexpected_upstream_source_fails_closed():
    with pytest.raises(ValueError, match="callsite changed"):
        instrument_pinned_decoder(_fixture().replace("error |= read_2004_section_handles", "// removed"))
    with pytest.raises(ValueError, match="Already instrumented"):
        instrument_pinned_decoder(instrument_pinned_decoder(_fixture()))
    with pytest.raises(ValueError, match="entrypoint"):
        instrument_pinned_decoder(_fixture().replace("/* for 2004 and 2010+ */", "CHANGED"))


def test_100k_guard_is_single_explicit_diagnostic_change():
    original = "VALUEOUTOFBOUNDS (num_ents, 50000)"
    assert patch_100k_guard(original) == "VALUEOUTOFBOUNDS (num_ents, 100000)"
    for bad in ("", original + original, "VALUEOUTOFBOUNDS (num_ents, 100000)"):
        with pytest.raises(ValueError):
            patch_100k_guard(bad)
