# P96 — Final Product Gap Audit

This audit freezes the evidence-based baseline before deeper production work.

## Findings
- The repository already contains quantity, drawing, BIM/IFC, BOQ/estimate, reporting, revision, collaboration, AI, client-contract and validation foundations.
- The remaining gaps are production-depth gaps, not missing-module gaps: deeper deterministic engineering quantity scenarios, editable drawing production workflow, IFC round-trip fidelity, one complete takeoff-to-estimate acceptance path, versioned Iranian data-pack provenance, report packaging, revision impact propagation, larger golden datasets, and release hardening.
- External commercial dependencies must remain explicit: licensed official Iranian price-list files, a redistributable DWG engine, optional IfcOpenShell runtime, licensed GGUF weights, and Windows signing credentials.

## Production-depth priorities
- **P97** — deep deterministic engineering quantity scenarios.
- **P98** — editable drawing production workflow.
- **P99** — IFC/BIM round-trip fidelity.
- **P100** — end-to-end takeoff → BOQ → estimate acceptance.
- **P101** — versioned Iranian engineering/pricing data-pack provenance.
- **P102** — professional report/export bundle.
- **P103** — revision impact propagation and review closure.
- **P104** — expanded golden/project validation dataset.
- **P105** — production hardening, performance and release readiness.

## P96 acceptance
A gap is accepted only when it has:
1. a concrete repository surface,
2. deterministic tests,
3. a dedicated CI gate,
4. regression coverage,
5. Main verification after merge.

This document is the baseline for P97–P105.
