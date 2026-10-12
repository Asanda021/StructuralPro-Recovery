param(
  [string]$OutputPath = "dist/StructuralPro-ReleaseManifest.json"
)
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$version=(Get-Content VERSION -Raw).Trim()
$tag=$env:GITHUB_REF_NAME
$commit=$env:GITHUB_SHA
$runId=$env:GITHUB_RUN_ID
$runAttempt=$env:GITHUB_RUN_ATTEMPT
$runnerOs=$env:RUNNER_OS
$runnerArch=$env:RUNNER_ARCH

if (-not $commit) { $commit="local" }
if (-not $tag) { $tag="local" }

$exe="dist/StructuralPro/StructuralPro.exe"
$embedded="dist/StructuralPro/VERSION"
$installer="dist/StructuralPro-$version-Setup.exe"
$checksums="dist/StructuralPro-SHA256SUMS.txt"

foreach ($file in @($exe,$embedded,$installer,$checksums)) {
  if (-not (Test-Path $file)) { throw "Release manifest input missing: $file" }
}

$packagedVersion=(Get-Content $embedded -Raw).Trim()
if ($packagedVersion -ne $version) { throw "Manifest version mismatch: packaged=$packagedVersion canonical=$version" }

$artifactInfo=[ordered]@{}
foreach ($file in @($exe,$embedded,$installer,$checksums)) {
  $artifactInfo[$file]=[ordered]@{
    sha256=(Get-FileHash -Algorithm SHA256 $file).Hash.ToLowerInvariant()
    size_bytes=(Get-Item $file).Length
  }
}

$manifest=[ordered]@{
  schema="structuralpro.release-manifest.v1"
  product="StructuralPro"
  version=$version
  tag=$tag
  source_commit=$commit
  workflow_run_id=$runId
  workflow_run_attempt=$runAttempt
  runner_os=$runnerOs
  runner_arch=$runnerArch
  packaged_version=$packagedVersion
  artifacts=$artifactInfo
}

New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath) | Out-Null
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $OutputPath
Write-Host "Wrote $OutputPath"