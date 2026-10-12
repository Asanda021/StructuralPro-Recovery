# Master Roadmap Acceptance — Phases 9–12

This document defines the closure evidence for the fixed master roadmap phases. It is not a claim that untested manual or customer-environment acceptance has already occurred.

## Phase 9 — Whole-building AEC and project controls
- Deterministic quantities and normalized units across architecture, structure, mechanical, electrical and count-based items.
- The discipline registry must include concrete, steel, masonry, timber, composite, renovation, historic and external/site work.
- Negative or non-finite quantities must fail closed.
- Existing product workflow tests remain part of the acceptance gate.

## Phase 10 — Estimate, finance, progress statements and reports
- Takeoff source identifiers remain traceable through BOQ.
- BOQ quantities and prices reconcile to estimate totals; invalid negative factors are rejected.
- Payment allocations cannot exceed the payment amount; budget and commitment variance is deterministic.
- A progress statement and CSV report must be generated through the application service, not a test-only report implementation.
- Official pricebook values must retain provenance; synthetic values in tests are fixtures only.

## Phase 11 — Reliability, recovery and large-project behavior
- A 10,000-row takeoff collection is measured by the production performance snapshot.
- Project save/read and backup export/import preserve project identity and data.
- SQLite integrity is checked after persistence.
- These CI tests do not substitute for benchmarking on representative customer hardware.

## Phase 12 — Persian RTL UX and accessibility contracts
- Persian navigation and offline help topics exist.
- Action keys and keyboard shortcuts are unique; labels and tooltips are present.
- Dirty/offline status is explicit.
- Focus and disabled-state styling remains available in the desktop theme.
- Final visual acceptance still requires a Windows desktop review at supported display scales.

## Merge / closure rule
Close the PR only when its dedicated phase tests and the full test suite pass, all required CI checks are green, the changes are merged, and post-merge main checks are green. Keep any manual or external-data acceptance item explicitly open until evidence is supplied.
