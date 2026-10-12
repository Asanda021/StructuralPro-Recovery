# StructuralPro Third-Party Compliance Inventory

This inventory records what is currently declared by the repository and what still requires release-time evidence.

## Direct Python dependencies

| Component | Declared source | License evidence | Commercial release status |
|---|---|---|---|
| pypdf | requirements.txt | Verify upstream package metadata at release | Pending release evidence |
| PySide6 | requirements.txt | Verify upstream package/commercial terms at release | Pending release evidence |
| ezdxf | Optional/commented | Verify only if enabled/bundled | Not bundled by default |
| ifcopenshell | Optional/commented | Verify only if enabled/bundled | Not bundled by default |

Transitive dependencies must also be captured from the exact release environment.

## External/bundled assets

| Asset | Current repository status | Required evidence |
|---|---|---|
| GGUF model weights | Not committed | Model license + checksum + redistribution permission |
| DWG converter/SDK | Not bundled by default | Vendor license + redistribution/runtime terms |
| Official price-list datasets | External/verified source required | Source provenance + usage/redistribution rights |
| Windows code-signing certificate | Not committed | Certificate ownership + secure signing procedure |

This file is an inventory template, not a claim that commercial redistribution rights have already been obtained.
