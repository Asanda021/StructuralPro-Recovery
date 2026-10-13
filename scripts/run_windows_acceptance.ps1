# Run manually on trusted Windows desktop with dependencies already installed.
# Source-only, no installer, no GitHub Actions, no build, no publication.
[CmdletBinding()]
param([string]$OutputDir = "qa\windows")
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
  python scripts/windows_acceptance_gate.py --repo "$root" --out-dir "$OutputDir"
  if ($LASTEXITCODE -ne 0) {
    throw "Windows acceptance not yet passed. Inspect $OutputDir\windows_acceptance.json"
  }
  Write-Host 'Technical GUI/PDF smoke succeeded. Human visual approval still REQUIRED.'
} finally { Pop-Location }
