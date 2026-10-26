# One Windows StructuralPro edition only. This is a release *procedure*, not approval.
# Never download unverified model weights, override an owner decision or build
# anything when owner approval is absent. -ValidateOnly performs no build.
param(
  [Parameter(Mandatory=$true)][string]$Version,
  [ValidateSet("unified")][string]$Edition = "unified",
  [Parameter(Mandatory=$true)][string]$AssetSource,
  [switch]$OwnerApproved,
  [switch]$ValidateOnly
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = (Get-Location).Path
$canonical = (Get-Content VERSION -Raw).Trim()
if ($Version -ne $canonical) { throw "Requested VERSION differs from canonical VERSION" }
if ($Edition -ne "unified") { throw "Only StructuralPro unified Windows edition is permitted" }
if (-not (Test-Path -LiteralPath $AssetSource -PathType Container)) {
  throw "A1 staged AI payload is missing; no model download is permitted"
}
$source = (Resolve-Path -LiteralPath $AssetSource).Path
# No build or installer before the full offline A1 gate passes.
python packaging/verify_unified_payload.py --asset-root $source
if ($LASTEXITCODE -ne 0) { throw "A1 source release preflight BLOCKED" }
if ($ValidateOnly) {
  Write-Host "StructuralPro unified A1 preflight passed; no binary or installer built"
  return
}
if (-not $OwnerApproved) { throw "Owner approval required; no EXE or release was generated" }
& "$PSScriptRoot/build_windows.ps1" -Version $Version
if ($LASTEXITCODE -ne 0) { throw "Windows payload build failed" }
$payload = "dist/StructuralPro"
if (-not (Test-Path "$payload/StructuralPro.exe")) { throw "Windows program missing" }
# Copy only prevalidated local assets; never fetch/download during build.
foreach ($directory in @("models", "ai_runtime")) {
  $from = Join-Path $source $directory
  if (-not (Test-Path -LiteralPath $from -PathType Container)) {
    throw "Staged assets directory missing: $directory"
  }
  Copy-Item -LiteralPath $from -Destination $payload -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $source "AI_RELEASE_MANIFEST.json") -Destination $payload -Force
Set-Content "$payload/EDITION" -Value "unified" -Encoding ascii
Set-Content "$payload/EDITION_VERSION" -Value "unified@$Version" -Encoding ascii
# Validated bytes must survive copying into the output unchanged.
python packaging/verify_unified_payload.py --asset-root $payload
if ($LASTEXITCODE -ne 0) { throw "A1 staged/packaged bytes changed or rights unverified" }
# Use the stable one-product installer; never the edition-suffixed template.
$template = Get-Content "$PSScriptRoot/installer.iss" -Raw
$generated = $template.Replace("__VERSION__", $Version)
New-Item -ItemType Directory -Force build | Out-Null
$generatedPath = "build/installer-$Version.iss"
Set-Content -LiteralPath $generatedPath -Value $generated -Encoding utf8
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) { throw "Inno Setup unavailable; no installer generated" }
& $iscc.Source $generatedPath
if ($LASTEXITCODE -ne 0) { throw "Unified installer compilation failed" }
$installer = "dist/StructuralPro-$Version-Setup.exe"
if (-not (Test-Path $installer)) { throw "Unified Windows installer missing" }
Write-Host "StructuralPro unified owner-approved release procedure finished"
