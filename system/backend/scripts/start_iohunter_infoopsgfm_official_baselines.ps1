[CmdletBinding()]
param(
    [string]$PythonExecutable = "D:\Anaconda\python.exe",
    [string]$Device = "0",
    [string]$Dataset = "russia",
    [string]$PrimaryMatrixRoot = "G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-infoopsgfm-official-matrix-20260812-230724",
    [int]$GpuMemoryIdleMiB = 1536,
    [int]$GpuUtilizationIdlePercent = 40,
    [int]$FreeMemoryMinimumMiB = 4096,
    [int]$PollSeconds = 60
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

if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw "Python executable does not exist: $PythonExecutable"
}
if ($PollSeconds -le 0) {
    throw "PollSeconds must be positive."
}

$backendRoot = Split-Path -Parent $PSScriptRoot
$systemRoot = Split-Path -Parent $backendRoot
$systemOutputRoot = "G:\CISCN\CogGuard\.worktrees\refactor-system\system\output"
$outputRoot = Join-Path $systemOutputRoot "coordination_two_stage_reproduction"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputDir = Join-Path $outputRoot "iohunter-infoopsgfm-official-baselines-$Dataset-$timestamp"
$launcherRoot = Join-Path $outputDir "launcher"
$logPath = Join-Path $launcherRoot "launcher.log"
$primaryMatrixManifest = Join-Path $PrimaryMatrixRoot "matrix_manifest.json"

New-Item -ItemType Directory -Path $launcherRoot -Force | Out-Null
@{
    schema_version = "cogguard.iohunter-infoopsgfm-baseline-queue/v1"
    queued_at = (Get-Date).ToUniversalTime().ToString("o")
    output_dir = $outputDir
    primary_matrix_root = $PrimaryMatrixRoot
    dataset = $Dataset
    methods = @("node_pruning", "node2vec")
    resource_gate = @{
        minimum_free_memory_mib = $FreeMemoryMinimumMiB
        maximum_gpu_memory_used_mib = $GpuMemoryIdleMiB
        maximum_gpu_utilization_percent = $GpuUtilizationIdlePercent
        poll_seconds = $PollSeconds
    }
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $launcherRoot "launcher.json") -Encoding utf8

while (-not (Test-Path -LiteralPath $primaryMatrixManifest -PathType Leaf)) {
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) waiting_for_primary_matrix_manifest=$primaryMatrixManifest"
    Start-Sleep -Seconds $PollSeconds
}

while ($true) {
    $state = Test-IdleResources `
        -MinimumFreeMemoryMiB $FreeMemoryMinimumMiB `
        -MaximumGpuMemoryMiB $GpuMemoryIdleMiB `
        -MaximumGpuUtilizationPercent $GpuUtilizationIdlePercent `
        -RequestedDevice $Device
    Add-Content -LiteralPath $logPath -Value (
        "$(Get-Date -Format o) free_memory_mib=$($state.FreeMemoryMiB) " +
        "gpu_memory_mib=$($state.GpuMemoryUsedMiB) " +
        "gpu_utilization_percent=$($state.GpuUtilizationPercent) ready=$($state.Ready)"
    )
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
Remove-Item Env:\COGGUARD_INFOOPSGFM_ALLOW_WINDOWS_NODE2VEC -ErrorAction SilentlyContinue

$baselineMethodArguments = @(
    @("--method", "node_pruning"),
    @("--method", "node2vec")
)

foreach ($methodArguments in $baselineMethodArguments) {
    $method = $methodArguments[1]
    $methodOutputDir = Join-Path $outputDir "$Dataset--$method--official"
    $arguments = @(
        "-m", "research.coordination_experiments.iohunter_socgfm",
        "--dataset", $Dataset,
        "--device", $Device,
        "--output-dir", $methodOutputDir
    )
    $arguments += $methodArguments
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) starting method=$method"
    & $PythonExecutable @arguments *>> $logPath
    $exitCode = $LASTEXITCODE
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) completed method=$method exit_code=$exitCode"
}
