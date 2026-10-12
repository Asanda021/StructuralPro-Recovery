# StructuralPro Configuration

## Configuration principles

StructuralPro is offline-first. Core calculations and local project work should not require a network service.

Configuration should be explicit, validated and documented. Do not create a second configuration source when an existing setting/service already owns the behavior.

## Version

The canonical application version is stored in VERSION. Release metadata is exposed through core/platform/release.py.

## Local project data

Project data should remain under the application's supported local project/storage boundary. Backups and exported formal records should be stored separately from the installation directory.

## Local AI

The local AI boundary may use a GGUF model from the models/ area when one is available and validated.

Operational requirements:
- model format must be supported by the local runtime;
- model checksum should be recorded;
- model license must permit the intended use;
- hardware compatibility should be checked;
- deterministic calculation paths must remain available independently of AI.

## External services

Network synchronization, optional providers and external provisioning are not required for the core offline workflow. Credentials must never be committed to the repository.

## Logging

Logs should contain enough context to diagnose an operational failure without exposing passwords, access tokens, license signing secrets or other sensitive credentials.

## Release configuration

Packaging and installer configuration lives under packaging/. Release workflows live under .github/workflows/. Keep release configuration aligned with VERSION and do not hard-code a competing version.
