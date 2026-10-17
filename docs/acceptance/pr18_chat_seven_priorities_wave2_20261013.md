# PR18 Seven Chat priorities — acceptance handoff, 2026-10-13

Verified parent head: 72cd77847edbbdc83fc0a9e33719367086f01641. Draft only.

1. Finance: BOQ/pricebook changes invalidate stale estimates; issued statements lock contract basis; financial exports require approved provenance.
2. Roofs: source-backed hollow-core section/void length and waffle rib/intersection counts; Uboot and composite safeguards remain active.
3. Structural: engine and Qt form require an explicit geometry shape; negative tests cover missing shape.
4. Manual takeoff: CAS-protected deletion creates a source tombstone and audit trail; issued statements block direct deletion.
5. UI: AEC table displays persisted takeoff and source identity; menu callback source contracts tested.
6. PDF: scale, drawing units, lengths and areas reject ambiguous/nonfinite/unverified input.
7. PR chain: linked Draft PRs audited; Dropbox backup is older than current HEAD.

Offline reconstructed checkout:
- Core: 330 passed.
- Group 2: 348 passed.
- New Chat7 tests: 68 passed.
- Structural GUI source and engine suite: 89 passed.
Groups overlap; no unique total may be inferred.

Broad offline pytest could not collect Qt tests due to missing PySide6.
Partial non-Qt run stopped at 25 failures (2062 pass, 1 skip); old fixtures, PDF dependencies and indirect Qt affected results. These are NOT exact-head or complete QA results. Earlier Work full baseline 2686 pass, 58 fail, 5 skip is not superseded.

Need Work/Windows: clean current PR18 SHA checkout, full pytest, real PySide6 clicks, Persian PDF, real DWG/PDF tests, five-storey golden scenarios and exact-HEAD Dropbox backup with recovery verification.

No Merge, GitHub Actions, Build, Release or Installer is authorized. Preserve 193 workflow quarantine files.