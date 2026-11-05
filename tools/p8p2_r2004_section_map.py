"""Bounded, read-only AC1018 map verification. Receipts MUST remain private.

Format basis: ODA DWG specification sections 4.1--4.7 and 17; independently
implemented here, without calling LibreDWG. Only single-page, uncompressed
FileDepList is supported. Encrypted, sparse and multi-page targets fail closed.
The descriptor's flag 2 means unknown, not password encryption; file security
and page checksums are checked separately. No CAD strings are returned.
"""
from __future__ import annotations

from struct import pack, unpack_from
from zlib import crc32

from tools.p8p2_r2004_fdl_page_oracle import UnsupportedPage

LIMIT = 50 * 1024 * 1024
MAP_LIMIT = 2 * 1024 * 1024


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise UnsupportedPage(reason)


def checksum(data: bytes, seed: int = 0) -> int:
    a, b = seed & 65535, seed >> 16
    for start in range(0, len(data), 5552):
        for value in data[start:start + 5552]:
            a += value
            b += a
        a %= 65521
        b %= 65521
    return (b << 16) | a


def decompress_map(data: bytes, expected: int) -> bytes:
    """Strict bounded R2004 LZ77; no zero-fill or truncated-stream recovery."""
    require(0 < expected <= MAP_LIMIT, 'Unsupported decompressed map size')
    out = bytearray()
    pos = 0

    def byte() -> int:
        nonlocal pos
        require(pos < len(data), 'Truncated compressed map')
        result = data[pos]
        pos += 1
        return result

    def extended(value: int, mask: int) -> int:
        n = value & mask
        if n == 0:
            n = mask
            v = byte()
            while v == 0:
                n += 255
                require(n <= expected, 'Oversized compressed run')
                v = byte()
            n += v
        return n

    def literal(n: int) -> int:
        nonlocal pos
        require(pos + n <= len(data) and len(out) + n <= expected,
                'Literal crosses map boundary')
        out.extend(data[pos:pos + n])
        pos += n
        return byte()

    op = byte()
    if op > 0x11:
        op = literal(op - 17)
    if op < 0x10:
        op = literal(extended(op, 15) + 3)
    while op != 0x11:
        require(op >= 0x10, 'Unsupported LZ opcode')
        if op >= 0x40:
            count = (op >> 4) - 1
            offset = ((op >> 2) & 3) + (byte() << 2) + 1
        else:
            count = extended(op, 7 if op < 0x20 else 31) + 2
            base = ((op & 8) << 11) + 0x4000 if op < 0x20 else 1
            op = byte()
            offset = base + (op >> 2) + (byte() << 6)
        require(0 < offset <= len(out) and len(out) + count <= expected,
                'Invalid map back-reference')
        for _ in range(count):
            out.append(out[-offset])
        n = op & 3
        if n == 0:
            op = byte()
            if op < 0x10:
                n = extended(op, 15) + 3
        if n:
            op = literal(n)
    # The format's LZ terminator may include the two zero offset bytes.
    require(data[pos:] in (b'', b'\0\0'), 'Unexpected compressed map tail')
    require(len(out) == expected, 'Decompressed map length mismatch')
    return bytes(out)


def _system_page(data: bytes, address: int, magic: int) -> tuple[bytes, dict]:
    require(address >= 256 and address % 32 == 0 and address + 20 <= len(data),
            'Invalid system page address')
    kind, size, stored, compression, crc = unpack_from('<5I', data, address)
    require(kind == magic and compression == 2, 'Unsupported system page')
    require(0 < stored <= MAP_LIMIT and address + 20 + stored <= len(data),
            'System page crosses source boundary')
    body = data[address + 20:address + 20 + stored]
    header = data[address:address + 16] + bytes(4)
    require(checksum(body, checksum(header)) == crc, 'System checksum mismatch')
    raw = decompress_map(body, size)
    return raw, {'address': address, 'stored_size': stored,
                 'decompressed_size': size, 'checksum_verified': True}


