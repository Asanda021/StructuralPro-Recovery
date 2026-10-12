param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ExpectedVersion
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path $Installer)) { throw "Installer not found: $Installer" }
if ($ExpectedVersion -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid expected version: $ExpectedVersion" }

$installDir = Join-Path $env:RUNNER_TEMP "StructuralPro-Installer-Smoke"
if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force }

$installerPath = (Resolve-Path $Installer).Path
$installerProcess = Start-Process -FilePath $installerPath -ArgumentList @(
    "/VERYSILENT",
    "/NORESTART",
    "/SUPPRESSMSGBOXES",
    "/DIR=$installDir"
) -Wait -PassThru
if ($installerProcess.ExitCode -ne 0) { throw "Installer exited with code $($installerProcess.ExitCode)" }

$exe = Join-Path $installDir "StructuralPro.exe"
$versionFile = Join-Path $installDir "VERSION"
if (-not (Test-Path $exe)) { throw "Installed executable missing: $exe" }
if (-not (Test-Path $versionFile)) { throw "Installed VERSION missing: $versionFile" }

$installedVersion = (Get-Content $versionFile -Raw).Trim()
if ($installedVersion -ne $ExpectedVersion) {
    throw "Installed VERSION '$installedVersion' does not match '$ExpectedVersion'"
}

$env:STRUCTURALPRO_SMOKE = "1"
$env:QT_QPA_PLATFORM = "offscreen"
$logDir = Join-Path $env:RUNNER_TEMP "StructuralPro-Installer-Smoke-Logs"
if (Test-Path $logDir) { Remove-Item $logDir -Recurse -Force }
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$env:STRUCTURALPRO_LOG_DIR = $logDir
try {
    $appProcess = Start-Process -FilePath $exe -Wait -PassThru
    $exitCode = $appProcess.ExitCode
}
finally {
    Remove-Item Env:STRUCTURALPRO_SMOKE -ErrorAction SilentlyContinue
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    Remove-Item Env:STRUCTURALPRO_LOG_DIR -ErrorAction SilentlyContinue
}

if ($exitCode -ne 0) {
    $appLog = Join-Path $logDir "structuralpro.log"
    if (Test-Path $appLog) {
        Write-Host "---- StructuralPro application log before process failure ----"
        Get-Content $appLog
        Write-Host "---- End StructuralPro application log ----"
    } else {
        Write-Host "No application log was created at $appLog"
    }
    throw "Installed application smoke exited with code $exitCode"
}

$uninstaller = Join-Path $installDir "unins000.exe"
if (Test-Path $uninstaller) {
    $uninstallProcess = Start-Process -FilePath $uninstaller -ArgumentList @("/VERYSILENT", "/NORESTART") -Wait -PassThru
    if ($uninstallProcess.ExitCode -ne 0) { throw "Uninstaller exited with code $($uninstallProcess.ExitCode)" }
}

Write-Host "Windows installer E2E smoke passed: $ExpectedVersion"
