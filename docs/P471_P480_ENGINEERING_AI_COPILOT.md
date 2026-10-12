# P471–P480 — Engineering AI Copilot

## Purpose
Create an evidence-first copilot boundary for engineering workflows across the whole AEC/building domain.

## Rules
- Input must carry explicit intent, context and evidence.
- Evidence must preserve source identity and revision.
- Only accepted evidence can drive a copilot response.
- Copilot output is a proposal/review artifact, not an automatic engineering calculation or data mutation.
- No hidden coefficients, invented dimensions, prices, quantities or standards.
- Every response is deterministic and fingerprintable.

## Scope
This phase establishes the production contract for explain/propose/review interactions. Model execution, local GGUF packaging and domain-specific automation remain bounded by the existing production/licensing gates.
