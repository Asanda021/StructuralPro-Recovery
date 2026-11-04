"""Synthetic safety regression for LibreDWG's documented error bitmask."""
import pytest
from core.drawings.libredwg_error_mask import (
    decode_libredwg_error_mask, libredwg_cli_receipt,
)


def test_historical_68_is_two_independent_flags_without_causal_inference():
    r = decode_libredwg_error_mask(68)
    assert r['known_mask'] == 68
    assert r['unknown_bits'] == 0
    assert r['flags'] == [
        {'bit': 4, 'name': 'DWG_ERR_UNHANDLEDCLASS'},
        {'bit': 64, 'name': 'DWG_ERR_VALUEOUTOFBOUNDS'},
    ]
    assert r['map_aec_causation_verified'] is False
    assert r['out_of_bounds_causation_verified'] is False
    assert r['financial_quantity_approved'] is False
    assert r['status'] == 'DECODE_ERROR_FLAGS_PRESENT_NO_GO'


@pytest.mark.parametrize('bit,name', [
    (1, 'DWG_ERR_WRONGCRC'), (2, 'DWG_ERR_NOTYETSUPPORTED'),
    (4, 'DWG_ERR_UNHANDLEDCLASS'), (8, 'DWG_ERR_INVALIDTYPE'),
    (16, 'DWG_ERR_INVALIDHANDLE'), (32, 'DWG_ERR_INVALIDEED'),
    (64, 'DWG_ERR_VALUEOUTOFBOUNDS'), (128, 'DWG_ERR_CLASSESNOTFOUND'),
    (256, 'DWG_ERR_SECTIONNOTFOUND'), (512, 'DWG_ERR_PAGENOTFOUND'),
    (1024, 'DWG_ERR_INTERNALERROR'), (2048, 'DWG_ERR_INVALIDDWG'),
    (4096, 'DWG_ERR_IOERROR'), (8192, 'DWG_ERR_OUTOFMEM'),
])
def test_each_documented_flag_has_exact_identity(bit, name):
    assert decode_libredwg_error_mask(bit)['flags'] == [{'bit': bit, 'name': name}]


def test_unknown_mask_bits_are_not_ignored():
    r = decode_libredwg_error_mask(0x10000 | 4)
    assert r['unknown_bits'] == 0x10000
    assert r['contains_critical_bits'] is True
    assert r['status'] == 'UNKNOWN_C_API_ERROR_BITS_NO_GO'


def test_zero_mask_is_not_engineering_approval():
    r = decode_libredwg_error_mask(0)
    assert r['flags'] == []
    assert r['status'] == 'ZERO_MASK_ONLY_NOT_FULL_SOURCE_VALIDATION'
    assert r['engineering_source_integrity_approved'] is False


@pytest.mark.parametrize('bad', [-1, 2**32, 1.5, None, True, '68'])
def test_reject_non_integer_or_unbounded_masks(bad):
    with pytest.raises(ValueError):
        decode_libredwg_error_mask(bad)


def test_cli_zero_cannot_be_treated_as_c_api_mask_zero():
    r = libredwg_cli_receipt(0, converter_is_libredwg=True)
    assert r['cli_exit_code'] == 0
    assert r['c_api_error_mask'] is None
    assert r['c_api_error_mask_verified'] is False
    assert r['c_api_status'] == 'NOT_OBSERVED_C_API_BITMASK_CLI_ONLY'
    assert r['financial_quantity_approved'] is False


def test_oda_exit_zero_is_not_libredwg_c_api_observation():
    r = libredwg_cli_receipt(0, converter_is_libredwg=False)
    assert r['c_api_status'] == 'NOT_APPLICABLE_NOT_LIBREDWG_CLI'
    assert r['c_api_error_mask_verified'] is False


@pytest.mark.parametrize('invalid', [-2, 65536, 0.5, True, None, '0'])
def test_invalid_cli_exit_code_is_refused(invalid):
    with pytest.raises(ValueError):
        libredwg_cli_receipt(invalid, converter_is_libredwg=True)


def test_boolean_provider_indicator_is_required():
    with pytest.raises(ValueError):
        libredwg_cli_receipt(0, converter_is_libredwg=1)