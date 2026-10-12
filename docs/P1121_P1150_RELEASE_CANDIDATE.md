# P1121–P1150 — Release Candidate

This phase establishes a deterministic, fail-closed release-candidate boundary.

## Gate
A candidate requires version, source commit, acceptance fingerprint, release-health fingerprint, production-boundary fingerprint, and a non-empty artifact-to-SHA256 map. Unknown or missing fields, malformed digests, and empty evidence block readiness.

## Verification
The dedicated workflow runs the focused pytest suite on Python 3.11. The phase is green only after the PR is merged and every post-merge Main workflow for the merge SHA succeeds.

## Scope
This gate prepares the repository for release preparation; it does not claim a production release by itself.
