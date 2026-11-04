"""Synthetic-only independent R2004 page tests, no private drawing material."""
from struct import pack_into
import pytest

from tools.p8p2_r2004_fdl_page_oracle import (
    R2004Page, UnsupportedPage, inspect_filedeplist_tv, scan_r2004_pages,
)


def _fixture(strings, logical_size=96, section_type=11):
    payload = bytearray(logical_size)
    pack_into('<I', payload, 0, len(strings))
    bits = []
    for length, mode in strings:
        bits.extend([(mode >> 1) & 1, mode & 1])
        if mode == 0:
            for value in [length & 255, length >> 8]:
                bits.extend((value >> (7 - i)) & 1 for i in range(8))
        elif mode == 1:
            bits.extend((length >> (7 - i)) & 1 for i in range(8))
        if length <= 10:
            bits.extend([0] * (length * 8))
    for j, value in enumerate(bits):
        cursor = 32 + j
        if cursor >= logical_size * 8:
            break
        payload[cursor // 8] |= value << (7 - cursor % 8)
    address = 256
    data = bytearray(address + 32 + logical_size + 100)
    data[:6] = b'AC1018'
    vals = (0x4163043B, section_type, logical_size,
            logical_size + 32, 0, 0, 0, 0)
    mask = 0x4164536B ^ address
    for i, value in enumerate(vals):
        pack_into('<I', data, address + 4 * i, value ^ mask)
    data[address + 32:address + 32 + logical_size] = payload
    return bytes(data)


def test_locate_raw_page_without_libredwg():
    data = _fixture([(4, 1), (0, 2)])
    pages = scan_r2004_pages(data)
    assert pages == [R2004Page(256, 11, 96, 128, 0)]
    result = inspect_filedeplist_tv(data, 96)
    assert result['declared_feature_count'] == 2
    assert result['feature_bounds_valid'] is True
    assert result['financial_quantity_approved'] is False
    assert result['section_map_descriptor_independently_decoded'] is False


def test_bogus_third_string_is_rejected_without_payload_read():
    result = inspect_filedeplist_tv(_fixture([(2, 1), (0, 2), (600, 0)]), 96)
    assert result['declared_feature_count'] == 3
    assert result['inspected_feature_prefixes'][-1]['declared_bytes'] == 600
    assert result['inspected_feature_prefixes'][-1]['payload_valid'] is False
    assert result['feature_bounds_valid'] is False


def test_wrong_section_size_version_and_truncated_page_fail_closed():
    with pytest.raises(UnsupportedPage):
        inspect_filedeplist_tv(_fixture([(2, 1)], section_type=12), 96)
    with pytest.raises(UnsupportedPage):
        inspect_filedeplist_tv(_fixture([(2, 1)]), 120)
    with pytest.raises(UnsupportedPage):
        scan_r2004_pages(b'AC1021' + b'\x00' * 300)
    with pytest.raises(UnsupportedPage):
        inspect_filedeplist_tv(_fixture([(2, 1)])[:-105], 96)


def test_output_has_no_cad_strings_coordinates_handles_or_addresses():
    result = inspect_filedeplist_tv(_fixture([(3, 1)]), 96)
    for forbidden in ('strings', 'coordinates', 'handles', 'page_address'):
        assert forbidden not in result
