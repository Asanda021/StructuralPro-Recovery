/* StructuralPro P8/P2: exact LibreDWG dwg_read_file return-mask probe.
 * No modification to source DWG, no serialization, no financial permission.
 * Build ONLY against the pinned, trace-enabled LibreDWG source.  The commit
 * string is a compile-time label, NOT a substitute for binary+library SHA.
 */
#include <stdio.h>
#include <string.h>
#include <dwg.h>
#ifndef STRUCTURALPRO_LIBREDWG_COMMIT
#define STRUCTURALPRO_LIBREDWG_COMMIT "UNPINNED"
#endif

int main(int argc, char **argv)
{
    Dwg_Data dwg;
    int mask;
    if (argc != 2 || !argv[1] || !argv[1][0]) {
        fputs("Expected exactly one local DWG file argument\n", stderr);
        return 64;
    }
    memset(&dwg, 0, sizeof(dwg));
    dwg.opts = 9; /* maximal trace if compiled with --enable-trace */
    mask = dwg_read_file(argv[1], &dwg);
    /* Print machine-readable summary, independent from C process exit. */
    printf("STRUCTURALPRO_LIBREDWG_COMMIT=%s\n", STRUCTURALPRO_LIBREDWG_COMMIT);
    printf("STRUCTURALPRO_C_API_MASK=%d\n", mask);
    printf("STRUCTURALPRO_C_API_OBJECTS=%lu\n", (unsigned long)dwg.num_objects);
    fflush(stdout);
    dwg_free(&dwg);
    return 0; /* successful DIAGNOSTIC invocation; not source acceptance */
}