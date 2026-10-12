# CAD production boundary

StructuralPro now has one explicit production CAD boundary.

- DXF: real parsing is bundled through ezdxf; the test creates an actual DXF file, writes it, reopens it, and validates the parsed entities.
- DWG: the application does not pretend that a DXF library is a DWG parser. DWG is accepted only through an explicitly configured provider that the deployment owner has authorized.
- No guessing: unsupported or unauthorized CAD input fails closed.
- Provider replacement: an authorized DWG implementation can be injected without changing takeoff or BOQ code.

This prevents an unlicensed parser from silently entering a commercial build while keeping the CAD API production-ready.
