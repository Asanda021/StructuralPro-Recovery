"""Source-pinned, nonproduction R2004 FileDepList feature decoder correction.

ODA DWG specification section 17 defines these fields as String32, not TV.
Only the AC1018 decode branch changes; generic TV and other versions are intact.
This is an isolated diagnostic patch, never a financial acceptance mechanism.
It deliberately does NOT change SORTENTSTABLE limits or suppress native errors.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

UPSTREAM = 'a83575825b86528bf1997484852b2a9f5cdbbac0'
TARGET = '  FIELD_VECTOR_T (features, TU32, num_features, 0);'
REPLACEMENT = r'''#ifdef IS_DECODER
  if (dat->from_version == R_2004)
    {
      /* SP_P8P2_R2004_STRING32: ODA section 17, byte-aligned RL size.
       * Preserve bounds failures and allocation errors. Never reinterpret
       * page padding as part of the logical section. */
      if (dat->bit != 0 || dat->byte > dat->size
          || _obj->num_features > (dat->size - dat->byte) / 4)
        return DWG_ERR_VALUEOUTOFBOUNDS;
      if (_obj->num_features)
        {
          _obj->features = (char **)calloc (_obj->num_features, sizeof (char *));
          if (!_obj->features)
            return DWG_ERR_OUTOFMEM;
          for (vcount = 0; vcount < _obj->num_features; vcount++)
            {
              Bit_Chain prefix = *dat;
              BITCODE_RL size;
              if (dat->byte > dat->size || dat->size - dat->byte < 4)
                return DWG_ERR_VALUEOUTOFBOUNDS;
              size = bit_read_RL (&prefix);
              if (size > prefix.size - prefix.byte)
                return DWG_ERR_VALUEOUTOFBOUNDS;
              _obj->features[vcount] = bit_read_T32 (dat);
              if (!_obj->features[vcount])
                return DWG_ERR_VALUEOUTOFBOUNDS;
            }
        }
    }
  else
#endif
    {
      FIELD_VECTOR_T (features, TU32, num_features, 0);
    }'''


def patch_spec(source: str) -> str:
    if source.count(TARGET) != 1 or 'SP_P8P2_R2004_STRING32' in source:
        raise ValueError('Pinned FileDepList feature anchor missing or already patched')
    return source.replace(TARGET, REPLACEMENT, 1)


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit('usage: python -m tools.p8p2_patch_r2004_fdl_string32 /public/checkout')
    root = Path(argv[1]).resolve(strict=True)
    actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != UPSTREAM:
        raise SystemExit('Pinned upstream identity mismatch')
    path = root / 'src/filedeplist.spec'
    original = subprocess.check_output(['git', '-C', str(root), 'show', UPSTREAM + ':src/filedeplist.spec'])
    if path.read_bytes() != original:
        raise SystemExit('FileDepList input differs from pinned source')
    path.write_text(patch_spec(original.decode()), encoding='utf-8')
    subprocess.run(['git', '-C', str(root), 'diff', '--check'], check=True)
    print('PINNED_R2004_STRING32_DIAGNOSTIC_PATCHED; financial approval remains false')


if __name__ == '__main__':
    main(sys.argv)
