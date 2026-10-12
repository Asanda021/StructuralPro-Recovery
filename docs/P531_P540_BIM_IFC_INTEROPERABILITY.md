# P531–P540 — BIM / IFC Interoperability & Round-trip

## Purpose
Provide a deterministic, evidence-first interoperability boundary for IFC records and round-trip verification.

## Contract
- IFC version is explicit; unsupported versions fail closed.
- Project, revision, source, discipline, external identity and element type are mandatory.
- Properties and quantities are carried as immutable evidence; this layer does not invent geometry or quantities.
- A deterministic fingerprint protects the interchange identity.
- Round-trip verification rejects identity, project/revision, or fingerprint drift.
- This contract is an interoperability boundary, not an IFC geometry parser or engineering calculation engine.
