# Phase 3 priorities 1–3 — verified implementation snapshot

| Priority | Software status | Evidence | Boundary |
|---|---|---|---|
| 1. Existing BOQ | COMPLETE | Effective-amendment audit, source identity gates, five-floor SQLite reopen, full regression | No new BOQ or payment engine |
| 2. User pricebooks | COMPLETE | Actual CSV/XLSX/XLSM imports, header/row rejection, explicit GUI currency/version, reviewed code/unit mapping, CAS, replacement history | Existing text-PDF contract only; no new OCR claim |
| 3. Factors/estimate | COMPLETE | Reviewed ordered document, exact Decimal oracle, estimate history, real Qt clicks | Explicit sequential compounding; no inferred formula, currency conversion or hidden rounding |
| External backup | PASS | Download SHA/53 Manifest entries, Git fsck, SQLite, 80 restored tests | Receipt follows archive creation |

Code: `786515689e5976a1b375960d4920defac2c948de`. Tested tree: `355475521afd27efeb7811d85caa47dc73489afa`. Parent baseline: `3bb02f3bd34496fd078c1ce818a69d26bf8dfb6d`. Earlier code commit: `92d5db9c715de2f62aff594a682b4b2201a463c3`.

[Draft PR #21](https://github.com/Asanda021/StructuralPro-Recovery/pull/21) is separate from unchanged Draft PR #20. No merge, release, EXE, manual Actions, protected branch or StructuralBot change occurred.

Final full regression: **7725 PASS / 0 FAIL / 0 ERROR / 5 SKIP / Exit 0**, 410.50 seconds. Skips are native PowerShell unavailable. Two pre-existing pytest JUnit `record_property` compatibility warnings remain. Targeted: **80 PASS**; focused final: **33 PASS**. Counts overlap and must not be added. Compileall, pip check and diff check each Exit 0. An earlier diagnostic run had two failures; it is retained separately and is not acceptance evidence.

The independent five-floor scenario preserves a PDF-bound slab, a controlled thickness amendment, original takeoffs, two active floors, a wall opening, user-imported synthetic prices and approved factor evidence. Oracle base **2080.40 IRR**, sequential final **2402.86200 IRR**, exact equality after SQLite reopen. PDF/XLSX/DOCX/CSV files were produced and reopened. The 10,000-row high-precision oracle has absolute difference zero. The unchanged 100,000-entity CAD threshold is 500 ms; measured maximum gap **279.11 ms**.

See [supported contracts](phase3_p1_3/contracts.md), [raw final log](phase3_p1_3/final.log), compressed original JUnit `phase3_p1_3/final.xml.gz`, [synthetic scenario](phase3_p1_3/accepted_five_floor/receipt.json), and [Qt screenshot](phase3_p1_3/accepted_five_floor/financial-qt.png). Source JUnit SHA and artifact hashes are in the backup Manifest.

Changed modules: `core/takeoff/estimate.py`, `core/pricing/factors.py`, `core/pricing/import_service.py`, `core/reports/aec_office_package.py`, `core/platform/application.py`, `app/main.py`, `app/financial_factor_review.py`; reproducible probe `scripts/phase3_financial_probe.py`; three new test files. Two old probes were strengthened for the new explicit inputs and blocked unpriced financial finalization, retaining their former quantity/outcome checks.

Eight-phase status: Phase 1 previous engineering acceptance preserved; Phase 2 previous non-Windows closure preserved; Phase 3 priorities 1–3 implemented/tested here, priorities 4–6 not started. Phases 4–8 have no new closure claim. Windows, native PowerShell and Microsoft Office acceptance remain unperformed here. Program remains exactly eight phases.

External recovery completed: [Drive backup](https://drive.google.com/file/d/1sxOtu61bdVHvtFbOOCnCq5x4hqikwOTz/view?usp=drivesdk), 13,214,661 bytes, SHA-256 `1c0ade59874fa1c5ea56a5a61cc0be11b90099f309f9670232902bf3be8be534`. Download, all 53 Manifest entries, Git fsck, restored SQLite and 80 independent restored tests passed (Exit 0). See `phase3_p1_3/recovery.json`. The archive is the pre-receipt snapshot; this later receipt documents its external recovery. No previous backup was changed.

**Phase 3 — Priorities 1–3: COMPLETE — Verified Non-Windows Scope.** This is not closure of all Phase 3. No later priority or phase was started.
