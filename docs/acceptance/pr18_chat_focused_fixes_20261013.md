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
