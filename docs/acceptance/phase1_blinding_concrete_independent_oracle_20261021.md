# StructuralPro — Phase 1: bounded independent blinding-concrete oracle (Chat)

**Date:** 2026-10-21  
**Family:** `blinding_concrete` / بتن مگر  
**PR:** #18, Open/Draft  
**Before:** `70b2dea34d43b10b6c195d95f10210508fbca4f6`  
**Result:** new actual repository regression module, no changes to production engine/BOQ/pricebook.

## Completed source and tests

- Added `tests/test_phase1_blinding_concrete_independent_oracle_chat.py`: **15 parametrized pytest cases** (3 positive independent Decimal quantity cases, 9 fail-closed input/provenance cases, 1 invalid physical unit, 1 altered-geometry mismatch detection, 1 real SQLite/CAS/reopen/unrelated nonempty BOQ preservation).
- Inputs are explicit **synthetic rectangular footprint** data, not an approved project drawing or an engineer-signed independent specialist certificate.
- All positive expected values are computed separately from the engine, with Decimal from the declared dimensions. The live calculation route under test is the existing AEC `empty_system` → `preview_system` → `TakeoffEngine`/ `footing_concrete` and `StructuralProApp` for SQLite. No payable handoff is performed.
- Local Python 3.13 Decimal-only checks of the three independent reference quantities **executed successfully (3 PASS / 0 FAIL)** in this Chat environment.
- **Important:** The newly committed 15 pytest cases **have not been executed against the complete repository** in the Chat container (no direct GitHub checkout). Their success and comprehensive regression cannot be claimed. Commands for subsequent verified execution:

```bash
python -m pytest -q tests/test_phase1_blinding_concrete_independent_oracle_chat.py
python -m pytest -q tests/test_phase1_37_family_triage_gate_chat.py
```

## Independent numbers (synthetic; SI units)

| Length m | Width m | Thickness m | Count | Independent Decimal volume m³ |
|---:|---:|---:|---:|---:|
| 3 | 2 | 0.1 | 1 | 0.6 |
| 2.4 | 1.25 | 0.08 | 4 | 0.96 |
| 1.125 | 2.25 | 0.15 | 2 | 0.759375 |

These cases do not establish a contract measurement rule for irregular footprints or additional blinding-concrete components. Quantity for existing synthetic fixtures is never imported as actual project proof.

## Fail-closed boundary

Missing/mismatched dimensions, zero/negative parameters, unreviewed essential component, missing source/reviewer, duplicate physical line, wrong discipline and wrong `kg` unit are asserted to block preview. A changed but otherwise valid dimension must create a new independent expected reference, not claim unchanged quantity. SQLite test asserts saved draft after reopen, stale CAS rejection, PRAGMA integrity and preservation of a **nonempty unrelated BOQ** without modifying it.

## Engineering acceptance — still OPEN

The family requires real survey/plan levels, sections and limits, documentary source/revision, deductions, preparation/formwork owner, reviewed quantity oracle and engineering reviewer. Those are specified in `docs/acceptance/phase1_closure_37_family_review_20261020.json`.

The row `blinding_concrete` in `docs/acceptance/phase1_37_family_actionable_triage_20261021.json` now includes a `bounded_independent_component_oracle` entry with explicit status `not_run` for full pytest and **`full_family_engineering_accepted:false`**. All 37 previously missing independent whole-family acceptances remain missing. No phase gate is silently closed.

**Change restrictions:** No Windows/Office, Merge, Release, manual Actions or executable build. PR remains draft. No new phase or financial-route permission.
