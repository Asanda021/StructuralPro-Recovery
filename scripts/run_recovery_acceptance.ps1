# Manual, source-only Windows acceptance. No Actions, executable build or release.
[CmdletBinding()]
param([string]$OutputDir = "qa\recovery-windows")
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
  $platform = (& python -c "import sys; print(sys.platform)").Trim()
  if ($LASTEXITCODE -ne 0 -or $platform -ne 'win32') {
    throw 'BLOCKED_NOT_WINDOWS: real Windows is required.'
  }
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
  python scripts/run_quarantined_workflow_qa.py --mode current --json "$OutputDir\current.json" --log "$OutputDir\current.log"
  if ($LASTEXITCODE -ne 0) { throw 'Current source policy or tests failed. Inspect current.log.' }
  python scripts/windows_acceptance_gate.py --repo "$root" --out-dir "$OutputDir\gate"
  if ($LASTEXITCODE -ne 0) { throw 'Windows gate blocked or failed. Inspect gate\windows_acceptance.json.' }
  python scripts/recovery_ui_export_probe.py --out-dir "$OutputDir\ui-exports"
  if ($LASTEXITCODE -ne 0) { throw 'Visible Qt or Office/PDF export probe failed.' }
  Write-Host 'Technical checks finished; actual Windows Office and owner visual approval remain PENDING.'
} finally { Pop-Location }
