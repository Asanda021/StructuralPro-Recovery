param(
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [Parameter(Mandatory = $true)][string]$ExpectedSourceSha
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if (-not $IsWindows -or -not [Environment]::Is64BitProcess) { throw 'Windows x64 PowerShell is required' }
$repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repo
$sha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sha -ne $ExpectedSourceSha) { throw 'Unexpected source SHA' }

$delivery = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $delivery) { throw 'Output directory must be new' }
New-Item -ItemType Directory -Path $delivery | Out-Null
$scratch = Join-Path ([IO.Path]::GetTempPath()) ('structuralpro-portable-' + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $scratch | Out-Null
$dist = Join-Path $scratch 'dist'
$spec = Join-Path $scratch 'spec'
New-Item -ItemType Directory -Path $spec | Out-Null

$freezeLog = Join-Path $scratch 'pyinstaller.log'
Write-Host "Freezing StructuralPro desktop from source $sha"
& python -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name StructuralPro `
    --paths $repo --distpath $dist --workpath (Join-Path $scratch 'build') --specpath $spec `
    app/column_takeoff_desktop.py 2>&1 | Tee-Object -FilePath $freezeLog
if ($LASTEXITCODE -ne 0) {
    $tail = (Get-Content -LiteralPath $freezeLog -Tail 12) -join ' '
    throw "PyInstaller failed with exit code ${LASTEXITCODE}: $tail"
}
$bundle = Join-Path $dist 'StructuralPro'
$internal = Join-Path $bundle '_internal'
$exe = Join-Path $bundle 'StructuralPro.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Missing StructuralPro.exe' }

# Install app-local VC143 runtime from the Visual Studio redistributable files.
# Runner system DLL availability is not evidence that the bundle contains them.
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = (& $vswhere -latest -products '*' -property installationPath | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or -not $vs) { throw 'Visual Studio redistributable location was not found' }
$redistRoot = Join-Path $vs 'VC/Redist/MSVC'
$redist = Get-ChildItem -LiteralPath $redistRoot -Directory |
    Where-Object { $_.Name -match '^\d+\.\d+(\.\d+)?$' } |
    Sort-Object { [version]$_.Name } -Descending |
    ForEach-Object { Join-Path $_.FullName 'x64/Microsoft.VC143.CRT' } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
    Select-Object -First 1
if (-not $redist) { throw 'Windows x64 VC143 redistributable payload is unavailable' }
Get-ChildItem -LiteralPath $redist -File -Filter '*.dll' |
    Copy-Item -Destination $internal -Force
Copy-Item -LiteralPath (Join-Path $repo 'VERSION') -Destination $bundle
@'
StructuralPro Windows portable preview
Extract this ZIP completely and run StructuralPro.exe from the extracted folder.
Keep the _internal folder beside the executable. No installer is needed.
PDF column quantities and user-entered steel assumptions are draft review only.
'@ | Set-Content -LiteralPath (Join-Path $bundle 'START-HERE.txt') -Encoding utf8

$zipName = 'StructuralPro-Windows-Portable.zip'
$archive = Join-Path $delivery $zipName
Compress-Archive -Path $bundle -DestinationPath $archive -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
$bytes = (Get-Item -LiteralPath $archive).Length
$extractRoot = Join-Path $scratch 'extracted'
Expand-Archive -LiteralPath $archive -DestinationPath $extractRoot
$extracted = Join-Path $extractRoot 'StructuralPro'
$frozen = Join-Path $extracted 'StructuralPro.exe'
$files = Get-ChildItem -LiteralPath $extracted -Recurse -File
$required = @('StructuralPro.exe', 'python312.dll', 'Qt6Core.dll', 'Qt6Gui.dll',
              'Qt6Widgets.dll', 'qwindows.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll')
