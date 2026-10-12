# Production Release Evidence Closure

This document closes the repository-side work for the production evidence boundary without fabricating external legal or customer evidence.

## Evidence classes

| Evidence | Repository automation | External proof required |
|---|---|---|
| Customer artifact | Windows installer build, smoke test, SHA-256 manifest, release registry | A real customer-facing release artifact from the release environment |
| Entitlement authorization | Release registry is fail-closed with `entitlement_required` | A real ERVIRA customer entitlement/license authorization record |
| Pricebook provenance | P100 records source/provenance and is explicit/manual | Proof that each redistributed dataset is licensed/authorized for commercial redistribution |
| Third-party licenses | Exact Windows build emits `StructuralPro-third-party-licenses.csv` + `pip-freeze` | Human/legal review of the exact release inventory and any redistribution obligations |
| DWG runtime terms | Explicit optional evidence slot | Vendor license/redistribution/runtime terms if a converter SDK is shipped |
| Code signing | Explicit optional evidence slot | Real certificate and signing procedure if signed binaries are required |

## Release policy

The project must **not** mark `release_ready=true` merely because a repository fixture or CI output exists.

Required external evidence must be supplied as real, non-empty evidence files and is SHA-256 fingerprinted by the production readiness evaluator.

### Pricebook rule

Public availability is not treated as redistribution permission. An annual Iranian pricebook is release-eligible only when its provenance and redistribution authorization are documented.

### Third-party dependency rule

The Windows release inventory is generated from the exact build environment. Any package whose license cannot be identified must block commercial release until reviewed.

### Customer entitlement rule

CI never invents or synthesizes a customer authorization. ERVIRA must provide the actual entitlement record for the customer/product/version.

## What is now fully automated

- Windows installer creation and validation.
- Installed application smoke acceptance.
- SHA-256 artifact verification.
- Release manifest and release registry.
- Exact dependency/license inventory.
- Fail-closed production readiness evaluation.
- Explicit separation of external P100 data availability from normal Main CI.

## What cannot legitimately be solved by source-code changes

The following are legal/commercial facts, not software defects:

1. A real customer entitlement issued by ERVIRA.
2. Commercial redistribution permission for official/licensed pricebook datasets.
3. Vendor redistribution/runtime permission for any proprietary DWG converter.
4. A real Windows code-signing certificate, if signing is required.

These must come from the actual rights holder/account and cannot be manufactured by CI.

## Closure criterion

Once the real external evidence is placed into the production evidence set, the existing fail-closed evaluator can determine readiness without another roadmap phase.
