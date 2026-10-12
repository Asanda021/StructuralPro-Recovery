param([Parameter(Mandatory=$true)][string]$Version,[Parameter(Mandatory=$true)][ValidateSet("light","standard","pro","enterprise")][string]$Edition)
$ErrorActionPreference="Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$canonicalVersion=(Get-Content VERSION -Raw).Trim()
if ($Version -ne $canonicalVersion) { throw "Requested version '$Version' does not match VERSION '$canonicalVersion'" }
& "$PSScriptRoot/build_windows.ps1" -Version $Version
if ($LASTEXITCODE -ne 0) { throw "Base Windows payload build failed" }
$payload="dist/StructuralPro"
if (-not (Test-Path "$payload/StructuralPro.exe")) { throw "Missing Windows executable" }
Set-Content "$payload/EDITION" -Value $Edition -Encoding ascii
Set-Content "$payload/EDITION_VERSION" -Value "$Edition@$Version" -Encoding ascii

# AI is embedded into the same StructuralPro installation for AI-enabled editions.
if ($Edition -ne "light") {
  & "$PSScriptRoot/fetch_embedded_ai_assets.ps1" -Payload $payload -Edition $Edition
  if ($LASTEXITCODE -ne 0) { throw "Embedded AI asset preparation failed" }
} else {
  New-Item -ItemType Directory -Force "$payload/models","$payload/ai_runtime" | Out-Null
  @{
    edition=$Edition; ai_tier="none"; runtime=$null; model=$null; mmproj=$null; offline=$true
  } | ConvertTo-Json | Set-Content "$payload/AI_MODEL_PROFILE.json" -Encoding utf8
}

# Fail closed if the embedded AI payload is incomplete. These checks run before
# Inno Setup so an installer can never be produced with a broken AI edition.
$aiProfile = Get-Content "$payload/AI_MODEL_PROFILE.json" -Raw | ConvertFrom-Json
if ($aiProfile.edition -ne $Edition) { throw "AI profile edition mismatch" }
if ($Edition -eq "light") {
  if (@(Get-ChildItem "$payload/models" -Filter "*.gguf" -File -ErrorAction SilentlyContinue).Count -ne 0) { throw "Light edition must not contain AI model files" }
  if (Test-Path "$payload/ai_runtime/llama-cli.exe") { throw "Light edition must not contain AI runtime" }
} else {
  if (-not (Test-Path "$payload/ai_runtime/llama-cli.exe")) { throw "Embedded llama-cli.exe missing" }
  if (@(Get-ChildItem "$payload/ai_runtime" -Filter "*.dll" -File -ErrorAction SilentlyContinue).Count -eq 0) { throw "Embedded llama.cpp DLL dependencies missing" }
  if (-not (Test-Path "$payload/models/$($aiProfile.model)")) { throw "Embedded AI model missing" }
  if ($Edition -in @("pro","enterprise")) {
    if (-not (Test-Path "$payload/ai_runtime/llama-mtmd-cli.exe")) { throw "Embedded multimodal runtime missing" }
    if (-not $aiProfile.mmproj -or -not (Test-Path "$payload/models/$($aiProfile.mmproj)")) { throw "Embedded vision projector missing" }
  }
}
$template=Get-Content "$PSScriptRoot/installer-edition.iss" -Raw
$generated=$template.Replace("__VERSION__",$Version).Replace("__EDITION__",$Edition)
$generatedPath="build/installer-$Edition-$Version.iss"
New-Item -ItemType Directory -Force build | Out-Null
Set-Content $generatedPath -Value $generated -Encoding utf8

# Resolve Inno Setup robustly across standard Windows and Chocolatey installs.
$isccCandidates=@(
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ChocolateyInstall\lib\innosetup\tools\ISCC.exe",
  "$env:ChocolateyInstall\lib\innosetup.install\tools\ISCC.exe"
)
$isccPath=$isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $isccPath) {
  $isccCommand=Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($isccCommand) { $isccPath=$isccCommand.Source }
}
if (-not $isccPath) {
  $searchRoots=@($env:ProgramFiles,${env:ProgramFiles(x86)},$env:ChocolateyInstall)
  foreach ($root in $searchRoots | Where-Object { $_ -and (Test-Path $_) }) {
    $found=Get-ChildItem -Path $root -Filter ISCC.exe -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $isccPath=$found.FullName; break }
  }
}
if (-not $isccPath) { throw "Inno Setup compiler not found after installation" }
Write-Host "Using Inno Setup compiler: $isccPath"
& $isccPath $generatedPath
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
$installer="dist/StructuralPro-$Edition-$Version-Setup.exe"
if (-not (Test-Path $installer)) { throw "Edition installer missing: $installer" }
if ((Get-Item $installer).Length -lt 1024) { throw "Edition installer is implausibly small" }
if ((Get-Content "$payload/EDITION" -Raw).Trim() -ne $Edition) { throw "Edition marker mismatch" }
Write-Host "Built StructuralPro $Edition edition $Version"
