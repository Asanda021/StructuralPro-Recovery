# StructuralPro DWG Bridge - ACadSharp

Flow:

DWG -> ACadSharp DwgReader -> CadDocument -> DxfWriter -> verified DXF -> StructuralPro/ezdxf

This .NET 8 bridge is the production boundary between the Python StructuralPro application and the MIT-licensed ACadSharp DWG reader.

The release pipeline should publish this project for win-x64 and ship the resulting executable with the Windows application. The Python adapter never downloads a converter at runtime.

ACadSharp documents DWG reader support for AC1014, AC1015, AC1018, AC1021, AC1024, AC1027 and AC1032.
