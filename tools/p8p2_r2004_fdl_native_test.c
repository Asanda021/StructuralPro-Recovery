/* Synthetic-only native regression; never pass CAD input to this program. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "dwg.h"
#include "bits.h"

extern int sp_p8p2_test_filedeplist (Bit_Chain *, Dwg_Data *);

static int
check (unsigned char *bytes, size_t size, int bit, int valid)
{
  Dwg_Data dwg = {0};
  Bit_Chain dat = {0};
  dat.chain = bytes;
  dat.size = size;
  dat.bit = bit;
  dat.version = dat.from_version = R_2004;
  int error = sp_p8p2_test_filedeplist (&dat, &dwg);
  int ok = valid ? error == 0 && dat.byte == size && dat.bit == 0
                 : (error & DWG_ERR_VALUEOUTOFBOUNDS) != 0;
  if (valid && dwg.filedeplist.num_features == 1)
    ok = ok && dwg.filedeplist.features
         && strcmp (dwg.filedeplist.features[0], "abc") == 0;
  if (dwg.filedeplist.features)
    {
      for (unsigned i = 0; i < dwg.filedeplist.num_features; i++)
        free (dwg.filedeplist.features[i]);
      free (dwg.filedeplist.features);
    }
  return ok;
}

int main (void)
{
  unsigned char valid[] = {1,0,0,0, 3,0,0,0, 'a','b','c', 0,0,0,0};
  unsigned char empty[] = {0,0,0,0, 0,0,0,0};
  unsigned char too_many[] = {255,255,255,127, 0,0,0,0};
  unsigned char too_long[] = {1,0,0,0, 255,255,255,255, 0,0,0,0};
  unsigned char short_prefix[] = {1,0,0,0, 1,0,0};
  unsigned char unaligned[] = {0,0,0,0, 0,0,0,0, 0};
  int ok = check (valid, sizeof valid, 0, 1)
           && check (empty, sizeof empty, 0, 1)
           && check (too_many, sizeof too_many, 0, 0)
           && check (too_long, sizeof too_long, 0, 0)
           && check (short_prefix, sizeof short_prefix, 0, 0)
           && check (unaligned, sizeof unaligned, 1, 0);
  if (!ok) { fputs ("Synthetic native FileDepList regression FAILED\n", stderr); return 1; }
  puts ("Synthetic native FileDepList: 6 cases PASS; no CAD input");
  return 0;
}
