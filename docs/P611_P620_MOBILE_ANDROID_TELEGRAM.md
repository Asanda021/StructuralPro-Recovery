# P611–P620 — Mobile / Android / Telegram Production Clients

This phase defines a production-safe client boundary for Android and Telegram.

## Rules
- Clients transport explicit project/revision/operation payloads.
- Engineering values are never inferred by the client.
- Every request has a deterministic identity and fingerprint.
- Evidence references are explicit when provided.
- Payload size is bounded.
- Protocol versions are explicit and fail closed.
- Offline capability is advertised, not assumed.

The Android shell and Telegram adapter must consume this contract rather than duplicate engineering logic.
