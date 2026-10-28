## Final accepted CI snapshot

Final codeed0e28a, CI40616837797 SUCCESS independently on Linux and Windows:461main,130historical,26security,8scale150,8scale200 eachOS; zero failed/errors/skipped, one fitz warning main and zero other pytest warnings. Broad source005a55f finishes8351PASS/2FAIL/0ERROR/10SKIP,3warnings,568.71s,exit1 withouttimeout; original JUnit in parent current-final.xml. Final direct collection8505,0errors; final source adds12 test-only IFC cases covered independently by main461/CI. Product app/core/scripts/workflow unchanged from broad snapshot. Whole broad is NOT green.

---

## Final integrated followup — source005a55f

Main final local workflow449PASS, security26PASS; full direct collection8493 with no errors. Final current population8363, separate historical130. The earlier finalized full snapshot0bb08b0 completed8347PASS/3FAIL/10SKIP/0ERROR,3warnings in569.41s. Two baseline failures are independently reproduced on original4bdb; third E4 exact-current-row failure is fixed by80ecbaf and deterministic native SelectColumns RED1→E4GREEN31. Final source005a55f broad results are in parent current-final.json/XML; earlier counts must not be reused as its verdict.

Windows CI40614473374 was overall FAILURE despite448main and24security PASS: historical setup failed beforeJUnit, both DPI stages skipped. A real Git CRLF checkout negative validates exact193 manifest-byte rejection and no-transform checkout acceptance. New CI disables Git autocrlf before Windows checkout, leaving source archive bytes/manifest/guard unchanged. CLI now exposes setup errors as retained log/JSON/non-green status and escaped annotation, removes stale requestedJUnit, and keeps exit1. Native setup+Git regression adds two cases:security26PASS. The new CI40615793724 is independently measured in parent ci-measured.json. No setup error is counted as a completed pytest PASS.

---

# Root final checkpoint — 2026-10-28

This section supersedes pending/intermediate statements below. All historical counts and current-suite checkpoints belong to their recorded source snapshot; none is promoted to full current green. QA branch be4bc32 includes both native bulk confirmation repairs and visible-modal polling. Its full current run reached the W1 specialist handoff but a hidden prior dialog could still be selected. The process was deliberately interrupted for diagnosis (SIGTERM, not timeout); current-visible-timer-interruption.json and official current-visible-timer.json retain that outcome. The root f09c85d sibling was also interrupted before reaching the same stale harness sequence; see parent current-final-code-interruption.json.

Final test correction uses QApplication.activeModalWidget(), not the first matching hidden top-level dialog. It targets the actual original executing modal and does not mock confirmation. P4 commit e4c0888 and P5 commit0bb08b0 carry the same correction. A fresh broad current run on P5 app/core/tests/scripts0bb08b0 is recorded separately in the parent current-active-modal.json/log/XML; only its actual finalized result controls whole-current status.

Full collection on final integrated P5:8490, no collection errors, including130 quarantined historical cases. Current population8360. All193 original workflow bytes and their SHA256 manifest remain unchanged; no historical Actions/release/build was executed. Security final dedicated count is measured separately by CI (24 cases), not inferred from a mixed run. Both repaired native bulk files retain original numerical assertions. Compressed logs/JSON have the same original bytes when decompressed; root-retained-compression.json explains retained names.

---

# QA current / historical separation — 2026-10-27

Initial code/test commit: `b9e2b0a4e095192d1ebb6a6a8d49244c2dab8831`;
fresh-cache-integrity followup: `42f21d269c4280277b66b4a682eedf6413e9f209`;
JUnit persistence followup: `eb1ff85b2f62364dbb501eb978f3d6d93c801e0d`;
native bulk-test repair: `0bca42804b802c9b486ffe7144a24fc55c81ab3e`; base `4bdb13d`.
Worktree `/workspace/StructuralPro-Gates-QA`, branch `phase6-three-gates-qa`.
All pytest executions use `/workspace/StructuralPro-Recovery/.venv/bin/python`.

