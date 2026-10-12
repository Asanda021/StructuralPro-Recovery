param(
  [Parameter(Mandatory=$true)][string]$Payload,
  [Parameter(Mandatory=$true)][ValidateSet("standard","pro","enterprise")][string]$Edition
)
$ErrorActionPreference="Stop"
New-Item -ItemType Directory -Force "$Payload/models","$Payload/ai_runtime" | Out-Null

$runtimeUrl="https://github.com/ggml-org/llama.cpp/releases/download/b10549/llama-b10549-bin-win-cpu-x64.zip"
$runtimeSha="11d38f2ed878489b2c3d02b3d1a67683c02fbfb3d265876b9ede749a8dff5f1c"
$runtimeZip="$env:TEMP\structuralpro-llama-b10549.zip"
& curl.exe -L --fail --retry 3 --retry-delay 2 -o $runtimeZip $runtimeUrl
if ($LASTEXITCODE -ne 0) { throw "llama.cpp runtime download failed" }
if ((Get-FileHash $runtimeZip -Algorithm SHA256).Hash.ToLower() -ne $runtimeSha) { throw "llama.cpp runtime SHA256 mismatch" }
$extract="$env:TEMP\structuralpro-llama-$Edition"
if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
Expand-Archive $runtimeZip $extract -Force
$cli=Get-ChildItem $extract -Filter "llama-cli.exe" -File -Recurse | Select-Object -First 1
if (-not $cli) { throw "llama-cli.exe missing from llama.cpp runtime" }
Copy-Item $cli.FullName "$Payload/ai_runtime/llama-cli.exe" -Force
# The prebuilt CLI binaries depend on llama.cpp/ggml shared libraries; keep the
# complete CPU runtime beside the executables so the bundled AI is self-contained.
$dlls=Get-ChildItem $extract -Filter "*.dll" -File -Recurse
if (-not $dlls) { throw "llama.cpp runtime DLLs are missing from the archive" }
foreach ($dll in $dlls) { Copy-Item $dll.FullName "$Payload/ai_runtime/$($dll.Name)" -Force }
$mtmd=Get-ChildItem $extract -Filter "llama-mtmd-cli.exe" -File -Recurse | Select-Object -First 1
if (($Edition -eq "pro" -or $Edition -eq "enterprise") -and -not $mtmd) { throw "llama-mtmd-cli.exe missing from llama.cpp runtime" }
if ($mtmd) { Copy-Item $mtmd.FullName "$Payload/ai_runtime/llama-mtmd-cli.exe" -Force }

function Download-Checked([string]$Url,[string]$Target,[string]$Sha) {
  & curl.exe -L --fail --retry 3 --retry-delay 2 -o $Target $Url
  if ($LASTEXITCODE -ne 0) { throw "AI model download failed: $Url" }
  if ((Get-FileHash $Target -Algorithm SHA256).Hash.ToLower() -ne $Sha) { throw "AI model SHA256 mismatch: $Target" }
}

if ($Edition -eq "standard") {
  $model="qwen2.5-0.5b-instruct-q4_k_m.gguf"
  Download-Checked "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf" "$Payload/models/$model" "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"
  $tier="base"
  $mmproj=$null
} else {
  $model="Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
  $mmproj="mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf"
  Download-Checked "https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf" "$Payload/models/$model" "d02fe9b69ad8cadbbd228e387667af66612c44bed29ffc8eb1e7caf9ac486c12"
  Download-Checked "https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf" "$Payload/models/$mmproj" "980c9b2f78c04e6cff93d277ada09e768394f112d75db3b4e9dea8a69f9fb904"
  $tier="takeoff"
}

[ordered]@{
  edition=$Edition
  ai_tier=$tier
  runtime="llama.cpp b10549 CPU x64"
  runtime_sha256=$runtimeSha
  model=$model
  mmproj=$mmproj
  offline=$true
  network_required_for_inference=$false
  runtime_dlls=(@($dlls | ForEach-Object { $_.Name } | Sort-Object -Unique))
} | ConvertTo-Json | Set-Content "$Payload/AI_MODEL_PROFILE.json" -Encoding utf8
"Embedded AI runtime: llama.cpp b10549 (MIT)" | Set-Content "$Payload/AI_THIRD_PARTY_LICENSES.txt" -Encoding utf8
"Embedded model license: Apache-2.0 (Qwen2.5 / Qwen2.5-VL)" | Add-Content "$Payload/AI_THIRD_PARTY_LICENSES.txt" -Encoding utf8
