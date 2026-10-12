# Open CAD/PDF provider policy

StructuralPro now uses an evidence-first provider boundary for drawing ingestion.

## DXF

The repository already depends on ezdxf; this change makes it an explicit
runtime provider rather than a mocked metadata path. A real DXF file is parsed
with ezdxf, and model-space entities, layers and document version are exposed
as evidence.

ezdxf is MIT-licensed and supports reading/writing DXF. It is not treated as a
native DWG parser.

## DWG

No proprietary DWG SDK is bundled. The provider boundary therefore rejects DWG
unless an authorized DWG provider is explicitly installed/configured. This is
intentional: a .dwg filename must never be treated as proof that its contents
were parsed.

## PDF

PyMuPDF is used to open a real PDF and obtain vector drawing evidence. The
measurement engine requires explicit calibration tied to the same source.
Missing or invalid calibration fails closed; no scale or quantity is guessed.

## Release consequence

This removes the need to ship a commercial DWG SDK for the open/evaluation
product path while preserving a replaceable provider boundary for a future
commercially authorized DWG provider.

It does not grant redistribution rights for official Iranian pricebooks. Those
remain provenance/authorization controlled and user-importable.

## Verification

The dedicated tests create and parse a real DXF and a real PDF during CI. They
also verify that unsupported DWG input fails closed.