## Outcome

The original 15 collection errors are resolved. Final direct full collection:
**8365 tests, zero collection errors** (8365 = 8235 current + 130 historical),
in `full-collection-junit.log`. Initial commit collection had 8361 tests; the
cache-integrity followup had 8363.
The official historical run finishes **130 passed, zero failed/error/skipped**.
Security/integration tests finish **23 passed** (`security-junit.xml/log`);
the initial commit had 19 passed and cache-integrity followup had 21.
The initial 900s current run finished **exit 124**, with **2893 completed PASSED
progress rows**, zero observed fail/error/skip rows and **no actual JUnit report**.
Its final trace confirms a stale native bulk test awaiting the correct product
confirmation. That test is repaired below; this is not an external blocker.
The replacement complete current run on the repaired snapshot is **pending** in
`current-repaired.xml/json/log` (900s cap, population 8235).
Do not infer complete-suite success from collection or earlier partial runs.

## Root cause and change

`tests/historical_contracts.py` and the official runner both invoked the strict
zero-active `current_policy` on an acceptance branch with 16 active workflows.
The policy correctly rejected that source, preventing 15 historical modules from
collecting. The fix stages a disposable source tree outside the checkout,
excludes `.github/workflows` and Git metadata before copying, preserves then
rejects all other symbolic links, and applies unchanged strict `current_policy`
to the zero-active stage. The static historical fixture is created from that
verified stage in another disposable directory. It contains only the 193
manifest-verified archived YAML files; no YAML or Actions command is executed.
Direct full collection uses the same staging helper. Current mode explicitly
lists all 15 ignored historical modules in its JSON; historical mode runs them
independently. Timeout exits 124 and never reports green. JSON records every
completed JUnit testcase outcome and all failures without changing assertions.
`prepare_fixture` now also enforces the SHA-256 manifest before copying.

Root review found that rechecking only the cached staged source could hide later
tampering in the original quarantine. The followup extracts quarantine-only
integrity validation, distinct from zero-active source authorization, and checks
the actual original quarantine on every `historical_root()` call and before
staging. Two adversarial tests mutate original workflow bytes or its manifest
after fixture caching: both failed before the fix and pass afterward.
`current_policy` and `workflow_paths` still independently reject active Actions.

The supported `--junit PATH` / trailing `junit_output` parameter persists the
actual pytest-generated XML bytes before disposable cleanup. A real subprocess
integration test independently captures the same pytest report during
`pytest_unconfigure` and proves byte equality. A second test supplies stale XML
and a timeout, proving stale output is removed, missing actual XML is not
reconstructed, and status remains 124 / timed out / non-green.
`historical.xml` is the real final historical pytest XML, not synthesized JSON.

Independent negative tests retain rejection of active and linked workflow paths,
quarantine symlinks, other source symlinks, count changes, manifest tampering and
overlapping source/destination. Integration tests execute real subprocess pytest
runs and prove historical assertion failures remain visible, current exclusions
are reported, timeouts remain non-green, source active YAML is unchanged, and
static historical fixture bytes exactly match quarantine bytes with no Git data.

## Native bulk test repair

The 900s initial snapshot progressed through the expensive fivefloor test and
then waited at `test_manual_formula_qt_closure.py:42`, which clicked bulk edit
without responding to the product's deliberate `QMessageBox.question` at
`manual_formula_controls.py:202`. Its captured final traceback and an isolated
20s RED run with 10s faulthandler both establish that cause. The test is outdated;
the product confirmation is correct. The authorized repair changes only
`tests/test_manual_formula_qt_closure.py`: a QTimer finds the actual modal
confirmation, QTest clicks its real native Yes button, and a two-second watchdog
rejects a stalled dialog. Assertions require exactly one actual confirmation and
preserve the original independently specified quantity result **6 -> 3**, copying,
filtering and history checks. No QMessageBox.question mock or product change.
The entire file is GREEN: **3 passed**, actual XML in
`native-bulk-contract-green.xml`. Latest complete current regression now runs
with this repair and the supported real `--junit` output.

