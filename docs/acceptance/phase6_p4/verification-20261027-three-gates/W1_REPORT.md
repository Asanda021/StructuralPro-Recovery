# W1 focused verification — synthetic fixtures, 2026-10-27

Code/tests commit: `50b965f` (base `043bb4b`). No push, merge, release or executable build.

The roof and architecture handoffs omitted the existing W1 originating-wizard/proposal guard. Real Qt buttons and SQLite reproduced two RED saves after PDF bytes changed. The minimal fix passes that guard to both original editors and checks it at the entry to Save, Review and Commit. The internal read-only repaint after a successful mutation does not re-authorize or revalidate that completed write. The original engine and draft contracts remain unchanged.

Coverage: 48 negative specialist modal actions (solid_slab/block_wall × save/review/commit × bytes/deletion/revision/project/floor/member/proposal/concurrent draft revision). Existing eight specialist positive review/commit paths also pass. PDF fixtures and engineering drafts are synthetic and manually documented; no quantity extraction from PDF is claimed. Windows deletion callback closes the PDF backend handle first. Modal callbacks always reject the dialog in finally.

Parsed IFC: original IFC4 synthetic fixture and independent explicit identity review, actual GlobalId/SHA/R1/project/member link. Beam uses original complete_beam draft, actual Save and SQLite reopen: positive and nine negative source/context/proof/CAS cases. Slab->solid_slab and Wall->block_wall use original specialist drafts and actual review/commit. Their two additional REDs showed an internal repaint was incorrectly rejecting after the editor's own successful mutation; entry guards fix that. After review, the test explicitly invokes the existing verified-crossview refresh before Commit. This user action rebuilds approved links at current project CAS; there is no automatic refresh of concurrent edits.

Supported evidence map (identity link does not imply geometry/quantity transfer): Beam/IfcBeam save tested; Roof solid_slab/IfcSlab and architecture block_wall/IfcWall review+explicit refresh+commit tested. Column/IfcColumn has an existing engineering transfer implementation but this change does not close the W1 parsed-IFC modal sequence. MEP IFC engineering identity/quantity mapping remains BLOCKED/not demonstrated: no synthetic service-family mapping or invented quantity was added. Roof subtype, floor finish and ceiling IFC mapping remains not verified. All other IFC families/complex models and complete Save->Review->Commit chains remain PARTIAL. The generic parser's ability to display IfcElement is not acceptance of an engineering-family crosswalk.

Final focused command:

`QT_QPA_PLATFORM=offscreen /workspace/StructuralPro-Recovery/.venv/bin/python -m pytest -q tests/test_phase6_p4_contextual_takeoff.py tests/test_phase6_p3_real_project_bridge.py --junitxml=docs/acceptance/phase6_p4/verification-20261027-three-gates/w1-regression.xml`

Result: 175 PASS, zero failure/error/skip, one existing fitz FutureWarning. Full broad suite deliberately not rerun under the delegated focused acceptance scope. Native Windows is for root CI and has not run locally. JUnit metadata in w1-results.json is parsed from actual XML. Intermediate REDs remain preserved and are not counted as successful runs.
