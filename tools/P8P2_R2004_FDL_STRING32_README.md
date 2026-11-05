# R2004 FileDepList diagnostic correction

The pinned GNU decoder uses `FIELD_VECTOR_T(features, TU32, ...)`, whose
pre-R2007 branch calls `bit_read_TV`. R2004 FileDepList feature names instead
use a little-endian 32-bit byte length. This changes the very first prefix
interpretation and therefore every subsequent cursor position.

Format reference: [ODA DWG specification](https://www.opendesign.com/files/guestdownloads/OpenDesign_Specification_for_.dwg_files.pdf),
sections 4.1–4.7 (container maps and checksums) and 17 (FileDepList String32).

`p8p2_r2004_section_map.verify_filedeplist_descriptor(bytes)` independently
reads the original encrypted file header, verifies CRC, decompresses both
system maps with strict bounds, validates their checksums and self-reference,
locates the named descriptor and checks its single uncompressed page against
the global/local maps and both page checksums. Logical length is taken only
from that verified descriptor. Multi-page, sparse, encrypted/security-enabled,
malformed and unsupported target layouts fail closed. Flag 2 is the format's
documented *unknown* marker; it is not treated as a password-encryption flag.

`inspect_filedeplist_string32(bytes)` then checks all feature/file prefixes,
scalars, feature references and exact logical-stream consumption. It returns
metadata, never feature or filename strings. Returned addresses, sizes and
IDs are still private source metadata: keep the entire receipt outside GitHub.
CRC validity is a corruption check, not authentication of the drawing's origin.

The older `inspect_filedeplist_tv` intentionally reproduces the legacy buggy
interpretation for comparison; its bounds flag is not format acceptance.

`python -m tools.p8p2_patch_r2004_fdl_string32 /path/to/public/upstream`
applies a decode-only AC1018 correction to GNU commit
`a83575825b86528bf1997484852b2a9f5cdbbac0`. It requires the exact original
FileDepList source, retains count/prefix/payload bounds and NULL failures,
and does not alter generic TV, other versions, SORTENTSTABLE caps or native
error accumulation. This remains a nonproduction diagnostic build.

Tests use generated synthetic containers and native in-memory payloads only.
The native test entry point is added only to the isolated CI build; no binary
is packaged or released. Private A/B evidence is deliberately excluded.
Neither a parser PASS nor a reduced native error mask grants financial,
geometry, unit, SHX or proprietary MAP/AEC acceptance. PR remains Draft.
