# StructuralPro Troubleshooting

## Application does not start

1. Confirm the installed version.
2. Re-run the supported installer if files may be incomplete.
3. Check application logs.
4. Try a new empty project to distinguish installation issues from project-data issues.
5. Preserve the failing project and logs before attempting destructive recovery.

## Project fails integrity validation

Do not continue editing blindly. Preserve a backup/copy first, inspect audit/history and identify the first failing validation. Restore the last known-good revision or backup when appropriate.

## Import produces unexpected quantities

Check:
- drawing scale;
- units;
- source ID;
- duplicate source detection;
- invalid/negative quantity warnings;
- converter output when DWG is involved.

Do not manually override a quantity until the source and measurement assumptions have been checked.

## Price is missing or unexpected

Check price-source provenance, effective/version information, custom-price overrides and project snapshots. Official annual price data must come from a verified/licensed source.

## AI output is incorrect

Treat AI output as advisory. Re-check the source drawing and deterministic calculation path. Do not allow an AI suggestion to silently replace an engineering quantity or calculation.

## Windows installer fails

Check the release version, installer log/output, expected dist/StructuralPro/StructuralPro.exe path, packaged VERSION and Inno Setup output. Confirm that the build used the canonical VERSION.

## Backup restore fails

Keep the original backup unchanged. Check integrity/tamper validation and compatibility. Try the most recent known-good backup only after preserving evidence from the failed restore.

## Release workflow cannot be verified

Do not infer a successful Windows build from the existence of workflow YAML alone. Confirm an actual GitHub Actions run and its artifact when the runner is available. If the API does not expose the run, record the limitation explicitly.
