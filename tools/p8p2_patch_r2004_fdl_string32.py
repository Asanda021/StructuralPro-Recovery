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
       * The following num_files RL is mandatory. Guard its four bytes and
       * every remaining feature prefix before reading any feature payload.
       * Never include page padding in the logical section. */
      BITCODE_BL sp_p8p2_free_idx;
      int sp_p8p2_feature_error = DWG_ERR_VALUEOUTOFBOUNDS;
      if (dat->bit != 0 || dat->byte > dat->size
          || dat->size - dat->byte < 4
          || _obj->num_features > (dat->size - dat->byte - 4) / 4)
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
              size_t available;
              size_t remaining_prefixes;
              if (dat->byte > dat->size || dat->size - dat->byte < 4)
                goto sp_p8p2_features_fail;
              size = bit_read_RL (&prefix);
              if (prefix.byte > prefix.size)
                goto sp_p8p2_features_fail;
              available = prefix.size - prefix.byte;
              remaining_prefixes = (size_t)(_obj->num_features - vcount - 1) * 4 + 4;
              if (remaining_prefixes > available
                  || (size_t)size > available - remaining_prefixes)
                goto sp_p8p2_features_fail;
              _obj->features[vcount] = bit_read_T32 (dat);
              if (!_obj->features[vcount])
                goto sp_p8p2_features_fail;
            }
        }
      /* A feature may never consume the mandatory num_files RL. Therefore
       * the pinned upstream T32 >= end check cannot reject a valid feature. */
      goto sp_p8p2_features_done;
sp_p8p2_features_fail:
      for (sp_p8p2_free_idx = 0;
           sp_p8p2_free_idx < _obj->num_features; sp_p8p2_free_idx++)
        free (_obj->features[sp_p8p2_free_idx]);
      free (_obj->features);
      _obj->features = NULL;
      _obj->num_features = 0;
      return sp_p8p2_feature_error;
sp_p8p2_features_done:
      ;
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
