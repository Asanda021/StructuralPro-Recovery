"""Generate a public-source-only, *diagnostic* LibreDWG R2004 bounds-stage patch.

Never takes a private DWG, DXF, ledger, source hash, object handle or trace.
Only intended for pinned LibreDWG a83575825b86528bf1997484852b2a9f5cdbbac0.
The resulting decoder build is experimental, nonproduction and nonfinancial.
"""
from __future__ import annotations

import sys
from pathlib import Path

UPSTREAM = "a83575825b86528bf1997484852b2a9f5cdbbac0"
STAGES = (
    "decode_R2004_header", "read_R2004_section_map",
    "read_2004_section_header", "read_2004_section_summary",
    "read_2004_section_classes", "read_2004_section_handles",
    "read_2004_section_auxheader", "read_2004_section_preview",
    "read_2004_section_appinfo", "read_2004_section_appinfohistory",
    "read_2004_section_filedeplist", "read_2004_section_security",
    "read_2004_section_revhistory", "read_2004_section_objfreespace",
    "read_2004_section_template", "read_2004_section_vbaproject",
    "read_2004_section_acds",
)

_HELPER = r"""
/* P8P2 diagnostic only: stage identity without payload, handles or file offsets. */
static int
sp_p8p2_b64_stage (const char *stage, int returned)
{
  if (returned & DWG_ERR_VALUEOUTOFBOUNDS)
    fprintf (stderr, "SP_P8P2_B64_STAGE=%s\n", stage);
  return returned;
}
"""

def instrument_pinned_decoder(source: str) -> str:
    """Fail closed if source structure differs; add only bounded stderr probes."""
    if "SP_P8P2_B64_STAGE" in source:
        raise ValueError("Already instrumented source")
    label = "/* for 2004 and 2010+ */\nstatic int\ndecode_R2004"
    if source.count(label) != 1:
        raise ValueError("Pinned R2004 entrypoint anchor is missing or ambiguous")
    result = source.replace(label, _HELPER + "\n" + label, 1)
    for name in STAGES:
        before = f"error |= {name} (dat, dwg);"
        if result.count(before) != 1:
            raise ValueError(f"Pinned section callsite changed: {name}")
        after = (
            f'error |= sp_p8p2_b64_stage ("{name}", '
            f'{name} (dat, dwg));'
        )
        result = result.replace(before, after, 1)
    before = ("added = dwg_decode_add_object (dwg, &obj_dat, &obj_dat, last_offset);\n"
              "          if (added > 0)\n"
              "            error |= added;")
    if result.count(before) != 1:
        raise ValueError("Pinned object-add return callsite changed")
    after = (
        "added = dwg_decode_add_object (dwg, &obj_dat, &obj_dat, last_offset);\n"
        "          /* Only the first sixteen bounds-error returns, no private IDs. */\n"
        "          if (added & DWG_ERR_VALUEOUTOFBOUNDS)\n"
        "            {\n"
        "              static unsigned sp_p8p2_obj_b64_seen = 0;\n"
        "              if (sp_p8p2_obj_b64_seen++ < 16)\n"
        '                fprintf (stderr, "SP_P8P2_B64_OBJECT_RETURN\\n");\n'
        "            }\n"
        "          if (added > 0)\n"
        "            error |= added;"
    )
    result = result.replace(before, after, 1)
    if result.count("SP_P8P2_B64_OBJECT_RETURN") != 1:
        raise ValueError("Failed to instrument object error return")
    return result

def patch_100k_guard(source: str) -> str:
    old = "VALUEOUTOFBOUNDS (num_ents, 50000)"
    new = "VALUEOUTOFBOUNDS (num_ents, 100000)"
    if source.count(old) != 1 or new in source:
        raise ValueError("Pinned 50k SORTENTSTABLE guard has changed")
    return source.replace(old, new)

def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("usage: p8p2_instrument_b64_stage.py /absolute/pinned/libredwg-checkout")
    root = Path(argv[1]).resolve(strict=True)
    import subprocess
    actual = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != UPSTREAM:
        raise SystemExit("Pinned upstream commit identity mismatch")
    decoder = root / "src" / "decode.c"
    spec = root / "src" / "dwg2.spec"
    new_decoder = instrument_pinned_decoder(decoder.read_text(encoding="utf-8"))
    new_spec = patch_100k_guard(spec.read_text(encoding="utf-8"))
    decoder.write_text(new_decoder, encoding="utf-8")
    spec.write_text(new_spec, encoding="utf-8")
    changed = subprocess.check_output(
        ["git", "-C", str(root), "diff", "--name-only"], text=True
    ).splitlines()
    if sorted(changed) != ["src/decode.c", "src/dwg2.spec"]:
        raise SystemExit("Unexpected diagnostic patch scope")
    subprocess.run(["git", "-C", str(root), "diff", "--check"], check=True)
    print("PINNED_PUBLIC_B64_STAGE_DIAGNOSTIC_PATCH_APPLIED; NO DWG INPUT")

if __name__ == "__main__":
    main(sys.argv)
