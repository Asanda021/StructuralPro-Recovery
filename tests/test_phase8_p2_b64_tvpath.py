"""Public synthetic tests only: exact source anchors, safe markers, no CAD."""
import pytest

from core.drawings.libredwg_native_trace_runner import parse_helper_stdout
from tools.p8p2_instrument_b64_field_oracle import (
    _FDL_FIELDS, instrument_fdl_spec,
)
from tools.p8p2_instrument_b64_tvpath import (
    add_fdl_tv_diagnostic, add_object_site_probes,
)


def test_tv_preflight_and_null_wrapper_are_r2004_scoped():
    src = "\n".join(field for field, _ in _FDL_FIELDS)
    result = add_fdl_tv_diagnostic(instrument_fdl_spec(src))
    assert result.count("SP_P8P2_FDL_2004_ONLY") >= 2
    assert result.count("SP_P8P2_FDL_PREFLIGHT_REJECT") == 1
    assert result.count("#define bit_read_TV(x) sp_p8p2_fdl_tv_read(x)") == 1
    assert result.count("#undef bit_read_TV") == 1
    assert result.count("FIELD_VECTOR_T (features, TU32, num_features, 0);") == 1
    assert "_obj->num_features * 2" in result
    assert "field value" not in result
    with pytest.raises(ValueError, match="feature-vector"):
        add_fdl_tv_diagnostic(result)
    with pytest.raises(ValueError, match="feature-vector"):
        add_fdl_tv_diagnostic(src.replace("FIELD_VECTOR_T (features, TU32, num_features, 0);", "CHANGED"))


def _object_region():
    return (
        "int\ndwg_decode_add_object (Dwg_Data *restrict dwg)\n{\n"
        "return DWG_ERR_VALUEOUTOFBOUNDS;\n"
        "return error;\n"
        "return error | DWG_ERR_VALUEOUTOFBOUNDS;\n"
        "return realloced ? -1 : error;\n"
        "}\n/** dwg_decode_unknown\n"
    )


def test_object_return_sites_are_exhaustive_and_do_not_modify_returns():
    result = add_object_site_probes(_object_region())
    assert result.count('sp_p8p2_obj_site ("') == 4
    assert 'sp_p8p2_obj_site ("ms_stream_overflow")' in result
    assert 'sp_p8p2_obj_site ("object_size_bounds")' in result
    assert 'sp_p8p2_obj_site ("invalid_class_index")' in result
    assert 'sp_p8p2_obj_site ("final_accumulation")' in result
    for part in (
        "return DWG_ERR_VALUEOUTOFBOUNDS;",
        "return error;",
        "return error | DWG_ERR_VALUEOUTOFBOUNDS;",
        "return realloced ? -1 : error;",
    ):
        assert part in result
    with pytest.raises(ValueError, match="missing or ambiguous"):
        add_object_site_probes(result)


def test_exact_tvpath_helper_identity_is_not_confusable_with_previous_builds():
    receipt = (
        "STRUCTURALPRO_LIBREDWG_COMMIT=a835758-exp100k-b64tvpath\n"
        "STRUCTURALPRO_C_API_MASK=68\n"
        "STRUCTURALPRO_C_API_OBJECTS=101504\n"
    )
    good = parse_helper_stdout(receipt, "a835758", "sortentstable_100k_b64tvpath")
    assert good["c_api_return_mask"] == 68
    assert good["observed_build_variant"] == "sortentstable_100k_b64tvpath"
    for wrong_variant in (
        "upstream", "sortentstable_100k", "sortentstable_100k_b64field",
        "sortentstable_100k_b64stage",
    ):
        with pytest.raises(ValueError, match="unpinned"):
            parse_helper_stdout(receipt, "a835758", wrong_variant)


def test_ci_builds_actual_tvpath_instrumenter_and_checks_patch_identity():
    from pathlib import Path
    workflow = Path(".github/workflows/phase8-p2-libredwg-b64-tvpath.yml").read_text()
    assert 'python -m tools.p8p2_instrument_b64_tvpath "$RUNNER_TEMP/libredwg-b64"' in workflow
    assert 'python -m tools.p8p2_instrument_b64_field_oracle ' not in workflow
    assert workflow.count("grep -Fq 'SP_P8P2_FDL_TV_NULL'") == 1
    assert workflow.count("grep -Fq 'SP_P8P2_FDL_PREFLIGHT_REJECT'") == 1
    assert workflow.count("grep -Fq 'SP_P8P2_B64_OBJECT_SITE'") == 1


def test_tv_null_reason_oracle_reads_only_a_shadow_cursor():
    from tools.p8p2_instrument_b64_tvpath import _EXTRA_HELPERS
    assert "Bit_Chain preview_mode = *dat;" in _EXTRA_HELPERS
    assert "Bit_Chain preview = *dat;" in _EXTRA_HELPERS
    assert "_EXTRA_HELPERS" not in _EXTRA_HELPERS
    assert _EXTRA_HELPERS.count("bit_read_TV (dat)") == 1
    for label in ("HEADER_BOUNDS", "PREFIX_BOUNDS", "PAYLOAD_BOUNDS", "ALLOC_OR_OTHER"):
        assert label in _EXTRA_HELPERS
    assert "SP_P8P2_FDL_TV_NULL_REASON=%s" in _EXTRA_HELPERS
    assert "fprintf (stderr, \"%s\", v)" not in _EXTRA_HELPERS
