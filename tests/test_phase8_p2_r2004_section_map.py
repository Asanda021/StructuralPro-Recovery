"""Synthetic AC1018 containers only; no source-derived fixtures or values."""
from struct import pack, pack_into, unpack_from
from zlib import crc32

import pytest

from tools.p8p2_r2004_fdl_page_oracle import UnsupportedPage, inspect_filedeplist_tv
from tools.p8p2_r2004_section_map import (
    checksum, decompress_map, inspect_filedeplist_string32,
    verify_filedeplist_descriptor,
)


def literal_stream(raw):
    assert len(raw) >= 4
    if len(raw) <= 18:
        prefix = bytes([len(raw) - 3])
    else:
        n = len(raw) - 18
        prefix = b'\0'
        while n > 255:
            prefix += b'\0'
            n -= 255
        prefix += bytes([n])
    return prefix + raw + b'\x11\0\0'


def system(raw, magic):
    body = literal_stream(raw)
    head = pack('<5I', magic, len(raw), len(body), 2, 0)
    return head[:16] + pack('<I', checksum(body, checksum(head))) + body


def text32(data):
    return pack('<I', len(data)) + data


def payload():
    # One file, two feature strings, all scalars and an empty path/GUID.
    return (pack('<I', 2) + text32(b'alpha') + text32(b'beta') + pack('<I', 1)
            + text32(b'file.bin') + text32(b'') * 3 + pack('<IIIHI', 1, 0, 8, 1, 2))


def fixture(*, raw=None, logical=None, n=1, compressed=1, encrypted=2,
            kind=11, offset=0, page_offset=0, stored=128, max_size=128,
            duplicate=False, security=0):
    raw = payload() if raw is None else raw
    logical = len(raw) if logical is None else logical
    out = bytearray(1184)
    out[:6] = b'AC1018'
    pack_into('<I', out, 0x18, security)
    body = raw.ljust(128, b'\0')
    assert len(body) == 128
    dcrc = checksum(body)
    fields = [0x4163043B, kind, stored, 160, page_offset & 0xFFFFFFFF,
              page_offset >> 32, 0, dcrc]
    fields[6] = checksum(pack('<8I', *fields), dcrc)
    out[256:288] = pack('<8I', *(v ^ (0x4164536B ^ 256) for v in fields))
    out[288:416] = body
    desc = pack('<Q6I', logical, n, max_size, 0, compressed, kind, encrypted)
    desc += b'AcDb:FileDepList'.ljust(64, b'\0')
    desc += b''.join(pack('<iIQ', 1, stored, offset) for _ in range(n))
    count = 2 if duplicate else 1
    info = pack('<5I', count, 2, 0x7400, 0, count) + desc * count
    encoded = system(info, 0x4163003B)
    out[416:416 + len(encoded)] = encoded
    records = pack('<iIiIiI', 1, 160, 2, 512, 3, 256)
    encoded = system(records, 0x41630E3B)
    out[928:928 + len(encoded)] = encoded
    header = bytearray(108)
    header[:12] = b'AcFssFcAJMB\0'
    pack_into('<I', header, 0x10, 108)
    pack_into('<I', header, 0x50, 3)
    pack_into('<Q', header, 0x54, 928 - 256)
    pack_into('<I', header, 0x5C, 2)
    pack_into('<I', header, 0x68, crc32(header))
    state = 1
    for i, value in enumerate(header):
        state = (state * 0x343FD + 0x269EC3) & 0xFFFFFFFF
        out[128 + i] = value ^ ((state >> 16) & 255)
    return bytes(out)


def test_complete_map_and_string32_payload():
    data = fixture()
    result = inspect_filedeplist_string32(data)
    assert result['full_payload_bounds_valid']
    assert result['consumed_bytes'] == len(payload())
    assert result['descriptor']['logical_size'] == len(payload())
    assert result['descriptor']['page_checksums_verified']
    assert result['financial_quantity_approved'] is False
    assert [p['length'] for p in result['prefixes']] == [5, 4, 8, 0, 0, 0]
    tv = inspect_filedeplist_tv(data, len(payload()))
    assert [p.get('declared_bytes') for p in tv['inspected_feature_prefixes']] != [5, 4]


