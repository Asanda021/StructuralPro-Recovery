#define MyAppName "StructuralPro __EDITION__"
#define MyAppVersion "__VERSION__"
#define MyEdition "__EDITION__"
#define MyAppId "StructuralPro-__EDITION__"
#define MyAppExeName "StructuralPro.exe"
[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\StructuralPro\{#MyEdition}
DefaultGroupName=StructuralPro {#MyEdition}
OutputDir=..\dist
OutputBaseFilename=StructuralPro-{#MyEdition}-{#MyAppVersion}-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
[Files]
Source: "..\dist\StructuralPro\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\StructuralPro {#MyEdition}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\StructuralPro {#MyEdition}"; Filename: "{app}\{#MyAppExeName}"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch StructuralPro {#MyEdition}"; Flags: nowait postinstall skipifsilent
