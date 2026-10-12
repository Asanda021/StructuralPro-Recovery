# StructuralPro User Guide

## 1. Purpose

StructuralPro is an offline-first construction quantity takeoff, estimating, project-control and reporting application. Core engineering calculations and project data are designed to remain usable without an internet connection.

AI features are advisory only. Deterministic quantity and calculation engines remain authoritative.

## 2. Start a project

1. Launch StructuralPro.
2. Create a new project.
3. Enter the project name, identification data and applicable project metadata.
4. Save the project before importing drawings or entering quantities.
5. Use a descriptive project identifier so backups and exported reports can be traced to the correct project.

## 3. Takeoff workflow

1. Add the source drawing/document.
2. Verify the drawing scale and units.
3. Record linear, area and count measurements using the applicable takeoff workflow.
4. Keep source references/IDs attached to measured items where available.
5. Review quantities for duplicate sources, invalid values and unexpected negatives.
6. Save a revision before major changes.

## 4. BOQ and estimating

1. Map takeoff items to the applicable BOQ/price item.
2. Select a price source or enter an approved custom price.
3. Review price provenance and effective/version information.
4. Apply documented project factors or overrides.
5. Generate the estimate.
6. Compare estimates when evaluating revisions or price changes.

Do not treat an unverified dataset as an official price list.

## 5. Progress and payment statements

Use contract quantities and the current/previous/cumulative workflow to record progress. Review retention, advance recovery, deductions, payable amount and remaining contract quantity before issuing a statement.

## 6. Finance

Record parties, documents, entries, costs, receipts, payments and obligations against the project. Reconcile ledger information before relying on dashboard totals.

## 7. Project management

Use schedules, tasks, daily reports, resources, materials and meetings to maintain project status. Compare planned and actual progress regularly.

## 8. Quality, history and revisions

- Use Audit/History to trace material changes.
- Use Undo/Redo for reversible editing.
- Create a Revision before major scope or quantity changes.
- Use snapshots when an isolated state must be preserved.
- Run integrity checks when a project is imported, restored or migrated.

## 9. Backup and restore

Create a backup before:
- major imports;
- bulk price updates;
- structural/project-data changes;
- application upgrades;
- restoring another project state.

After restore, run integrity validation and inspect key project totals before continuing work.

## 10. Local AI

If a compatible GGUF model is installed, the local AI layer can inspect, classify, suggest and explain. AI output is not a substitute for deterministic engineering calculations and requires user review before being accepted into project data.

Large model weights are not committed to the repository. Only use models whose redistribution and commercial-use terms have been verified.

## 11. Export and reporting

Generate reports only after checking project revision, quantities, prices and financial totals. Preserve the exported file together with the project/revision identifier when it is used as a formal record.

## 12. Offline-first behavior

Core local work must not depend on an online service. Optional synchronization or external provisioning must be explicit. If an external dependency is unavailable, continue with local functionality where supported and record the dependency as a release/operational requirement.

## 13. Before delivery

Confirm:
- correct project and revision;
- source drawings and quantities reviewed;
- price provenance reviewed;
- BOQ totals reconciled;
- payment/finance totals reconciled where applicable;
- required backup exists;
- exported report opens correctly;
- unresolved validation warnings are understood.
