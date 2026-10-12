# StructuralPro — Beam detail takeoff implementation contract (2026-10-13)

**Scope:** Windows/PySide6, Persian-first UI, core takeoff + SQLite ProjectStore. Recovery repository only; not a release or sign-off.

## Fixed initial states

| Group | Initial state |
| --- | --- |
| Longitudinal / میلگرد طولی | `needs_detail` |
| Stirrups / خاموت | `needs_detail` |
| Side bars / کمرکش تیر | `unreviewed` |
| Crossties / سنجاقی | `unreviewed` |
| Additional bars / میلگرد تقویتی | `unreviewed` |

An unreviewed bar is never treated as absent or zero. `not_applicable` requires reviewer's name, explicit reason and detail reference.

## Operational contract

1. Reuse **existing** `core.projects.store.ProjectStore` (SQLite, revisions, backups), `core.takeoff.engine.TakeoffEngine`, `core.takeoff.boq.build_boq` and `core.drawings` graphical viewport. Never add competing data stores, calculation engines or BOQ pathways.
2. The graphical window retains the drawing next to `BeamDetailPanel`. A rectangle links a draft to source bytes SHA-256 + page + scene coordinates, **not** proof of automatic member/dimension recognition. Manual mode remains separate for projects without drawings.
3. Each beam is identified by (project, floor, beam tag). A drawing quantity source may be used only once. A shared *detail drawing* is not itself a unique quantity source.
4. Numeric entries require positive finite values; zero deduction must be **entered explicitly**. Concrete net volume uses canonical beam gross computation minus reviewed overlap deduction. Exposed formwork area is a reviewed input, not automatically inferred.
5. Each reinforcement group is individually confirmed or ruled not applicable. Confirmed groups require explicit bar count, reviewed **cut length** including applicable hooks, laps, bends, and unit mass; multi-zone segments are supported by the domain model.
6. Save incomplete projects as **drafts only**. An incomplete or unreviewed row is never transferred to official takeoffs, BOQ, estimate or reports. `commit` reruns all checks, rejects duplicate source IDs, and persists takeoffs+BOQ atomically with optimistic SQLite revision checking.
7. No official pricebook, AI-derived engineering quantity, automatic detail inference, or default scale is invented.

## Review boundaries

- The current graph selection is region-level provenance. **Automatic B1 -> beam schedule/section/rebar detail matching and automatic drawing-derived quantities are NOT complete.**
- GUI multi-zone rebar editing is not yet implemented (the domain model supports segments and blocks unsafe overwrite in the simple panel).
- Windows GUI runtime, real DWG/PDF quantity extraction, Persian PDF/Excel reports, five-story acceptance, and full regression **must be tested** before marking all 10 items complete.
- Recovery snapshot is not confirmed to be the latest original StructuralPro main; preserve source, do not merge into the original until reconciliation.
- The recovery repository currently has no active `.github/workflows/`; **do not enable GitHub Actions, builds, installers or releases** without owner approval.

## Acceptance scenarios to run on actual project

- B1 from DWG and PDF: open, zoom window, select, highlight; inspect provenance.
- B1 with all five initial statuses: draft saves/reopens in SQLite, BOQ unchanged.
- Complete reviewed B1: concrete with explicit overlap deductions; formwork; rebar by reviewed cut lengths, weights and approvals.
- Stirrups with multiple spacing zones: segment counts and lengths checked against actual details.
- Extra bars and crossties: verified applicable or verified absent; no implicit zeros.
- Duplicate B1, repeated drawing region, modified drawing hash, out-of-date revision: fail closed.
- Generated BOQ, Persian Excel and PDF: verified numerically, RTL and lossless descriptions.
- Windows high-DPI layout and large DWG test; no change to existing source or user data on import failures.

## Deployment policy

**No executable build, installer, release, merge or workflow activation without explicit owner approval.** This is draft development on a separate feature branch.
