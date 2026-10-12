# Versioning and Release Process

## Version source

VERSION is the single canonical application version.

Current repository version at this documentation baseline: 0.1.0.

Use semantic MAJOR.MINOR.PATCH formatting.

## Release preparation

1. Decide the intended release version.
2. Update VERSION.
3. Update release notes/documentation.
4. Run focused and full tests.
5. Run production-gate tests.
6. Validate packaging and installer surfaces.
7. Review license/dependency requirements.
8. Commit the release preparation.
9. Create a matching v<version> tag.
10. Run the Windows release workflow.
11. Verify the produced EXE and installer artifacts.
12. Publish the release only after the actual build evidence is available.

## Tag rule

The Windows workflow is designed for v* tags and validates that the tag version matches VERSION. A mismatched tag must not be treated as a valid release.

## Build evidence

Record:
- source commit;
- VERSION;
- tag;
- workflow run ID/status;
- EXE presence;
- packaged VERSION;
- installer presence;
- installer filename;
- artifact/checksum information where available.

## Patch/minor/major intent

- PATCH: backward-compatible bug fixes and documentation/maintenance changes.
- MINOR: backward-compatible functionality additions.
- MAJOR: incompatible public contract or data-model changes.

If a change has migration or compatibility impact, document it explicitly instead of relying on the version number alone.