## Executions

All commands below run from the worktree root. `$PY` means
`/workspace/StructuralPro-Recovery/.venv/bin/python`; `$QA` means
`docs/acceptance/phase6_p5/verification-20261027-three-gates/qa`.

- `$PY -m pytest -q tests/test_recovery_quarantined_workflow_qa.py --junitxml=$QA/security.xml > $QA/security.log 2>&1`: exit 0, **19 passed**.
- `$PY -m pytest --collect-only -q > $QA/full-collection.log 2>&1`: exit 0, **8361 collected**, zero collection errors. Fontconfig emits a cache message separately.
- `$PY scripts/run_quarantined_workflow_qa.py --mode historical --json $QA/historical.json --log $QA/historical.log`: exit 0, **130 passed**, zero fail/error/skip. Every testcase is in `historical.json`; per-module counts follow.
- `$PY scripts/run_quarantined_workflow_qa.py --mode current --timeout 180 --json $QA/current.json --log $QA/current.log`: exit 124 after 180s, **2867 completed PASSED progress rows**, zero observed failed/error/skipped rows, incomplete JUnit. This checkpoint collected 8230 current tests before the final extra linked-active-path parametrization added one test. It stopped during `tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports`. `current-partial-progress.json` records every completed progress row, explicitly distinguished from a finalized JUnit result.
- `$PY $QA/run_native_diagnostic.py`: exit 124 after 75s, one test incomplete. 30s faulthandler sample shows active JSON decoding in `manual_formula_register.catalog -> clean -> verified -> load -> application.load_manual_formulas`, at line 55 of that test's 70-row review/commit loop. This supports expensive repeated work, **not a proven dialog deadlock or external blocker**. No app/takeoff/performance patch was made.
- `$PY $QA/run_nonwidget_regression.py`: supplementary selection of 612 modules, with all 102 omitted modules explicitly listed. Exit 124 after 180s, **4860 completed PASSED progress rows**, zero observed fail/error/skip; incomplete JUnit. Stopped during `tests/test_phase3_financial_chain.py::test_five_floor_probe_standalone_process_exits_cleanly`. Selection uses direct QApplication/QtWidgets mentions and is not proof of absence of indirect native UI. It is not the full current-suite outcome.
- `$PY scripts/run_quarantined_workflow_qa.py --mode current --timeout 900 --json $QA/current-final.json --log $QA/current-final.log`: exit 124; initial b9e2b0a snapshot, population 8231, 2893 completed PASSED progress rows. `current-final-partial-progress.json` stores all observed outcomes. No actual XML was produced: the read-only observer recorded copied:false and synthesized nothing.

Native repair commands: `QT_QPA_PLATFORM=offscreen timeout 20s $PY -m pytest -vv -s -o faulthandler_timeout=10 tests/test_manual_formula_qt_closure.py::test_bulk_copy_filter_history_with_native_qt_clicks > $QA/native-bulk-contract-red.log 2>&1` (exit124, confirmed question wait); `QT_QPA_PLATFORM=offscreen timeout 30s $PY -m pytest -q -o faulthandler_timeout=10 tests/test_manual_formula_qt_closure.py --junitxml=$QA/native-bulk-contract-green.xml > $QA/native-bulk-contract-green.log 2>&1` (exit0,3PASS). Replacement current command: `$PY scripts/run_quarantined_workflow_qa.py --mode current --timeout 900 --junit $QA/current-repaired.xml --json $QA/current-repaired.json --log $QA/current-repaired.log` (pending).

Followup commands (exit 0): `$PY -m pytest -q tests/test_recovery_quarantined_workflow_qa.py --junitxml=$QA/security-followup.xml > $QA/security-followup.log 2>&1` (**21 passed**); `$PY -m pytest --collect-only -q > $QA/full-collection-followup.log 2>&1` (**8363 collected**); `$PY scripts/run_quarantined_workflow_qa.py --mode historical --json $QA/historical-followup.json --log $QA/historical-followup.log` (**130 passed**).

