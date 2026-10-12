param(
  [string]$OutputPath = "dist/StructuralPro-SHA256SUMS.txt"
)
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$version=(Get-Content VERSION -Raw).Trim()
$files = @(
  "dist/StructuralPro/StructuralPro.exe",
  "dist/StructuralPro/VERSION"
)

$installerPath="dist/StructuralPro-$version-Setup.exe"
if (-not (Test-Path $installerPath)) { throw "Expected installer not found: $installerPath" }
$files += $installerPath

foreach ($file in $files) {
  if (-not (Test-Path $file)) { throw "Required release artifact missing: $file" }
}

$lines = foreach ($file in $files) {
  $hash=(Get-FileHash -Algorithm SHA256 $file).Hash.ToLowerInvariant()
  "$hash  $($file.Replace((Get-Location).Path + '\',''))"
}
New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath) | Out-Null
$lines | Set-Content -Encoding UTF8 $OutputPath
Write-Host "Wrote $OutputPath"