def test_target_id_comes_from_named_descriptor_not_constant():
    assert verify_filedeplist_descriptor(fixture(kind=7))['section_type'] == 7


@pytest.mark.parametrize('options', [
    {'n': 2}, {'n': 0}, {'compressed': 2}, {'encrypted': 1},
    {'encrypted': 3}, {'security': 1}, {'offset': 128},
    {'page_offset': 1 << 32}, {'logical': 129}, {'logical': 0},
    {'stored': 127}, {'max_size': 256}, {'duplicate': True},
])
def test_unsupported_or_inconsistent_maps_fail_closed(options):
    with pytest.raises(UnsupportedPage):
        verify_filedeplist_descriptor(fixture(**options))


@pytest.mark.parametrize('offset', [0, 128, 296, 280, 432, 960])
def test_checksums_and_version_detect_corruption(offset):
    data = bytearray(fixture())
    data[offset] ^= 1
    with pytest.raises(UnsupportedPage):
        verify_filedeplist_descriptor(bytes(data))


@pytest.mark.parametrize('length', [0, 128, 280, 1000, 1183])
def test_truncated_source_fails_closed(length):
    with pytest.raises(UnsupportedPage):
        verify_filedeplist_descriptor(fixture()[:length])


@pytest.mark.parametrize('raw', [
    pack('<I', 0xFFFFFFFF),
    pack('<II', 1, 0xFFFFFFFF),
    pack('<I', 1) + b'\0\0\0',
    pack('<II', 0, 0xFFFFFFFF),
    payload() + b'\0',
    payload()[:-1],
])
def test_string32_negative_bounds_without_padding_or_truncation(raw):
    with pytest.raises(UnsupportedPage):
        inspect_filedeplist_string32(fixture(raw=raw))


def test_exact_end_empty_and_large_strings():
    for strings in ([], [b''], [b'a' * 100]):
        raw = pack('<I', len(strings)) + b''.join(text32(s) for s in strings) + pack('<I', 0)
        assert inspect_filedeplist_string32(fixture(raw=raw))['consumed_bytes'] == len(raw)


def test_invalid_feature_index_and_graphics_flag():
    for offset, fmt, value in [(-18, '<I', 2), (-6, '<H', 3)]:
        raw = bytearray(payload())
        pack_into(fmt, raw, len(raw) + offset, value)
        with pytest.raises(UnsupportedPage):
            inspect_filedeplist_string32(fixture(raw=raw))


def test_lz_overlap_and_exact_boundary():
    # ABCD followed by a six-byte overlapping backreference, then terminator.
    assert decompress_map(b'\x01ABCD\x70\x00\x11\0\0', 10) == b'ABCDDDDDDD'
    assert decompress_map(literal_stream(b'x' * 600), 600) == b'x' * 600
    assert decompress_map(b'\x01ABCD\x21\0\0\x11\0\0', 7) == b'ABCDDDD'
    assert decompress_map(b'\x01ABCD\x20\x01\0\0\x11\0\0', 38) == b'ABCD' + b'D' * 34
    initial = bytes(range(256)) * 64
    stream = literal_stream(initial)[:-3] + b'\x12\0\0\x11\0\0'
    assert decompress_map(stream, len(initial) + 4) == initial + initial[:4]


@pytest.mark.parametrize('data,size', [
    (b'', 4), (b'\x01AB', 4), (b'\x01ABCD\x70\xFF\x11', 10),
    (b'\x01ABCD\x70\0\x11', 9), (b'\x01ABCD\x11bad', 4),
    (b'\x01ABCD\x11', 5), (b'\x01ABCD\x11', 3),
    (b'\0\0\0\0', 10),
])
def test_bad_compressed_maps(data, size):
    with pytest.raises(UnsupportedPage):
        decompress_map(data, size)


def test_receipt_does_not_contain_cad_strings():
    import json
    result = json.dumps(inspect_filedeplist_string32(fixture()))
    assert all(value not in result for value in ('alpha', 'beta', 'file.bin'))
