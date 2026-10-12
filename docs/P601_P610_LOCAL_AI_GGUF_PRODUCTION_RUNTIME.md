# P601-P610 — Local AI / GGUF Production Runtime

This phase establishes a production-safe local AI boundary. Model weights are external artifacts and are never downloaded by application code.

## Production gates
1. Manifest format must be GGUF.
2. Exactly one production model must be declared.
3. The artifact must exist locally.
4. Complete artifact SHA-256 must match the manifest.
5. A non-empty license must be recorded.
6. Commercial-use permission must be explicitly true.
7. Internet access is not a runtime requirement.
8. Missing, changed, unlicensed, or unverified artifacts fail closed.
9. Deterministic engineering calculations remain outside the AI layer.
10. AI output is advisory and must not invent engineering values.

The existing LocalAIEngine remains available. This phase adds a stricter artifact gate rather than silently trusting the first GGUF file found on disk.

Before real production deployment, replace the placeholder manifest only after licensing and SHA-256 verification. No model weights are committed to GitHub.
