# P31 — Commercial Readiness

P31 validates the product's commercial client boundary.

## Covered
- licensing lifecycle
- activation integrity and fail-closed revocation
- feature entitlements
- trial/demo entitlement model
- canonical versioning
- trusted update manifests and rollback/downgrade rejection
- migration
- backup/restore
- offline in-app documentation/help

## Boundary
This phase does not fabricate payment processing, cloud licensing, issuer
infrastructure, private signing keys, customer data, or network activation.
Those are external commercial services.

## Acceptance
Implementation → Tests → CI → Merge → Post-Merge Main Verification.
P31 is green only after all five are successful.
