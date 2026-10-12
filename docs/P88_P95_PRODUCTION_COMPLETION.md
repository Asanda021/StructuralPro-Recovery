# P88–P95 — Production Completion Block

This block closes the operational gap between pricebook source registration and release readiness.

- P88: normalize imported pricebook rows before pricing.
- P89: require year/discipline coverage and provenance.
- P90: provide a deterministic takeoff → price end-to-end gate.
- P91: fail closed unless the Iranian benchmark reaches green2.
- P92: preserve source/year/discipline isolation in the E2E path.
- P93: validate the real Windows release contract.
- P94: validate the collaboration event contract.
- P95: produce one deterministic release-candidate fingerprint only when all gates pass.

No fabricated price rows are embedded. Real artifacts must be downloaded, hashed and supplied to the gates before a release can be declared production-ready.
