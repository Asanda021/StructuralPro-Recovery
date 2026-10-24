# Phase 4 priorities 1–3 implementation plan

> Execute inline with superpowers:executing-plans, test-driven development, and one independent whole-branch review.

Goal: complete only WBS (20%), CPM/calendar/Gantt (25%), and verified weighted progress (20%) using the existing project store, management collections, and report services.
Architecture: extend the existing ProjectManagement domain with project-control validation and computations in focused support modules. Persist canonical activities in project_schedule_tasks; physical floors/members keep their existing IDs. All project-control mutations replay validated commands inside ProjectStore's existing SQLite transaction and CAS, with append-only history and immutable baselines/report revisions.
Tech: Python, Decimal, SQLite, PySide6/QTest, existing Persian exporters.
Spec: docs/acceptance/phase4_p1_3/mission.fa.md

## Global constraints
No main/prior PR writes, merge, force push, release, executable, manual Actions, new financial/BOQ engine, fabricated quantities or StructuralBot. Only explicit working days/holidays, durations, progress distribution, source and weights. Native Windows/Office not claimed.

## Review focus
- Aggregate BOQ rows and many physical locations must not duplicate quantity ownership.
- Revisions of source quantities must mark the activity basis stale, never silently replace baseline.
- Missing approved weights/work/distribution means unknown, not zero.
- Calendar boundaries, negative lags, different dependency types and milestone semantics must be mathematically explicit.
- Direct payload writes, concurrent edits and partial failures must not mutate official history.

## Tasks
1. WBS/physical structure and canonical activity commands: extend existing floors and project_schedule_tasks with stable IDs, explicit links, sources, units, append-only event history; application API and store guard. Tests: hierarchy/cycle/duplicate, multi-floor assignment, BOQ ownership/unit/stale basis, CAS, failure atomicity, SQLite reopen.
2. CPM: core/projects/scheduling.py supporting explicit workday durations, FS/SS/FF/SF and signed workday lag, calendar, topological longest-path earliest/latest/free/total floats; immutable baseline and current versions via same commands. Tests: independent network oracle, parallel/critical/float, milestone, cycle, holidays and year boundary.
3. Verified progress: support module for reviewed cumulative quantity documents, formal superseding corrections, approved versioned weights and explicit linear/milestone/manual planned curves. Decimal aggregation by WBS/floor/zone/discipline with coverage; append-only dated reports and S-curve points with no interpolation. Tests: zero/full/overrun, negative/missing, approval independence, quantity and weight corrections, missing coverage, period history/reopen.
4. Operational management workspace: RTL WBS tree/activity table and detail forms, explicit structure/relationship/calendar editing, Jalali dates, baseline controls, QGraphics Gantt selection/zoom/dependencies/milestones/baseline/progress, source drilldown and S-curve. Real menu/ribbon entry; QTest actions and selection; large activity responsiveness gate.
5. Existing exporter adapters for WBS, activities, CPM, progress/variance, Gantt and S-curve figures, PDF/XLSX/DOCX/CSV readback and visual QA. Five-floor synthetic integration with independent CPM/Decimal oracle, multiple disciplines/periods and schedule revision.
6. Independent review; fix reproduced critical findings with RED→GREEN tests. Final targeted suite then one final full regression. Capture logs/JUnit/images, exact commit/tree, overlapping case identities; preserve five PowerShell skips.
7. Draft dependent PR, source/evidence bundle SHA256 Manifest, new Drive backup, redownload/Git+SQLite+targeted recovery; final evidence-only commit/report. Stop before priorities 4–6.

Each task: write and observe failing acceptance test, implement, run relevant old/new tests, commit and update execution ledger. Full regression once after final executable freeze, per user instruction.
