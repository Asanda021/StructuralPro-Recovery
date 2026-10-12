# DWG Production Provider

StructuralPro now uses a real CAD library behind a small Windows bridge:

DWG -> ACadSharp DwgReader -> CadDocument -> DxfWriter -> verified DXF -> ezdxf -> extraction/takeoff

## Why ACadSharp

ACadSharp is MIT-licensed and documents DWG reading for AC1014, AC1015, AC1018, AC1021, AC1024, AC1027 and AC1032. StructuralPro uses its reader and writer through a dedicated .NET 8 bridge.

This replaces the previous ODA File Converter boundary. No ODA executable is required and no converter is downloaded at runtime.

## Production deployment

The Windows release publishes the bridge project for win-x64 and ships StructuralPro.DwgBridge.exe with the application.

The Python side can also be pointed at an explicitly installed bridge with STRUCTURALPRO_DWG_BRIDGE.

If the bridge is missing, conversion fails closed. There is no fallback to guessed scale, guessed geometry, or an unrelated converter.

## Integrity rules

- Only .dwg input is accepted.
- ACadSharp must exit successfully.
- A non-empty DXF artifact must be produced.
- The generated DXF is parsed by the existing real ezdxf engine before it enters the takeoff pipeline.
- Bridge errors, timeouts, missing output, or invalid DXF fail closed.

## Verification

The dedicated Windows smoke test builds the bridge and exercises real ACadSharp reads on representative DWG files from AC1014 through AC1032, then parses every produced DXF with ezdxf.