$runtime = foreach ($name in $required) {
    $file = $files | Where-Object Name -eq $name | Select-Object -First 1
    if (-not $file) { throw "Required bundled runtime file missing: $name" }
    [ordered]@{
        file = [IO.Path]::GetRelativePath($extracted, $file.FullName)
        bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

# Both launches use the extracted application and no runner Python on PATH.
$env:Path = [IO.Path]::Combine($env:SystemRoot, 'System32') + ';' + $env:SystemRoot
Remove-Item Env:PYTHONPATH, Env:PYTHONHOME, Env:QT_PLUGIN_PATH, Env:QT_QPA_PLATFORM_PLUGIN_PATH -ErrorAction SilentlyContinue
$env:QT_QPA_PLATFORM = 'windows'
$sandbox = Join-Path $scratch 'synthetic-smoke'
New-Item -ItemType Directory -Path $sandbox | Out-Null
$smokePath = Join-Path $sandbox 'portable-smoke.json'
$process = Start-Process -FilePath $frozen -WorkingDirectory $sandbox `
    -ArgumentList @('--smoke-test', ('"{0}"' -f $sandbox)) -PassThru
try {
    if (-not $process.WaitForExit(180000)) { throw 'Frozen executable smoke test timed out' }
    if ($process.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $smokePath -PathType Leaf) {
            Write-Host (Get-Content -LiteralPath $smokePath -Raw)
        }
        throw "Frozen executable smoke failed with exit code $($process.ExitCode)"
    }
} finally {
    if (-not $process.HasExited) { $process.Kill() }
    $process.Dispose()
}
$smoke = Get-Content -LiteralPath $smokePath -Raw | ConvertFrom-Json -AsHashtable
$requiredChecks = @('qt_window', 'pdf_extraction', 'scenario_edit', 'excel_roundtrip',
                    'persian_paths', 'nonfinancial_only', 'file_switch', 'invalid_pdf')
if ($smoke.status -ne 'PASS' -or $smoke.qt_platform -ne 'windows' -or
    ($requiredChecks | Where-Object { $smoke.checks[$_] -ne 'PASS' })) {
    Write-Host (Get-Content -LiteralPath $smokePath -Raw)
    throw 'Frozen smoke did not confirm all checks on the native Windows Qt platform'
}

$visible = Start-Process -FilePath $frozen -WorkingDirectory $sandbox -PassThru
try {
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        Start-Sleep -Milliseconds 250
        $visible.Refresh()
        if ($visible.HasExited) { throw "Visible application exited before showing its window: $($visible.ExitCode)" }
        $ready = $visible.MainWindowHandle -ne [IntPtr]::Zero -and $visible.MainWindowTitle -like '*StructuralPro*'
    } until ($ready -or [DateTime]::UtcNow -ge $deadline)
    if (-not $ready) { throw 'StructuralPro did not show its native desktop window' }
    if (-not $visible.CloseMainWindow() -or -not $visible.WaitForExit(30000) -or $visible.ExitCode -ne 0) {
        throw 'Visible StructuralPro application did not close normally'
    }
} finally {
    if (-not $visible.HasExited) { $visible.Kill() }
    $visible.Dispose()
}

Copy-Item -LiteralPath $smokePath -Destination $delivery
"$hash  $zipName" | Set-Content -LiteralPath (Join-Path $delivery "$zipName.sha256.txt") -Encoding ascii
$manifest = [ordered]@{
    source_sha = $sha
    archive = $zipName
    archive_bytes = $bytes
    archive_sha256 = $hash
    executable = 'StructuralPro/StructuralPro.exe'
    bundled_runtime = $runtime
    exact_archive_frozen_smoke = 'PASS'
    native_window_launch_and_close = 'PASS'
    qt_platform = $smoke.qt_platform
    synthetic_checks = $smoke.checks
}
$manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $delivery 'portable-build.json') -Encoding utf8
$checks = $smoke.checks.Keys -join ', '
Write-Host "::notice title=StructuralPro Windows portable artifact::$zipName SHA-256 $hash bytes $bytes source $sha"
Write-Host "::notice title=Frozen Windows application verified::Native launch and close PASS. Synthetic checks: $checks"
if ($env:GITHUB_STEP_SUMMARY) {
    @"
### StructuralPro Windows portable preview

- Source commit: ``$sha``
- Archive: ``$zipName``
- Size: $bytes bytes
- SHA-256: ``$hash``
- Native Windows desktop launch and close: PASS
- Synthetic checks in the unpacked executable: $checks
"@ | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding utf8
}
