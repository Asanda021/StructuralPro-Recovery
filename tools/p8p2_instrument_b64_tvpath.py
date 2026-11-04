"""Exact upstream-only, public-source P8/P2 FileDepList TV vs bounds diagnostic.

Never accepts or uploads a drawing. NO PRODUCTION DECODER OR FINANCIAL APPROVAL.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.p8p2_instrument_b64_field_oracle import (
    UPSTREAM, instrument_decoder, instrument_fdl_spec, patch_100k_guard,
)

_EXTRA_HELPERS = r"""
/* R2004-only / public callsite names. No data, strings, handles, counts. */
static unsigned sp_p8p2_tv_calls = 0, sp_p8p2_tv_nulls = 0;
static BITCODE_TV
sp_p8p2_fdl_tv_read (Bit_Chain *dat)
{
  BITCODE_TV v;
  /* Read the bitshort *header on a cloned cursor*. Never consume original
   * stream twice or retain any length, bytes, coordinates or file paths. */
  const char *cause = "ALLOC_OR_OTHER";
  if (dat->bit > 7 || dat->byte >= dat->size)
    cause = "HEADER_BOUNDS";
  else
    {
      size_t available = (dat->size - dat->byte) * 8 - dat->bit;
      if (available < 8) /* exact first CHK_OVERFLOW_PLUS(1) guard */
        cause = "HEADER_BOUNDS";
      else
        {
          Bit_Chain preview_mode = *dat;
          unsigned mode = bit_read_BB (&preview_mode);
          size_t suffix_bits = mode == 0 ? 16 : (mode == 1 ? 8 : 0);
          if (available < (2 + suffix_bits))
            cause = "PREFIX_BOUNDS";
          else
            {
              Bit_Chain preview = *dat;
              unsigned length = bit_read_BS (&preview);
              if (preview.bit > 7 || preview.byte > preview.size)
                cause = "PREFIX_BOUNDS";
              else
                {
                  size_t payload_available
                    = (preview.size - preview.byte) * 8 - preview.bit;
                  if ((size_t)length > payload_available / 8)
                    cause = "PAYLOAD_BOUNDS";
                }
            }
        }
    }
  v = bit_read_TV (dat); /* The unmodified GNU reader: exactly once. */
  if (sp_p8p2_tv_calls++ < 4)
    fprintf (stderr, "SP_P8P2_FDL_TV_CALLED\n");
  if (!v && sp_p8p2_tv_nulls++ < 16)
    {
      fprintf (stderr, "SP_P8P2_FDL_TV_NULL\n");
      fprintf (stderr, "SP_P8P2_FDL_TV_NULL_REASON=%s\n", cause);
    }
  return v;
}
static void
sp_p8p2_obj_site (const char *site)
{
  static unsigned count = 0;
  if (count++ < 16)
    fprintf (stderr, "SP_P8P2_B64_OBJECT_SITE=%s\n", site);
}
"""

def add_fdl_tv_diagnostic(spec: str) -> str:
    """Guard preflight + TV read wrapper strictly to original features macro."""
    target = "FIELD_VECTOR_T (features, TU32, num_features, 0);"
    if (spec.count(target) != 1 or "SP_P8P2_FDL_PREFLIGHT_REJECT" in spec
            or "sp_p8p2_fdl_tv_read" in spec):
        raise ValueError("Unexpected pinned feature-vector call")
    replacement = (
        "#ifdef SP_P8P2_FDL_2004_ONLY\n"
        "    /* Read-only preflight mirroring _VECTOR_CHKCOUNT for R2004. */\n"
        "    if (_obj->num_features > 0 &&\n"
        "        ((int64_t)_obj->num_features > AVAIL_BITS (dat) ||\n"
        "         (int64_t)_obj->num_features * 2 > AVAIL_BITS (dat)))\n"
        '      fprintf (stderr, "SP_P8P2_FDL_PREFLIGHT_REJECT\\n");\n'
        "    #define bit_read_TV(x) sp_p8p2_fdl_tv_read(x)\n"
        "#endif\n"
        + target +
        "\n#ifdef SP_P8P2_FDL_2004_ONLY\n"
        "    #undef bit_read_TV\n"
        "#endif"
    )
    return spec.replace(target, replacement, 1)

def add_object_site_probes(source: str) -> str:
    """Mark exact bounds return sites, preserve all native return values."""
    start = source.index("int\ndwg_decode_add_object (")
    end = source.index("\n/** dwg_decode_unknown", start)
    region = source[start:end]
    if 'SP_P8P2_B64_OBJECT_SITE' in region or 'sp_p8p2_obj_site (' in region:
        raise ValueError('Pinned object return sites missing or ambiguous: already instrumented')
    anchors = (
        ("return DWG_ERR_VALUEOUTOFBOUNDS;", "ms_stream_overflow"),
        ("return error;", "object_size_bounds"),
        ("return error | DWG_ERR_VALUEOUTOFBOUNDS;", "invalid_class_index"),
        ("return realloced ? -1 : error;", "final_accumulation"),
    )
    for original, label in anchors:
        if region.count(original) != 1:
            raise ValueError("Pinned return site missing or ambiguous: " + label)
        pre = (
            'sp_p8p2_obj_site ("' + label + '");\n'
            if label != "final_accumulation" else
            'if (error & DWG_ERR_VALUEOUTOFBOUNDS)\n'
            '    sp_p8p2_obj_site ("final_accumulation");\n'
        )
        region = region.replace(original, pre + "  " + original, 1)
    return source[:start] + region + source[end:]

def instrument_tvpath(source: str, spec: str) -> tuple[str, str, int]:
    decoder, wrapped = instrument_decoder(source)
    anchor = "static int\nfiledeplist_private ("
    if decoder.count(anchor) != 1:
        raise ValueError("FileDepList scope changed")
    decoder = decoder.replace(anchor, _EXTRA_HELPERS + "\n" + anchor, 1)
    return add_object_site_probes(decoder), add_fdl_tv_diagnostic(instrument_fdl_spec(spec)), wrapped

def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("usage: python -m tools.p8p2_instrument_b64_tvpath /abs/public/checkout")
    root = Path(argv[1]).resolve(strict=True)
    actual = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != UPSTREAM:
        raise SystemExit("Pinned upstream identity mismatch")
    dec, fdl, dwg2 = (root / "src" / name for name in ("decode.c", "filedeplist.spec", "dwg2.spec"))
    new_dec, new_fdl, wrapped = instrument_tvpath(
        dec.read_text(encoding="utf-8"), fdl.read_text(encoding="utf-8"),
    )
    new_dwg2 = patch_100k_guard(dwg2.read_text(encoding="utf-8"))
    dec.write_text(new_dec, encoding="utf-8")
    fdl.write_text(new_fdl, encoding="utf-8")
    dwg2.write_text(new_dwg2, encoding="utf-8")
    changed = subprocess.check_output(
        ["git", "-C", str(root), "diff", "--name-only"], text=True,
    ).splitlines()
    if sorted(changed) != ["src/decode.c", "src/dwg2.spec", "src/filedeplist.spec"]:
        raise SystemExit("Unexpected source modifications")
    subprocess.run(["git", "-C", str(root), "diff", "--check"], check=True)
    print("PINNED_B64_TVPATH_PUBLIC_DIAGNOSTIC_PATCHED; decoder_calls=" + str(wrapped))

if __name__ == "__main__":
    main(sys.argv)
