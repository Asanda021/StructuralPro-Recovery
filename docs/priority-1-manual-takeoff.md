# Priority 1 — Professional Manual Takeoff

## Implemented in this slice
- Project-scoped and floor-scoped manual takeoff register.
- Reuses the deterministic TakeoffEngine; no separate quantity formula is introduced.
- Preserves original input text, normalized parameters, item identity, formula, unit, quantity, and draft status for traceability.
- Returns a draft with exact missing fields when geometry is incomplete.
- Project defaults are applied only when the caller explicitly lists each field in confirmed_default_fields; there is no silent default guessing.
- Supports semicolon batch entry and undo/redo of register changes.
- Current mappings: columns, beams, tie beams, footings, shear walls, solid slabs, joist-block/foam roofs, stairs, walls, excavation, rebar, and steel.

## Explicit limits
- The Persian Windows UI now exposes a project-linked manual takeoff dialog from Quick Takeoff. It previews complete entries and saves them through `StructuralProApp.add_takeoff`, preserving the floor as the system and a unique source ID.
- Incomplete entries are shown as drafts and are not persisted. Saving is retry-safe within the dialog session: already saved rows are not submitted twice.
- The dialog supports clipboard paste, pending-row edit/re-entry, row copy, copy-to-floor, reversible pending-row deletion, undo/redo, and an append-only project audit timeline (bounded to the latest 500 events). Saved rows are deliberately protected from destructive edits in this dialog; use the project management path for persisted-record changes. Assembly-template expansion and a revision-safe editor for persisted rows remain outstanding.
- Rebar/steel quantities are only valid when length and unit weight inputs are supplied; schedules are not inferred.
- Unknown or incomplete fields are not fabricated.

## Acceptance checks
1. A complete entry calculates with the existing deterministic engine.
2. Incomplete entry returns a draft and does not create a quantity record.
3. Project defaults require explicit per-field confirmation.
4. Batch entry, undo/redo, reversible deletion, UI controls, clipboard flow, and source traceability are covered by tests.