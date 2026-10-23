# Phase 3 priorities 4–6 execution plan
Goal: complete the existing statement and financial workflows, keeping eight phases.
Architecture: reuse statement periods, amendment service, exact_values, existing financial collections and ProjectStore CAS/revisions. Add guarded commands, never a parallel calculation engine. Owner-documented authority is local attribution, not authenticated identity.
Tech stack: Python, Decimal, SQLite, PySide6/QTest and existing RTL exporters.
Spec: owner's phase 3 priorities 4–6 mission in this Work thread.
Constraints: no protected branch changes, merge, release, EXE, manual Actions, guessed terms, or old backup deletion.
- [ ] P4: tests for two periods, workflow authorization, explicit terms/factors/advance cap, immutability, amendment and CAS; implement guarded transitions through existing calculation functions.
- [ ] P5: tests for exact cash/accrual distinction, approved budget/commitment/cost/payment/receipt records, duplicate references, caps, reversals, rollback; extend existing ledger and transactional guard.
- [ ] P6: operational RTL finance dialog and existing amendment UI; report export/reopen and Qt tests; independent five-floor scenario.
- [ ] Final targeted tests, one final full regression, evidence and hashes; new dependent Draft PR; Drive backup/download/manifest/Git/SQLite restore.
Review focus: stale revisions, mixed currencies, changing signed sources, nonfinite/oversized decimals, partial settlement and reversal after dependent records.
