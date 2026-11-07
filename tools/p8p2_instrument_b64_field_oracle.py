"""Source-only, fail-closed LibreDWG FileDepList + object decoder diagnostic.

Requires the exact pinned *public* a835758 LibreDWG source checkout.
Never ingests CAD, private hashes, handles, coordinates or payloads.
No decoder change is production-authorized.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from tools.p8p2_instrument_b64_stage import (
    UPSTREAM, instrument_pinned_decoder, patch_100k_guard,
)

_FDL_FIELDS = (
    ("FIELD_RL (num_features, 0);", "num_features"),
    ("FIELD_VECTOR_T (features, TU32, num_features, 0);", "features"),
    ("FIELD_RL (num_files, 0);", "num_files"),
    ("FIELD_T32 (files[rcount1].filename, 0);", "filename"),
    ("FIELD_T32 (files[rcount1].filepath, 0);", "filepath"),
    ("FIELD_T32 (files[rcount1].fingerprint, 0);", "fingerprint"),
    ("FIELD_T32 (files[rcount1].version, 0);", "version"),
    ("FIELD_RL (files[rcount1].feature_index, 0);", "feature_index"),
    ("FIELD_RL (files[rcount1].timestamp, 0);", "timestamp"),
    ("FIELD_RL (files[rcount1].filesize, 0);", "filesize"),
    ("FIELD_RS (files[rcount1].affects_graphics, 0);", "affects_graphics"),
    ("FIELD_RL (files[rcount1].refcount, 0);", "refcount"),
)

_FDL_HELPERS = r"""
/* Public field labels only. The last attempted field is NOT proof of corruption. */
static const char *sp_p8p2_fdl_entered = "none";
static const char *sp_p8p2_fdl_completed = "none";
static void sp_p8p2_fdl_enter (const char *n) { sp_p8p2_fdl_entered = n; }
static void sp_p8p2_fdl_complete (const char *n) { sp_p8p2_fdl_completed = n; }
static int sp_p8p2_b64_decoded (const char *decoder, int result)
{
  if (result & DWG_ERR_VALUEOUTOFBOUNDS)
    fprintf (stderr, "SP_P8P2_B64_DECODER=%s\n", decoder);
  return result;
}
"""

def instrument_fdl_spec(text: str) -> str:
    """Instrument known C macro calls without altering their results."""
    result = text
    if "sp_p8p2_fdl_enter" in text:
        raise ValueError("FileDepList already instrumented")
    for original, field in _FDL_FIELDS:
        if result.count(original) != 1:
            raise ValueError("Pinned FileDepList field missing or repeated: " + field)
        # No values, file names, feature data, counts or paths are logged.
        result = result.replace(
            original,
            '#ifdef SP_P8P2_FDL_2004_ONLY\n'
            '    sp_p8p2_fdl_enter ("' + field + '");\n'
            '#endif\n'
            + original +
            '\n#ifdef SP_P8P2_FDL_2004_ONLY\n'
            '    sp_p8p2_fdl_complete ("' + field + '");\n'
            '#endif',
            1,
        )
    return result

def instrument_decoder(text: str) -> tuple[str, int]:
    """Use prior stage probe, then locate nested per-object decoder returns."""
    result = instrument_pinned_decoder(text)
    anchor = "static int\nfiledeplist_private (Bit_Chain *restrict dat, Dwg_Data *restrict dwg)"
    if result.count(anchor) != 1:
        raise ValueError("Pinned filedeplist_private anchor changed")
    result = result.replace(anchor, _FDL_HELPERS + "\n" + anchor, 1)
    # The shared spec is ALSO included by decode_r2007.c. Only R2004 may
    # call these local helpers; 2007 must compile with marker code excluded.
    spec_include = '  #include "filedeplist.spec"'
    if result.count(spec_include) != 1:
        raise ValueError("Pinned FileDepList include scope changed")
    result = result.replace(
        spec_include,
        '  #define SP_P8P2_FDL_2004_ONLY 1\n'
        + spec_include
        + '\n  #undef SP_P8P2_FDL_2004_ONLY',
        1,
    )

    old = "  error = filedeplist_private (dat, dwg);"
    if result.count(old) != 1:
        raise ValueError("Pinned FileDepList read call changed")
    new = (
        old + "\n"
        '  if (error & DWG_ERR_VALUEOUTOFBOUNDS)\n'
        '    fprintf (stderr, "SP_P8P2_B64_FDL_LAST=%s|%s\\n",\n'
        '             sp_p8p2_fdl_entered, sp_p8p2_fdl_completed);'
    )
    result = result.replace(old, new, 1)

    begin = result.index("int\ndwg_decode_add_object (")
    end = result.index("\n/** dwg_decode_unknown", begin)
    region = result[begin:end]
    pattern = re.compile(
        r'error = (dwg_decode_([A-Za-z0-9_]+) \(dat, obj\));'
    )
    region, replaced = pattern.subn(
        lambda m: 'error = sp_p8p2_b64_decoded ("' + m.group(2) +
                  '", ' + m.group(1) + ');', region
    )
    if replaced < 60 or replaced > 150:
        raise ValueError("Unexpected pinned decoder call count")
    # Custom MAP/AEC and UNKNOWN object paths are not silently excluded.
    custom = "dwg_decode_variable_type (dwg, dat, hdl_dat, obj)"
    if region.count(custom) != 1:
        raise ValueError("Pinned custom class decoder call changed")
    region = region.replace(
        custom,
        'sp_p8p2_b64_decoded ("variable_type", ' + custom + ')', 1,
    )
    for name in ("UNKNOWN_OBJ", "UNKNOWN_ENT"):
        original = "error |= dwg_decode_" + name + " (dat, obj);"
        if region.count(original) != 1:
            raise ValueError("Pinned UNKNOWN class call changed: " + name)
        region = region.replace(
            original, 'error |= sp_p8p2_b64_decoded ("' + name +
            '", dwg_decode_' + name + ' (dat, obj));', 1,
        )
    result = result[:begin] + region + result[end:]
    return result, replaced

def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("usage: p8p2_instrument_b64_field_oracle.py /abs/pinned/public/libredwg")
    root = Path(argv[1]).resolve(strict=True)
    actual = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != UPSTREAM:
        raise SystemExit("Pinned upstream Git identity mismatch")
    dec = root / "src/decode.c"
    spec = root / "src/dwg2.spec"
    fdl = root / "src/filedeplist.spec"
    new_dec, wrapped = instrument_decoder(dec.read_text(encoding="utf-8"))
    new_spec = patch_100k_guard(spec.read_text(encoding="utf-8"))
    new_fdl = instrument_fdl_spec(fdl.read_text(encoding="utf-8"))
    dec.write_text(new_dec, encoding="utf-8")
    spec.write_text(new_spec, encoding="utf-8")
    fdl.write_text(new_fdl, encoding="utf-8")
    changed = subprocess.check_output(
        ["git", "-C", str(root), "diff", "--name-only"], text=True
    ).splitlines()
    if sorted(changed) != ["src/decode.c", "src/dwg2.spec", "src/filedeplist.spec"]:
        raise SystemExit("Unexpected instrumented public source paths")
    subprocess.run(["git", "-C", str(root), "diff", "--check"], check=True)
    print("PINNED_B64_FDL_AND_OBJECT_PUBLIC_ORACLE_READY; wrapped=" + str(wrapped))

if __name__ == "__main__":
    main(sys.argv)
