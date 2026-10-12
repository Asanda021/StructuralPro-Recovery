# P511–P520 — Integration Ecosystem

## Purpose
Provide a deterministic integration envelope for AEC data exchange.

## Rules
- Every exchange carries project/source identity and revision.
- Supported formats are explicit; unsupported formats fail closed.
- Validation does not mutate engineering quantities.
- Payload identity is represented by a deterministic hash.
- Provider-specific adapters remain behind this shared contract.
