param(
  [string]$ManifestPath = "dist/StructuralPro-ReleaseManifest.json",
  [string]$OutputPath = "dist/StructuralPro-ReleaseRegistry.json"
)
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path $ManifestPath)) { throw "Release manifest missing: $ManifestPath" }
$m=Get-Content $ManifestPath -Raw | ConvertFrom-Json
if ($m.product -ne "StructuralPro") { throw "Unexpected product" }
if ($m.version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid release version" }
foreach ($name in @("dist/StructuralPro/StructuralPro.exe","dist/StructuralPro/VERSION","dist/StructuralPro-$($m.version)-Setup.exe","dist/StructuralPro-SHA256SUMS.txt")) {
  if (-not (Test-Path $name)) { throw "Required release artifact missing: $name" }
}
$registry=[ordered]@{
  schema="structuralpro.release-registry.v1"
  product="StructuralPro"
  version=$m.version
  tag=$m.tag
  source_commit=$m.source_commit
  workflow_run_id=$m.workflow_run_id
  release_ready=$false
  delivery_state="ci_verified"
  download_authorization="entitlement_required"
  installed_version_detection="verified"
  artifacts=$m.artifacts
}
$registry | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $OutputPath
Write-Host "Wrote $OutputPath"