def verify_filedeplist_descriptor(data: bytes) -> dict:
    """Derive the target bounds from checksum-verified original maps only.

    Returned addresses/IDs/sizes are source metadata and MUST remain private.
    This verifies container bounds, not engineering validity or file ownership.
    """
    require(isinstance(data, bytes) and 256 <= len(data) <= LIMIT
            and data[:6] == b'AC1018', 'Bounded AC1018 source required')
    require(unpack_from('<I', data, 0x18)[0] == 0, 'Unsupported security flags')
    state, header = 1, bytearray()
    for b in data[0x80:0xEC]:
        state = (state * 0x343FD + 0x269EC3) & 0xFFFFFFFF
        header.append(b ^ ((state >> 16) & 255))
    require(header[:12] == b'AcFssFcAJMB\0', 'Invalid decrypted file header')
    require(unpack_from('<I', header, 0x10)[0] == 108, 'Unsupported header size')
    expected_crc = unpack_from('<I', header, 0x68)[0]
    header[0x68:0x6C] = bytes(4)
    require(crc32(header) == expected_crc, 'File header CRC mismatch')
    map_id = unpack_from('<I', header, 0x50)[0]
    map_address = unpack_from('<Q', header, 0x54)[0] + 256
    info_id = unpack_from('<I', header, 0x5C)[0]
    raw, map_receipt = _system_page(data, map_address, 0x41630E3B)
    pos, address, pages = 0, 256, {}
    while pos < len(raw):
        require(pos + 8 <= len(raw), 'Truncated global page record')
        number, size = unpack_from('<iI', raw, pos)
        pos += 8
        require(number != 0 and number not in pages and size > 0,
                'Invalid or duplicate global page record')
        require(address + size <= len(data), 'Global page exceeds source')
        pages[number] = {'address': address, 'size': size}
        address += size
        if number < 0:
            require(pos + 16 <= len(raw), 'Truncated gap record')
            pos += 16
    require(map_id in pages and pages[map_id]['address'] == map_address,
            'Global map self-reference mismatch')
    require(info_id in pages, 'Missing data section map')
    require(20 + map_receipt['stored_size'] <= pages[map_id]['size'],
            'Global map overlaps next page')
    raw, info_receipt = _system_page(data, pages[info_id]['address'], 0x4163003B)
    require(20 + info_receipt['stored_size'] <= pages[info_id]['size'],
            'Data section map overlaps next page')
    require(len(raw) >= 20, 'Truncated data map')
    count, compression, maximum, encrypted, count2 = unpack_from('<5I', raw)
    require(0 < count <= 256 and compression == 2 and encrypted == 0,
            'Unsupported data map header')
    pos, matches, ids, names = 20, [], set(), set()
    for _ in range(count):
        require(pos + 96 <= len(raw), 'Truncated section descriptor')
        size, n, maximum, unknown, compressed, kind, encrypted = unpack_from('<Q6I', raw, pos)
        name = raw[pos + 32:pos + 96].split(b'\0', 1)[0]
        require(kind not in ids and name not in names, 'Duplicate section descriptor')
        ids.add(kind)
        names.add(name)
        pos += 96
        require(n <= 8192 and pos + 16 * n <= len(raw), 'Truncated local page map')
        refs = [unpack_from('<iIQ', raw, pos + 16 * j) for j in range(n)]
        pos += 16 * n
        if name == b'AcDb:FileDepList':
            matches.append((size, maximum, compressed, kind, encrypted, refs))
    require(pos == len(raw) and len(matches) == 1, 'Ambiguous or trailing data map')
    size, maximum, compressed, kind, encrypted, refs = matches[0]
    require(compressed == 1 and encrypted in (0, 2), 'Unsupported target encoding')
    require(len(refs) == 1, 'Multi-page FileDepList unsupported')
    number, stored, offset = refs[0]
    require(number in pages and number > 0 and offset == 0,
            'Missing or sparse FileDepList page')
    page = pages[number]
    address = page['address']
    require(page['size'] >= 32 and address % 32 == 0, 'Invalid target page boundary')
    fields = tuple(v ^ (0x4164536B ^ address)
                   for v in unpack_from('<8I', data, address))
    magic, page_kind, data_size, page_size, offset_low, offset_high, header_crc, data_crc = fields
    page_offset = offset_low | (offset_high << 32)
    require(magic == 0x4163043B and kind == page_kind, 'Target page type mismatch')
    require(0 < size <= maximum == stored == data_size and offset == page_offset
            and data_size + 32 == page_size == page['size'], 'Target size mismatch')
    body = data[address + 32:address + 32 + stored]
    require(checksum(body) == data_crc, 'Target data checksum mismatch')
    check_header = pack('<8I', *fields[:6], 0, data_crc)
    require(checksum(check_header, data_crc) == header_crc, 'Target header checksum mismatch')
    return {'descriptor_verified': True, 'header_crc_verified': True,
            'global_map': map_receipt, 'data_map': info_receipt,
            'global_page_count': len(pages), 'descriptor_count': count,
            'section_type': kind, 'logical_size': size, 'max_page_payload': maximum,
            'compressed': compressed, 'encrypted_flag': encrypted,
            'file_security_flags': 0, 'physical_page_number': number,
            'physical_address': address, 'page_offset': offset,
            'page_size': page_size, 'stored_payload_size': stored,
            'page_checksums_verified': True, 'financial_quantity_approved': False}


def inspect_filedeplist_string32(data: bytes) -> dict:
    """ODA R2004 String32 fields; metadata only, no decoded string output."""
    descriptor = verify_filedeplist_descriptor(data)
    start = descriptor['physical_address'] + 32
    raw = data[start:start + descriptor['logical_size']]
    pos, lengths = 0, []

    def integer(n: int = 4) -> int:
        nonlocal pos
        require(pos + n <= len(raw), 'Truncated FileDepList scalar')
        v = int.from_bytes(raw[pos:pos + n], 'little')
        pos += n
        return v

    def string(field: str) -> None:
        nonlocal pos
        offset = pos
        size = integer()
        require(size <= len(raw) - pos, 'String32 payload crosses logical section')
        lengths.append({'field': field, 'prefix_byte_offset': offset, 'length': size})
        pos += size

    features = integer()
    require(features <= 4096 and features <= (len(raw) - pos) // 4,
            'Invalid FileDepList feature count')
    for _ in range(features):
        string('feature')
    files = integer()
    require(files <= 4096 and files <= (len(raw) - pos) // 34,
            'Invalid FileDepList file count')
    for _ in range(files):
        for field in ('filename', 'filepath', 'fingerprint', 'version'):
            string(field)
        require(integer() < features, 'Invalid FileDepList feature index')
        integer()  # timestamp
        integer()  # filesize
        require(integer(2) in (0, 1), 'Invalid affects_graphics flag')
        integer()  # refcount
    require(pos == len(raw), 'Unconsumed FileDepList logical bytes')
    return {'descriptor': descriptor, 'format': 'R2004_String32',
            'feature_count': features, 'file_count': files, 'prefixes': lengths,
            'consumed_bytes': pos, 'full_payload_bounds_valid': True,
            'financial_quantity_approved': False}
