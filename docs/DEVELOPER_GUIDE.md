# StructuralPro Developer Guide

## Architecture principles

1. Prefer the existing core/data contracts over parallel implementations.
2. Keep deterministic engineering calculations separate from AI/advisory layers.
3. Preserve offline-first behavior for core workflows.
4. Keep release metadata centralized in VERSION and core/platform/release.py.
5. Do not embed license signing secrets in the desktop application.
6. Make import/export deterministic and validate external data at the boundary.
7. Add regression tests with every behavioral change.

## Repository areas

- core/ — domain logic, project data and platform services.
- app/ — desktop/application entry and UI.
- packaging/ — Windows build and installer definitions.
- tests/ — automated unit, integration, regression and production-gate tests.
- docs/ — product, production and release documentation.
- models/ — local-model boundary; large model weights are intentionally not committed.
- android/ and mobile/ — client/runtime boundaries and shared contracts.

## Development workflow

1. Start from the current main commit.
2. Create a focused branch.
3. Inspect existing implementations before adding code.
4. Reuse existing services/contracts.
5. Implement the smallest coherent change.
6. Add or update tests.
7. Run the focused tests and the full regression suite.
8. Inspect failures and fix root causes.
9. Review the diff for accidental duplication or release regressions.
10. Open a PR.
11. Review CI and PR changes.
12. Merge only after the required gates are green.
13. Re-check main after merge.

## Testing expectations

At minimum, changes should preserve:
- Python compilation;
- existing unit/integration tests;
- production-gate tests;
- deterministic import/export behavior;
- integrity/audit/revision guarantees;
- Windows packaging validation when release surfaces change.

A green test suite does not prove that third-party licenses, proprietary datasets, external converters or model weights have been provisioned.

## Release-sensitive changes

Changes to VERSION, packaging scripts, installer templates, release workflows, license primitives or user-facing release documentation must be reviewed together. Avoid creating a second version source or second license authority.

## Code quality

Use clear names, small deterministic functions and explicit validation. Prefer fail-closed behavior for release and license validation. Do not silently fabricate engineering quantities, official prices or external provisioning.

## Documentation rule

When a user-visible workflow, configuration key, release behavior or operational requirement changes, update the corresponding documentation and regression coverage in the same change.
