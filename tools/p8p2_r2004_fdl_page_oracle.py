"""Independent read-only R2004 FileDepList raw-page and TV prefix auditor.

Inputs MUST remain private. No writes, uploads, CAD text, source hashes or handles.
Only a single uncompressed FileDepList page is supported. The supplied logical
section length still needs separate section-map validation; finding the physical
page by raw header XOR does not establish the logical map's correctness.
"""
from __future__ import annotations

from dataclasses import dataclass
from struct import unpack_from

_MAGIC = 0x4163043B
_XOR_SEED = 0x4164536B
_FILEDEPLIST_TYPE = 11
_MAX_DWG = 50 * 1024 * 1024


@dataclass(frozen=True)
class R2004Page:
    address: int
    section_type: int
    data_size: int
    page_size: int
    page_offset: int


class UnsupportedPage(ValueError):
    """Fail closed on ambiguous, unsupported or truncated source geometry."""


def scan_r2004_pages(file_bytes: bytes) -> list[R2004Page]:
    """Find XOR-masked page headers from original bytes, without LibreDWG."""
    if not isinstance(file_bytes, bytes) or file_bytes[:6] != b'AC1018':
        raise UnsupportedPage('R2004 AC1018 bytes required')
    if not (192 <= len(file_bytes) <= _MAX_DWG):
        raise UnsupportedPage('DWG exceeds bounded size limits')
    candidates: list[R2004Page] = []
    target = _MAGIC ^ _XOR_SEED
    for address in range(128, len(file_bytes) - 32):
        if unpack_from('<I', file_bytes, address)[0] ^ address != target:
            continue
        mask = _XOR_SEED ^ address
        fields = tuple(unpack_from('<I', file_bytes, address + j * 4)[0] ^ mask
                       for j in range(8))
        magic, section_type, data_size, page_size, page_offset = fields[:5]
        if (magic != _MAGIC
                or not (0 < data_size <= len(file_bytes) - address - 32)
                or not (data_size <= page_size <= _MAX_DWG)
                or page_offset > len(file_bytes)):
            continue
        candidates.append(R2004Page(address, section_type, data_size,
                                    page_size, page_offset))
        if len(candidates) > 2048:
            raise UnsupportedPage('Ambiguous excessive page header count')
    return candidates


def inspect_filedeplist_tv(file_bytes: bytes, logical_section_size: int) -> dict:
    """Decode only prefix lengths, NEVER any actual feature string bytes."""
    pages = [p for p in scan_r2004_pages(file_bytes)
             if p.section_type == _FILEDEPLIST_TYPE]
    if len(pages) != 1:
        raise UnsupportedPage('Require exactly one FileDepList physical page')
    page = pages[0]
    if (page.page_offset != 0 or page.page_size != page.data_size + 32
            or not isinstance(logical_section_size, int)
            or not (4 <= logical_section_size <= page.data_size)):
        raise UnsupportedPage('Unsupported page or logical section geometry')
    raw = file_bytes[page.address + 32:page.address + 32 + page.data_size]
    logical = raw[:logical_section_size]
    num_features = unpack_from('<I', logical, 0)[0]
    if num_features > 4096:
        raise UnsupportedPage('Feature count exceeds safe limit')
    bit_pos = 32

    def bits(n: int) -> int:
        nonlocal bit_pos
        if n < 0 or bit_pos + n > len(logical) * 8:
            raise EOFError('TV bit prefix out of range')
        value = 0
        for offset in range(bit_pos, bit_pos + n):
            value = (value << 1) | (
                (logical[offset // 8] >> (7 - offset % 8)) & 1)
        bit_pos += n
        return value

    prefixes = []
    for index in range(num_features):
        try:
            mode = bits(2)
            if mode == 0:
                declared_bytes = bits(8) | (bits(8) << 8)
            elif mode == 1:
                declared_bytes = bits(8)
            elif mode == 2:
                declared_bytes = 0
            else:
                declared_bytes = 256
        except EOFError:
            prefixes.append({'index': index + 1, 'prefix_valid': False,
                             'payload_valid': False})
            break
        available = (len(logical) * 8 - bit_pos) // 8
        valid = declared_bytes <= available
        prefixes.append({
            'index': index + 1, 'prefix_valid': True, 'length_mode': mode,
            'declared_bytes': declared_bytes, 'remaining_bytes': available,
            'payload_valid': valid,
        })
        if not valid:
            break
        bit_pos += declared_bytes * 8

    return {
        'read_only': True,
        'source_format': 'AC1018',
        'section_page_type': page.section_type,
        'physical_payload_bytes': page.data_size,
        'page_bytes_including_header': page.page_size,
        'section_map_logical_bytes': logical_section_size,
        'declared_feature_count': num_features,
        'inspected_feature_prefixes': prefixes,
        'feature_bounds_valid': len(prefixes) == num_features and all(
            p['payload_valid'] for p in prefixes),
        'section_map_descriptor_independently_decoded': False,
        'financial_quantity_approved': False,
    }
