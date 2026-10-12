# P591-P600 — Multi-Discipline Coordination

Deterministic evidence boundary for coordination across Structural, Architectural, Mechanical, Electrical, Civil and General disciplines.

The engine stores explicit coordination records and evidence references. It does not infer geometry, clash severity, quantities, design adequacy, or engineering resolution.

Supported relations: overlap, near, aligned, connected, conflict.

Fail-closed requirements:
- all identities and evidence references are explicit
- supported discipline only
- relation vocabulary is explicit
- self-relations rejected
- duplicate records rejected
- deterministic canonical SHA-256 fingerprint
