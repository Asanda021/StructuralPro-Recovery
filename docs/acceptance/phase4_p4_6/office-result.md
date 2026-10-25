# Site office domain acceptance

Scope: `core/projects/site_office.py`, canonical daily reports and meetings, evidence-backed obstacles, correspondence, action history, document package snapshots. Local actor names provide attribution; they do not establish authentication or external signatures. No external sending occurs.

Daily lifecycle is draft → reviewed → approved → issued; review and approval require distinct local actors. Issued document amendments create new draft records with supersedes/version linkage. Original issued contents remain unchanged. Explicit daily transfer creates one draft physical-progress document per report/activity, with required cumulative quantity semantics and current source evidence. Daily approval alone creates no progress. Existing progress review/approval remain separate commands.

Package sources are actual approved/issued records selected by collection, ID, exact content SHA256 and version. The package stores full detached snapshots and provenance. Unsupported collections, foreign project IDs, altered evidence, mismatched versions/digests and changed physical measurement bases fail closed. Lifecycle transitions recheck source records. Drawing-derived documents remain `waiting_phase7`.

Obstacles and meeting actions have responsible persons, dates, locations/activity references, source evidence and additive resolutions. Read snapshots calculate overdue open actions and obstacles without mutating stored records. Correspondence remains `not_sent`, even when the caller supplies a fabricated delivery status.

TDD evidence: first focused run failed at collection because the office module did not exist (RED). After implementation and additional negative paths, the prescribed offline runner passed 19 tests (GREEN):

```
QT_QPA_PLATFORM=offscreen ../p4-venv/bin/python scripts/run_offline_tests.py -q tests/test_phase4_site_office.py
19 passed
```

Tests cover versions, independent review, no automatic progress, explicit cumulative transfer, duplicate rejection, missing quantity/person count/evidence, cross-project and unknown activity/resource IDs, unit mismatch, tampered records and evidence files, unapproved package/transfer, stale package source at transition, detached read snapshots, overdue and additive resolutions, and no fabricated delivery.

Domain evidence only: UI, exporters, SQLite replay/CAS integration and operating-system acceptance are owned by the coordinating implementation and are not claimed by these tests.

## Review correction evidence

Transfer now captures and compares the activity measurement digest, requires an explicit previous cumulative quantity and latest active earlier approved observation ID, and enforces `cumulative = previous cumulative + signed daily quantity` using Decimal arithmetic. An initial observation requires `initial_observation=True` and explicit zero previous cumulative quantity. Amendments transfer only as corrections of the original report's already approved transferred observation, with exact supersedes linkage; pending originals, duplicate transfers, and old reports with amendment descendants are rejected. Four newly added regression assertions failed before this correction and then passed.

W4 now selects actual `statement_periods` by period number only when an exact period is bound to an existing `statement_workflow` envelope with status `ISSUED`; legacy snapshots cannot claim official issuance. Sealed `progress_reports` require real approved source observations, current measurement bases and evidence. Applied `manual_formula_amendments` and `beam_amendments` use their actual dictionary collections, existing applied mappings and existing canonical-register/source validation (`verified`/`effective`, `beam_current`/`beam_effective_takeoffs`). Unsupported or unbound legacy financial records remain blocked. No collection status is fabricated.

Latest focused offline result: **26 passed**. Includes approved earlier observation reconciliation, pending-original amendment rejection, successful additive progress correction, statement envelope mismatches, and progress report/source tamper.

Residual correction: an issued daily amendment made before any ancestor was transferred can create regular draft progress after explicit reconciliation. If an ancestor was transferred, the nearest transferred ancestor must first have approved progress, then its exact ID is superseded; pending draft transfer returns a clear blocking message. Package read snapshots retain immutable issued content while exposing `current` and `source_error` on both packages and packaged document entries. Two new regressions failed before the fix; latest focused offline result: **28 passed**.
