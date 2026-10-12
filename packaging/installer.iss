; StructuralPro Inno Setup installer template.
; VERSION is injected into the stable installer placeholder by the release workflow.
#define MyAppName "StructuralPro"
#define MyAppVersion "__VERSION__"
#define MyAppExeName "StructuralPro.exe"
[Setup]
AppId={{E2E3D4D5-7C21-4A1A-9D4A-123456789ABC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\StructuralPro
DefaultGroupName=StructuralPro
OutputDir=..\dist
OutputBaseFilename=StructuralPro-{#MyAppVersion}-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
[Files]
Source: "..\dist\StructuralPro\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\StructuralPro"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\StructuralPro"; Filename: "{app}\{#MyAppExeName}"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch StructuralPro"; Flags: nowait postinstall skipifsilent
