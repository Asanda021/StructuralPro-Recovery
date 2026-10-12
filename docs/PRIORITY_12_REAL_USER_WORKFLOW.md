# Priority 12 — Real User Workflow

StructuralPro now exposes a deterministic end-to-end workflow for the desktop product:

1. Project
2. Takeoff
3. BOQ
4. Estimate
5. Progress
6. Payment Statement
7. Finance
8. Report

The workflow is derived from persisted project data. It does not perform engineering calculations and it does not delegate workflow truth to AI.

## Product behavior

- The dashboard shows project workflow completion and the next recommended action.
- Each stage has a direct navigation action.
- Downstream stages are visibly blocked when a prerequisite has no meaningful persisted result.
- Existing modules remain directly accessible; workflow guidance does not prevent expert users from navigating manually.
- The application service exposes the same workflow snapshot to future Windows/mobile/Telegram clients.

## Readiness rule

A stage is complete only when its expected persisted data exists. This keeps the dashboard honest: a page being available is not treated as proof that the project work is complete.

## Scope boundary

Priority 12 is workflow orchestration and user guidance. Drawing measurement depth, real-world datasets, engineering libraries, and deeper CAD/BIM validation remain subsequent priorities.
