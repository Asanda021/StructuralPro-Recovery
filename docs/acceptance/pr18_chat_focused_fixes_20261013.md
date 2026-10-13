# PR #18 — focused Chat follow-up acceptance record

Date: 2026-10-13. Existing Draft PR only; no merge, release or Actions.

## GitHub changes
- Financial cost/commitment/receipt ledgers remain reportable with no BOQ; unknown contract amount, progress and margin are None, never an invented zero.
- Cost reports use the existing recorded cost category when an optional description is blank.
- Legacy regression fixtures carry explicit one-member count, a stable synthetic source identity and a reviewed unit/price catalog with a hash-verified on-disk fixture.
- The SQLite spawned estimator test still performs a successful concurrent estimate with an actual reviewed fixture pricebook; it is not weakened into a negative-only check.
- Historical test fixtures never authorize production defaults or prices.

## Executed local evidence
- Source: the owner's Dropbox backup StructuralPro_PR18_Followup_20261013.zip, whose archived Git HEAD is 4a6e7ebf55c7dccda90f14993656fd97f14ff362.
- Archive: 1,630 entries; ZipFile.testzip found no corrupt members.
- Initial archived selected test suite: 25 PASS and 18 FAIL (including one absent PySide6 dependency).
- An offline copy with selectively reproduced current GitHub fixes: 16 PASS, 0 FAIL, 0 SKIP in a combined targeted pytest run (1.75 seconds).
- Breakdown: 6 P32 regression tests; 1 application-service sourced takeoff; 1 shared product workflow; 1 successful cross-process priced SQLite update; 7 finance/cost/ledger/report cases.
- Python 3.13 and pytest 9.0.2; PySide6 not installed. No Windows GUI acceptance.

## Limitations
- Not a byte-identical checkout or full pytest run of the latest PR #18 HEAD; do not promote local 16 PASS to full CI GREEN.
- Work baseline of 58 FAIL and 5 SKIPPED remains the latest complete project result until rerun.
- No main merge, Github Actions activation, installer or release.


## Follow-up: approved pricebook and legacy stabilization regression

- Added a **reusable explicit fixture** in tests/conftest.py. It serializes independently supplied code/unit/rate values to a real local file, verifies file SHA-256 in the production gate, and marks approval with a named test reviewer. The fixture does not derive prices from BOQ.
- Restored product-chain acceptance: architecture wall with explicit count and source -> BOQ -> approved pricebook -> estimate/factors -> statement -> CSV report -> SQLite reopen.
- Updated P36/P37/P38 stability, JSON serialization, backup and freeze acceptance to use the same reviewed source-backed pricebook fixture.
- Updated six real-life finance/cost/receipt/progress test functions (seven measured wall sources) with **explicit physical count** and distinct synthetic fixture identities, and catalog prices backed by SHA-256.
- Offline tests on the user's Dropbox archive \`StructuralPro_PR18_Followup_20261013.zip\`, selectively overlaid with matching updated source/tests:
  \`45 PASS / 0 FAIL / 0 SKIPPED / 4 DESELECTED\`. Python 3.13, pytest 9.0.2; this includes successful spawned-process SQLite persistence.
- The 4 deselected tests exercise stale desktop conditions including PySide6 and were not within this specific pricebook regression scope.
- This is NOT a full checkout of the current PR #18 HEAD, not Windows GUI acceptance and not the full ~2,750-test suite. **Do not decrement the original 58 FAIL or 5 SKIPPED before a fresh full-branch run.**

## Follow-up: P31/P33/P35/P51 golden acceptance — 2026-10-13

Four additional historic suites were revised, without changing production calculation gates:

- tests/test_priority_31_deep_testing.py: approved source-backed slab-volume estimate; independent fixture source/physical count; duplicate identity; invalid factors now assert their actual validation message after a valid reviewed m2 pricebook rather than accidentally passing because of missing rates.
- tests/test_priority_35_real_world_golden.py: reviewed individual concrete and reinforcement-related quantities with distinct price codes and explicit slab member count; recovery and three-part Golden acceptance now use approved local pricebook. Added a **negative** unreviewed-rate acceptance: rate/code alone cannot create an estimate or mutate persisted project.
- tests/test_priority_51_golden_project_e2e.py: whole project with both slab area m2 and beam volume m3 has independently supplied reviewed price entries and explicit count; source, report and recovery checks retained.
- tests/test_priority_33_edge_failure.py: duplicate source remains blocked; invalid factor failure is only counted after a valid approved pricebook; AI confirmation path is still read-only.

Offline Python 3.13.5 / pytest 9.0.2 on owner's Dropbox archive, selectively overlaid with these corresponding changes and the same source-backed shared fixture:

    tests/test_priority_31_deep_testing.py
    tests/test_priority_35_real_world_golden.py
    tests/test_priority_33_edge_failure.py
    tests/test_priority_51_golden_project_e2e.py

Result: **28 PASS, 0 FAIL, 0 SKIPPED** in 1.59 s.

Scope caveat: archived repository at 4a6e7ebf55c7dccda90f14993656fd97f14ff362 is not a byte-identical checkout of the latest branch; this is targeted offline corroboration, not PR-head full regression and not Windows/PySide6 GUI acceptance. The last entire-worktree Work baseline remains 2686 PASS / 58 FAIL / 5 SKIPPED until rerun. All changes remain on the existing Draft PR #18 branch. Never weaken engineering provenance, pricing approval or quantity gates.

## Further targeted repair: stale SQLite, explicit steel inputs, phase 10 — 2026-10-13

- tests/test_audit_critical_persistence.py: stale estimator, snapshot and report scenarios now have real, approved, hash-verified fixture unit rate and explicit source/count. This continues to test that a stale desktop never discards an external measurement. The Qt audit UI variant is **not locally verified** due to absent PySide6.
- tests/test_application_service.py: project statement/financial controls include reviewed file-backed pricing; previous arbitrary BOQ price mutations no longer count as verified provenance.
- tests/test_p76_layer1_engineering_foundation.py: verified steel member count, independently specified plate density and its reference, weld unit weight; new fail-closed regressions reject missing density provenance, weld unit weight or element count. No engineering default introduced.
- tests/test_roadmap_phase10.py: wall count explicit; price from a fixture with real on-disk hash and reviewer through estimate, statement and CSV report.

### Actual offline verification

On the user's Dropbox archive (archived git HEAD `4a6e7ebf55c7dccda90f14993656fd97f14ff362`) reconstructed with **selectively replicated** changes:

- Combined 13-test-file regression: **88 passed, 0 failed, 4 deselected in 4.71s**.
- Three separately executed non-GUI stale-desktop SQLite variants passed; the Qt variant was not executed because PySide6 is unavailable.
- A diagnostic whole-suite pytest attempt on this reconstructed archive timed out after reaching ~85% of selected tests. A faster stopped run showed old archived test mismatches and missing local PySide6/arabic_reshaper; this is **not** the current branch's remaining-failure count.
- The latest **genuine entire-worktree Work baseline** remains **2686 passed, 58 failed, 5 skipped**, pending a fresh full-suite run on exact PR #18 HEAD.
- No Windows GUI evidence is claimed. No main merge, Actions run, build or release was requested.

Note: The 88-case local sample is useful functional evidence, not final product acceptance.
