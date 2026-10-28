## Final root validation — 2026-10-28

This section supersedes intermediate counts and family limitations below. Code/test `e4c0888856be59de1023a94941fa67fcde19d9ed`, tree `adbd72b521c57fc2b683287383a7f5aee244657d`. Actual CI 40614385899 succeeds on Linux offscreen and Windows native: **245 passed each**, zero failed/errors/skipped, one existing fitz FutureWarning each. Counts and artifact digests are preserved in ci-measured.json; earlier XML remains identified by its own run.

Followup `442b878`/`46a6f8c` added 11 parsed-IFC full-flow scenarios and fixed Beam's own legitimate Preview draft invalidating its subsequent read/implicit Commit preview. Column now has a positive complete original editor chain as well as source/proposal/member revision negatives. Beam positive Preview and explicit refresh/Commit and source/CAS negatives are tested; dirty Beam without a documented drawing region remains rejected without invented mapping. Live guard checks remain before writes and after native confirmation. Existing Beam workflow regression is included in the 245-test workflow.

Supported IFC evidence: Beam, Column, solid_slab, block_wall only in their explicitly tested manual synthetic contexts; not all structural subtypes. No engineering IFC MEP mapping or real building acceptance is claimed. The final test-only timer repair waits for a visible actual modal rather than consuming a one-shot while its controls are still constructing. No confirmation is mocked.


اصلاح نهایی آزمون فقط modal فعال QApplication را می‌بندد؛ پنجره مخفی باقی‌مانده از آزمون قبلی نباید انتخاب شود. اجرای گسترده پیشین برای تشخیص این آلودگی حالت متوقف شد و PASS محسوب نشده است.

---

## Follow-up review: all reachable specialist mutations and family binding

Latest code/tests: `b845366`. The earlier 175-test result below predates this follow-up. Root will run the full exact workflow and native Windows CI after integration. Latest targeted result: **28 PASS, zero failure/error/skip**, one existing fitz warning; `w1-secondary-green.xml` is the actual JUnit.

Review correctly identified that Copy/Delete/Create amendment/Review amendment/Apply amendment were still reachable writes outside the initial three-button fix. Ten actual Qt REDs reproduced SQLite changes after proposal replacement (both editors × five actions), using valid original specialist drafts, committed records and amendment data. Added live guard entry checks to all these mutations. Six further REDs covered family dropdown changes: W1 now binds the editor's selected kind to the originally routed kind, without changing non-W1 semantics. Two REDs changed source Revision inside native Delete confirmation then clicked the real Yes button; post-confirmation checks now prevent stale deletion. Negative tests compare full SQLite snapshots, integrity and persisted state after reopening.

The first confirmation-test attempt used QMessageBox.done(Yes), which canceled the static question instead of clicking its Yes button; that was a test harness mistake, corrected before capturing the preserved true SQLite-mutation RED. The final bounded callback clicks the real button and dismisses the dialog in finally even on callback error.

Focused follow-up command:

`QT_QPA_PLATFORM=offscreen /workspace/StructuralPro-Recovery/.venv/bin/python -m pytest -q tests/test_phase6_p4_contextual_takeoff.py -k 'secondary_writes or form_kind or parsed_synthetic_ifc_specialist or modal_review_and_explicit' --junitxml=docs/acceptance/phase6_p4/verification-20261027-three-gates/w1-secondary-green.xml`

The 28 scenarios comprise 12 secondary-write/confirmation negatives, six family-change negatives, eight original positive specialist workflows, two parsed-IFC positive workflows. No full-suite result is claimed for the follow-up. Remaining IFC mapping limitations below are unchanged.

---

# W1 focused verification — synthetic fixtures, 2026-10-27

Code/tests commit: `50b965f` (base `043bb4b`). No push, merge, release or executable build.

The roof and architecture handoffs omitted the existing W1 originating-wizard/proposal guard. Real Qt buttons and SQLite reproduced two RED saves after PDF bytes changed. The minimal fix passes that guard to both original editors and checks it at the entry to Save, Review and Commit. The internal read-only repaint after a successful mutation does not re-authorize or revalidate that completed write. The original engine and draft contracts remain unchanged.

Coverage: 48 negative specialist modal actions (solid_slab/block_wall × save/review/commit × bytes/deletion/revision/project/floor/member/proposal/concurrent draft revision). Existing eight specialist positive review/commit paths also pass. PDF fixtures and engineering drafts are synthetic and manually documented; no quantity extraction from PDF is claimed. Windows deletion callback closes the PDF backend handle first. Modal callbacks always reject the dialog in finally.

Parsed IFC: original IFC4 synthetic fixture and independent explicit identity review, actual GlobalId/SHA/R1/project/member link. Beam uses original complete_beam draft, actual Save and SQLite reopen: positive and nine negative source/context/proof/CAS cases. Slab->solid_slab and Wall->block_wall use original specialist drafts and actual review/commit. Their two additional REDs showed an internal repaint was incorrectly rejecting after the editor's own successful mutation; entry guards fix that. After review, the test explicitly invokes the existing verified-crossview refresh before Commit. This user action rebuilds approved links at current project CAS; there is no automatic refresh of concurrent edits.

Supported evidence map (identity link does not imply geometry/quantity transfer): Beam/IfcBeam save tested; Roof solid_slab/IfcSlab and architecture block_wall/IfcWall review+explicit refresh+commit tested. Column/IfcColumn has an existing engineering transfer implementation but this change does not close the W1 parsed-IFC modal sequence. MEP IFC engineering identity/quantity mapping remains BLOCKED/not demonstrated: no synthetic service-family mapping or invented quantity was added. Roof subtype, floor finish and ceiling IFC mapping remains not verified. All other IFC families/complex models and complete Save->Review->Commit chains remain PARTIAL. The generic parser's ability to display IfcElement is not acceptance of an engineering-family crosswalk.

Final focused command:

`QT_QPA_PLATFORM=offscreen /workspace/StructuralPro-Recovery/.venv/bin/python -m pytest -q tests/test_phase6_p4_contextual_takeoff.py tests/test_phase6_p3_real_project_bridge.py --junitxml=docs/acceptance/phase6_p4/verification-20261027-three-gates/w1-regression.xml`

Result: 175 PASS, zero failure/error/skip, one existing fitz FutureWarning. Full broad suite deliberately not rerun under the delegated focused acceptance scope. Native Windows is for root CI and has not run locally. JUnit metadata in w1-results.json is parsed from actual XML. Intermediate REDs remain preserved and are not counted as successful runs.
