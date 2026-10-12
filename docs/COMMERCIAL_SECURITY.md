# Commercial Readiness Security Gates

## Licensing
- Private signing keys stay outside source code, desktop packages and CI logs.
- The client verifies licenses through an injected verifier and public verification material.
- Production activation must define issuer, signature algorithm, expiration, entitlements and revocation/support policy.
- Verification fails closed for malformed, incomplete or unsupported licenses.

## Secrets
Credentials must be supplied through secure runtime/build mechanisms, never committed to the repository. Release security tests scan supported source and packaging surfaces for common embedded-secret patterns.

## Dependencies and third-party assets
Before commercial distribution, maintain evidence for:
- Python dependency licenses and versions;
- bundled converters/SDKs;
- local GGUF model licenses and checksums;
- price-list/catalog data rights;
- code-signing certificates and signing policy, if enabled.

The application must not claim a third-party entitlement that has not been verified.

## Release artifacts
Record the source commit, VERSION, tag, workflow result, installer artifact and checksum/signature evidence where applicable.

## Windows signing
Code signing is a commercial-release requirement when distribution policy requires a trusted publisher signature. The certificate/private key must be provisioned outside the repository and build logs.
