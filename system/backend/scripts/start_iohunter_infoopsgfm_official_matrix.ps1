[CmdletBinding()]
param(
    [string]$PythonExecutable = "D:\Anaconda\python.exe",
    [string]$Device = "0",
    [string[]]$Dataset = @("russia", "venezuela", "iran", "china", "UAE", "cuba"),
    [string[]]$Method = @("gnn", "gnn_plus_llm", "multimodal_gnn", "cross_attention"),
    [int]$GpuMemoryIdleMiB = 1536,
    [int]$GpuUtilizationIdlePercent = 40,
    [int]$FreeMemoryMinimumMiB = 4096,
    [int]$PollSeconds = 60,
    [switch]$RetryNonSuccess
)

$ErrorActionPreference = "Stop"

function Get-SelectedGpuState {
    param([string]$RequestedDevice)

    $lines = & nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $lines) {
        throw "nvidia-smi could not query the selected GPU."
    }

    foreach ($line in $lines) {
        $parts = $line -split "," | ForEach-Object { $_.Trim() }
        if ($parts.Count -ne 3 -or $parts[0] -ne $RequestedDevice) {
            continue
        }
        return [PSCustomObject]@{
            Index = [int]$parts[0]
            MemoryUsedMiB = [int]$parts[1]
            UtilizationPercent = [int]$parts[2]
        }
    }

    throw "CUDA device $RequestedDevice was not returned by nvidia-smi."
}

function Test-IdleResources {
    param(
        [int]$MinimumFreeMemoryMiB,
        [int]$MaximumGpuMemoryMiB,
        [int]$MaximumGpuUtilizationPercent,
        [string]$RequestedDevice
    )

    $freeMemoryMiB = [math]::Floor(
        (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB
    )
    $gpu = Get-SelectedGpuState -RequestedDevice $RequestedDevice
    return [PSCustomObject]@{
        Ready = (
            $freeMemoryMiB -ge $MinimumFreeMemoryMiB -and
            $gpu.MemoryUsedMiB -le $MaximumGpuMemoryMiB -and
            $gpu.UtilizationPercent -le $MaximumGpuUtilizationPercent
        )
        FreeMemoryMiB = $freeMemoryMiB
        GpuMemoryUsedMiB = $gpu.MemoryUsedMiB
        GpuUtilizationPercent = $gpu.UtilizationPercent
    }
}

$backendRoot = Split-Path -Parent $PSScriptRoot
$systemRoot = Split-Path -Parent $backendRoot
$outputRoot = Join-Path $systemRoot "output\coordination_two_stage_reproduction"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputDir = Join-Path $outputRoot "iohunter-infoopsgfm-official-matrix-$timestamp"
$launcherRoot = Join-Path $outputDir "launcher"
$logPath = Join-Path $launcherRoot "launcher.log"

if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw "Python executable does not exist: $PythonExecutable"
}
if ($PollSeconds -le 0) {
    throw "PollSeconds must be positive."
}

New-Item -ItemType Directory -Path $launcherRoot -Force | Out-Null
$launcherManifest = [ordered]@{
    schema_version = "cogguard.iohunter-infoopsgfm-queued-matrix/v1"
    queued_at = (Get-Date).ToUniversalTime().ToString("o")
    output_dir = $outputDir
    python_executable = $PythonExecutable
    device = $Device
    datasets = $Dataset
    methods = $Method
    resource_gate = [ordered]@{
        minimum_free_memory_mib = $FreeMemoryMinimumMiB
        maximum_gpu_memory_used_mib = $GpuMemoryIdleMiB
        maximum_gpu_utilization_percent = $GpuUtilizationIdlePercent
        poll_seconds = $PollSeconds
    }
    retry_non_success = [bool]$RetryNonSuccess
}
$launcherManifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $launcherRoot "launcher.json") -Encoding utf8

while ($true) {
    $state = Test-IdleResources `
        -MinimumFreeMemoryMiB $FreeMemoryMinimumMiB `
        -MaximumGpuMemoryMiB $GpuMemoryIdleMiB `
        -MaximumGpuUtilizationPercent $GpuUtilizationIdlePercent `
        -RequestedDevice $Device
    $message = "$(Get-Date -Format o) free_memory_mib=$($state.FreeMemoryMiB) gpu_memory_mib=$($state.GpuMemoryUsedMiB) gpu_utilization_percent=$($state.GpuUtilizationPercent) ready=$($state.Ready)"
    Add-Content -LiteralPath $logPath -Value $message
    if ($state.Ready) {
        break
    }
    Start-Sleep -Seconds $PollSeconds
}

$env:PYTHONPATH = $systemRoot
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:TEMP = Join-Path $launcherRoot "tmp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null

$arguments = @(
    "-m", "research.coordination_experiments.iohunter_socgfm",
    "--run-matrix",
    "--output-dir", $outputDir,
    "--device", $Device
)
foreach ($item in $Dataset) {
    $arguments += @("--matrix-dataset", $item)
}
foreach ($item in $Method) {
    $arguments += @("--matrix-method", $item)
}
if ($RetryNonSuccess) {
    $arguments += "--retry-non-success"
}

Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) starting official matrix"
& $PythonExecutable @arguments *>> $logPath
$exitCode = $LASTEXITCODE
Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) completed exit_code=$exitCode"
exit $exitCode
