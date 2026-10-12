# P291-P300 — Cross-Client Parity Integrity

## Repository-derived scope
The repository already defines Windows, Android and Telegram client contracts, shared request/response structures, a capability manifest, Android build workflow and provider-neutral sync contracts. This phase hardens that boundary without duplicating engineering calculations in clients.

## Priority mapping
- P291 Shared capability evidence
- P292 Platform identity validation
- P293 Contract-version consistency
- P294 Duplicate platform detection
- P295 Cross-client capability parity validation
- P296 Shared command boundary
- P297 Invalid-client fail-closed behavior
- P298 Deterministic parity fingerprint
- P299 Android/Telegram contract regression coverage
- P300 Dedicated production gate

## Boundary
This phase does not claim that every capability is natively implemented on every client. It records implementation/contract/planned status explicitly and validates the shared boundary. Native Android UI and Telegram transport remain separate client surfaces.
