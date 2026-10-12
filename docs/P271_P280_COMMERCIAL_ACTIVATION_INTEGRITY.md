# P271-P280 Commercial Activation Integrity

Repository-backed scope: harden the existing offline commercial license lifecycle
without fabricating payment, issuer, key-management, or network activation
infrastructure.

- P271 Activation evidence contract
- P272 License identity binding
- P273 Product/version evidence
- P274 Entitlement integrity
- P275 Revocation policy boundary
- P276 Offline/provisioned channel boundary
- P277 Fail-closed activation decision
- P278 Deterministic activation fingerprint
- P279 Non-secret evidence boundary
- P280 Dedicated + regression production gate

This layer complements `core/platform/release.py`. It does not replace the
cryptographic signature verifier and never stores private signing material.
External issuer, payment, certificate/key management, and activation services
remain explicit infrastructure dependencies.