JUnit followup commands (exit 0): `$PY -m pytest -q tests/test_recovery_quarantined_workflow_qa.py --junitxml=$QA/security-junit.xml > $QA/security-junit.log 2>&1` (**23 passed**); `$PY -m pytest --collect-only -q > $QA/full-collection-junit.log 2>&1` (**8365 collected**); `$PY scripts/run_quarantined_workflow_qa.py --mode historical --junit $QA/historical.xml --json $QA/historical-junit.json --log $QA/historical-junit.log` (**130 passed**, actual XML persisted).

RED evidence is retained: `red.log` has 7 new missing-stage failures / 6 existing
passes; `integrity-red.log` has 1 real missing-manifest-enforcement failure /
15 passes; `timeout-results-red.log` has 2 missing-outcome/timeout-support
failures / 16 passes. `collection-integration-red.log` records the initial
integration overlap rejection (1 collection error), corrected by distinct sibling
disposable source and fixture directories. None of these failures is counted as green.
`cached-tamper-red.log` separately records both real cached-original tampering
failures (2 failed / 19 passed) before the followup fix. `junit-red.log` records
both missing JUnit-support failures (2 failed / 21 passed) before persistence was
implemented.

## All 15 original historical collection-error modules

| Module | PASS | FAIL/ERROR | SKIP |
|---|---:|---:|---:|
| tests/test_binary_build_security_contract.py | 25 | 0 | 0 |
| tests/test_owner_approved_binary_build_workflows.py | 6 | 0 | 0 |
| tests/test_p37_real_product_deployment.py | 2 | 0 | 0 |
| tests/test_p37_release_gate_separation.py | 21 | 0 | 0 |
| tests/test_p61_p70_release_delivery.py | 4 | 0 | 0 |
| tests/test_priority_10_compliance.py | 3 | 0 | 0 |
| tests/test_priority_10_release.py | 3 | 0 | 0 |
| tests/test_priority_10_release_integrity.py | 7 | 0 | 0 |
| tests/test_priority_17_reports_excel_pdf.py | 38 | 0 | 0 |
| tests/test_priority_38_pre_release_freeze.py | 4 | 0 | 0 |
| tests/test_priority_41_ci_dependency_parity.py | 2 | 0 | 0 |
| tests/test_priority_42_windows_runtime_smoke.py | 2 | 0 | 0 |
| tests/test_priority_43_release_artifact_integrity.py | 2 | 0 | 0 |
| tests/test_priority_49_windows_installer_acceptance.py | 2 | 0 | 0 |
| tests/test_priority_9_qa.py | 9 | 0 | 0 |
| **Total** | **130** | **0** | **0** |

## Preserved boundaries

`quarantine-invariants.json` records all 193 filenames and SHA-256 values.
They equal both the reviewed manifest and base manifest. Manifest SHA-256:
`43887084794a8fbd9ac97c23117ea229222c3114cb01986a6270606cbced0e8b`.
All 16 original active workflow paths remain in source; none is copied into the
disposable source. No application/takeoff/CI file was changed; the later authorized scope expansion
adds only the stale native Qt test repair. No push, merge,
main update, force operation, release, EXE/build or GitHub Actions execution was
performed. A source with active Actions still fails `current_policy` independently.

Historical static compatibility does not establish current GitHub settings,
Windows native GUI acceptance, physical UAT, commercial-model availability or
release readiness. Current repaired full regression remains pending until its actual
final result is available. Earlier caps are incomplete timed checkpoints, and the
900s trace identified a fixable stale test contract rather than an external blocker.

Prior collection logs (`full-collection.log`, `full-collection-followup.log`,
`full-collection-junit.log`) are preserved losslessly as `.log.gz` to avoid
duplicating large parameterized node lists. `compressed-collection-artifacts.json`
records uncompressed hashes and sizes; `full-collection-final.log` stays plain.
