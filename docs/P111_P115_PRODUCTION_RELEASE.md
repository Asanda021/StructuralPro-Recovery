# P111-P115 Production / Release Acceptance

## P111 — Iranian Official Data Boundary
The product validates version, provenance, checksum and license references through the IranDataPack contract. The acceptance fixture is explicitly controlled/sample data and is NOT an official Iranian annual price-list dataset. Official commercial data remains a release-time licensed provisioning dependency.

## P112 — Professional Office Reports
The acceptance flow generates Excel, PDF and DOCX outputs and verifies non-empty artifacts. Persian report columns and RTL-aware Excel/PDF/DOCX structures are exercised.

## P113 — Revision & Change Impact
A revision changes a quantity from 10 to 12 and the acceptance flow verifies propagated BOQ/cost impact and finalizability when review is approved.

## P114 — Large Project Performance
A 10,000-row project snapshot and pagination path are exercised. The system reports project scale and deterministic collection counts without claiming a universal performance benchmark.

## P115 — Production Packaging / Release
Release metadata is validated from VERSION, production hardening imports are checked, and existing Windows packaging/release gates remain part of the regression boundary.

## Important boundary
Green repository acceptance does not mean official Iranian data, third-party DWG/IFC runtimes, signing certificates, or other external commercial assets have been provisioned.
