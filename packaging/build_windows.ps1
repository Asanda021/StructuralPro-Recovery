param([string]$Version="", [switch]$BuildInstaller, [switch]$SmokeTest)
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$canonicalVersion=(Get-Content VERSION -Raw).Trim()
if (-not $Version) { $Version=$canonicalVersion }
if ($Version -ne $canonicalVersion) { throw "Requested build version '$Version' does not match VERSION '$canonicalVersion'" }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid VERSION format: $Version" }

python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed with exit code $LASTEXITCODE" }
python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed with exit code $LASTEXITCODE" }
python -m PyInstaller --noconfirm --clean packaging/structuralpro.spec --distpath dist/StructuralPro --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed with exit code $LASTEXITCODE" }

$exe="dist/StructuralPro/StructuralPro.exe"
$embedded="dist/StructuralPro/VERSION"
dotnet restore tools/acadsharp-dwg-bridge/StructuralPro.DwgBridge.csproj
if ($LASTEXITCODE -ne 0) { throw "DWG bridge restore failed with exit code $LASTEXITCODE" }
dotnet publish tools/acadsharp-dwg-bridge/StructuralPro.DwgBridge.csproj -c Release -r win-x64 --self-contained true /p:PublishSingleFile=true /p:IncludeNativeLibrariesForSelfExtract=true --output dist/StructuralPro/dwg-bridge
if ($LASTEXITCODE -ne 0) { throw "DWG bridge publish failed with exit code $LASTEXITCODE" }
if (-not (Test-Path "dist/StructuralPro/dwg-bridge/StructuralPro.DwgBridge.exe")) { throw "ACadSharp DWG bridge was not published" }
Copy-Item "tools/acadsharp-dwg-bridge/README.md" "dist/StructuralPro/dwg-bridge/README.md" -Force
Copy-Item "third_party/ACADSHARP_LICENSE.txt" "dist/StructuralPro/dwg-bridge/ACADSHARP_LICENSE.txt" -Force

if (-not (Test-Path $exe)) { throw "PyInstaller did not create $exe" }
Copy-Item VERSION $embedded -Force
if (-not (Test-Path $embedded)) { throw "Packaged VERSION is missing" }
$packagedVersion=(Get-Content $embedded -Raw).Trim()
if ($packagedVersion -ne $canonicalVersion) { throw "Packaged VERSION '$packagedVersion' does not match canonical VERSION '$canonicalVersion'" }

if ($SmokeTest) {
    $env:STRUCTURALPRO_SMOKE="1"
    & $exe
    if ($LASTEXITCODE -ne 0) { throw "Windows packaged smoke test failed with exit code $LASTEXITCODE" }
    Remove-Item Env:STRUCTURALPRO_SMOKE -ErrorAction SilentlyContinue
}

$installer=""
if ($BuildInstaller) {
    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $iscc) { throw "BuildInstaller requested but ISCC.exe (Inno Setup) is not installed." }
    $iss="packaging/installer.iss"
    $tempIss="build/installer-$canonicalVersion.iss"
    New-Item -ItemType Directory -Force (Split-Path $tempIss) | Out-Null
    (Get-Content $iss -Raw).Replace("__VERSION__",$canonicalVersion) | Set-Content $tempIss -Encoding UTF8
    & $iscc.Source $tempIss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
    $installer="dist/StructuralPro-$canonicalVersion-Setup.exe"
    if (-not (Test-Path $installer)) { throw "Installer was not created at $installer" }
}

$shaFile="dist/StructuralPro-$canonicalVersion-SHA256.txt"
$targets=@($exe)
if ($installer) { $targets += $installer }
$hashes=foreach ($target in $targets) {
    $h=Get-FileHash $target -Algorithm SHA256
    "$($h.Hash.ToLower())  $([IO.Path]::GetFileName($target))"
}
$hashes | Set-Content $shaFile -Encoding ASCII

Write-Host "StructuralPro Windows payload built and version-validated: $canonicalVersion"
if ($installer) { Write-Host "Installer built: $installer" }
Write-Host "Checksums: $shaFile"
