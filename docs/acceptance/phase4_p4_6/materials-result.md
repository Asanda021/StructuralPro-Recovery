# W3 materials domain result — 2026-10-24

Implemented in `core/projects/site_materials.py`; direct domain acceptance in `tests/test_phase4_site_materials.py`. No shared source files, BOQ engine, financial ledger, services, orders, or external writes changed.

## Interface and operation schemas

`dispatch(p, op, data, actor, reason)` mutates only its supplied isolated payload and returns a detached result. Root supplies permissions/CAS/replay/persistence. `OPS` is the exact supported operation set. `KEYS` protects `project_materials`, `material_rules`, `material_requirements`, `material_closures`, `purchase_drafts`. `snapshot(p, *, as_of, activity_id=None)` is read-only; authoritative numeric values are Decimal strings, unknown stock/shortage is `None`.

All operations require explicit nonempty actor/reason. All IDs must be unique within their canonical collection. Optional `project_id` must match the payload.

| Operations | Required data, with optional fields marked `?` |
| --- | --- |
| material_rule_create | id, material_code, specification, base_unit, material_unit, ratio, waste_percent (explicit 0 allowed), source_version, source |
| material_rule_review / material_rule_approve | id; creator, reviewer, approver must all differ |
| material_need | id, rule_id, source_ids (whole aggregate), item_code, activity_id, floor_ids, zone_ids, period_start, period_end, supersedes?, quantity_approval? |
| inventory_opening / receipt | id, material_code, unit, quantity, date, reference, source, confirmed=True, supplier? |
| inventory_consume / reserve | same as receipt plus requirement_id |
| inventory_return | same as receipt plus direction=stock_in/stock_out, reference_id; stock_in references consumption and stock_out references receipt; quantity is capped to its unreturned balance |
| inventory_correct | id, material_code, unit, date, reference, source, confirmed=True, reference_id; quantity is inferred exactly from reference, never overwritten |
| inventory_close | id, material_code, unit, period_start, period_end, source, confirmed=True |
| purchase_draft | id, requirement_id, as_of, owner, supplier?, price?, currency?, price_source?; supplied price requires currency and source |
| purchase_review / purchase_approve | id; creator, reviewer, approver must all differ |

`source` / `price_source` are existing controls evidence objects `{path, sha256, reference}` and are reverified against real bytes. Dates are explicit ISO dates. Units use existing normalize_unit without implicit conversion. A material code cannot acquire conflicting specifications or units.

Need uses existing `audit_boq`, `effective_takeoffs`, and `boq_basis`; no parallel quantity engine. Original BOQ operation and unit remain part of source identity, so one source's concrete/formwork operations remain distinct. A physical material allocation for the same source-set/operation/unit is unique, even across activities. The entire BOQ aggregate source-set is required.

Canonical specialist `review.approved_by` and committed reviewed-register source IDs are recognized. Canonical older manual rows without an approval marker require explicit `quantity_approval={source, approved_by, source_version, basis_digest}`. Its approver must differ from the creator and its digest must exactly equal existing `controls.boq_basis(p,row)`. Explicit unreviewed/draft/proposed/rejected source status is blocked; AI provenance without original committed reviewed registry is blocked even when supplied this approval. No legacy takeoff approval fields are fabricated.

## Calculation and preservation

Need = audited BOQ base quantity × explicit approved consumption ratio × (1 + approved waste_percent / 100), under the existing exact Decimal context (512 digits, inexact/rounded traps). BOQ financial current-period quantities/prices do not redefine material quantity basis.

On-hand = opening + actual receipts + consumption returns − actual consumption − supplier returns. Net consumption is consumption minus its capped stock-in returns. Outstanding reservation = max(cumulative reservation − net consumption, 0). Free stock = on-hand − all outstanding reservations. For each current material/unit need, remaining = max(need − net consumption, 0). Its own outstanding reservation is protected. The free pool is allocated exactly once in deterministic `(period_start, period_end, id)` order; shortage = max(remaining − own outstanding reservation − allocated free stock, 0). Activity filtering never changes the project-wide allocation. This prevents both double consumption/reservation counting and double use of common free stock.

An explicit source-backed opening and complete period attestation covering opening through as_of are required for known on-hand/free stock/shortage. The attestation hashes all official ledger entries through its period end. New/backdated entries invalidate it until a fresh close. Missing opening, missing close, or changed source bytes produces unknown. Confirmed explicit 0 opening plus complete coverage produces true 0. Legacy MaterialRecord rows are preserved verbatim and never promoted to official stock. New official events retain name/quantity/unit/date/supplier/status in canonical `project_materials` alongside metadata.

Returns and corrections append; originals remain unchanged. Corrections reference and reverse, with dependency returns reversed first. Duplicate document references, over-consumption/reservation, incompatible units, foreign project records and negative chronological known balances are rejected. Requirement supersession preserves prior records; outstanding linked inventory must be fully reversed before superseding. Source/rule revisions mark requirements stale and suppress current shortage. Purchase previews and approvals write no finance data. Purchase snapshot `current`/`basis_stale` rechecks its quantity/stock snapshot and approval digest; the root financial handoff must recheck at its current as_of and independently authorize the financial transaction.

## Verification evidence

Requested scoped command only:

```
QT_QPA_PLATFORM=offscreen ../p4-venv/bin/python scripts/run_offline_tests.py -q tests/test_phase4_site_materials.py
```

The initial requested command was blocked because the virtualenv interpreter link was missing. The coordinator restored it. Before restoration the same offline runner was usable through primary Python plus the existing virtualenv site-packages; no installation or outbound connection was used. Initial absent-domain RED captured 29 failed cases; the initial draft had been written while the interpreter issue was unresolved, so this first group is test-first authoring with delayed RED execution rather than a strict pre-implementation RED cycle. Subsequent behavioral additions used observed failing assertions before their fixes: 4 failed/32 passed (scope, reversal chain, historical coverage, inferred correction); 2 failed/36 passed (single common stock allocation, reversed supersession); final 4 failed/38 passed (purchase freshness, OPS, AI rejection, canonical specialist metadata). One earlier test's ledger-row count oracle was corrected from 8 to the actual seven preserved records.

Reviewer zero-opening correction regression RED: 1 failed/42 passed; fixed inferred zero-quantity reversal without changing the original opening. Final fresh requested command: **43 passed in 0.37s**, exit 0. Offline runner confirmed native connect/send syscalls blocked. Cases cover concrete/block/tile/pipe exact independent oracles, multiple BOQ quantities and entire source sets, partial delivery/consume/reserve, both return directions/caps and reversal chains, missing opening/coverage, explicit zero, unconfirmed legacy, incompatible units, duplicate references and physical allocation, stale BOQ/rules, evidence tampering, high precision, read-only snapshot, cross-project transplant, historical negative stock, missing price, price evidence/currency, independent review/approval, no financial side effects, canonical legacy/specialist approval and unreviewed AI rejection.

No full regression was run, per brief. No UI/Windows/Office verification or export is claimed by this scoped worker. Root integration owns the authorized finance handoff and the shared transaction/UI path. No automatic unit conversion, retroactive reassignment of active consumption to a revised need, or supplier-order transmission is implemented.
