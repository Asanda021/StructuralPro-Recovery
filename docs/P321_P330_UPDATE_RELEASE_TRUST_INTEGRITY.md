# P321-P330 — Update / Release Trust Integrity

- P321 release manifest construction
- P322 artifact hash and size binding
- P323 manifest self-integrity fingerprint
- P324 current-version / downgrade protection
- P325 channel binding
- P326 artifact-byte verification
- P327 fail-closed malformed manifest handling
- P328 release-security boundary reuse
- P329 regression coverage
- P330 dedicated production gate

The implementation reuses the existing update validator and static release-security
scanner. It does not add network download behavior or bypass existing security gates.
