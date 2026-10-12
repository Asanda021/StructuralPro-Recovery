# Run manually on real Windows. Source-only; no Actions/build/install/release.
[CmdletBinding()]
param([string]$PythonExe = 'python',
      [string]$OutputDir = ("qa\critical-windows-" + (Get-Date -Format 'yyyyMMdd_HHmmss')))
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    $platform = (& $PythonExe -c "import sys; print(sys.platform)").Trim()
    if ($LASTEXITCODE -ne 0 -or $platform -ne 'win32') {
        throw 'BLOCKED_NOT_WINDOWS: real Windows is required.'
    }
    New-Item -ItemType Directory -Path $OutputDir -ErrorAction Stop | Out-Null
    & $PythonExe scripts/windows_acceptance_gate.py --repo $root --out-dir "$OutputDir\gate"
    if ($LASTEXITCODE -ne 0) { throw 'Windows source gate failed or blocked.' }
    & $PythonExe -m pytest -q tests/test_audit_critical_persistence.py tests/test_audit_critical_ui.py tests/test_audit_critical_quantities.py tests/test_audit_critical_finance.py tests/test_audit_critical_drawing_sources.py tests/test_recovery_manual_audit_concurrency.py "--junitxml=$OutputDir\critical.xml" "--basetemp=$OutputDir\data"
    if ($LASTEXITCODE -ne 0) { throw 'Critical source regression failed; inspect the logs and XML.' }
    Write-Host 'Technical source checks passed. Windows Office/RTL/DPI and engineer/owner visual approval remain required.'
    Write-Host 'Launch the source manually: python -m app.main'
} finally { Pop-Location }
