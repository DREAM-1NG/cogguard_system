$ErrorActionPreference = "Continue"

$Root = "G:\CISCN\CogGuard\subsystems\cogguard_dev"
$Benchmark = Join-Path $Root "benchmark"
$LogDir = Join-Path $Benchmark "logs"
$GuardLog = Join-Path $LogDir "propagation_training_sufficiency_fullsource_guard_20260811.log"
$ContinuationScript = Join-Path $Benchmark "run_propagation_training_sufficiency_continue_after_fullsource_20260811.ps1"
$FullSourceOut = Join-Path $Benchmark "propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811.json"
$FullSourceCheckpointDir = Join-Path $Benchmark "checkpoints\propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $FullSourceCheckpointDir | Out-Null

function Write-GuardLog {
    param([string]$Message)
    "[$((Get-Date).ToString("s"))] $Message" | Tee-Object -FilePath $GuardLog -Append
}

function Test-FullSourceComplete {
    if (-not (Test-Path -LiteralPath $FullSourceOut)) {
        return $false
    }
    try {
        $Payload = Get-Content -LiteralPath $FullSourceOut -Raw | ConvertFrom-Json
        $Rows = @($Payload.rows)
        $Audit = $Payload.protocol_audit
        return (
            $Payload.status -eq "ok" -and
            $Rows.Count -ge 18 -and
            $null -ne $Audit -and
            $Audit.passed -eq $true -and
            [int]$Audit.fair_ok_count -ge 18 -and
            [int]$Audit.requested_count -eq 18
        )
    }
    catch {
        Write-GuardLog "Unable to parse fullsource output: $($_.Exception.Message)"
        return $false
    }
}

function Get-FullSourceRowCount {
    if (-not (Test-Path -LiteralPath $FullSourceOut)) {
        return 0
    }
    try {
        $Payload = Get-Content -LiteralPath $FullSourceOut -Raw | ConvertFrom-Json
        if ($null -ne $Payload.rows) {
            return @($Payload.rows).Count
        }
        if ($null -ne $Payload.results) {
            return @($Payload.results).Count
        }
        return 0
    }
    catch {
        Write-GuardLog "Unable to inspect fullsource row count: $($_.Exception.Message)"
        return 0
    }
}

function Get-FullSourceTraining {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match "python" -and
            $_.CommandLine -match "benchmark\.propagation_training_adequacy_20260810" -and
            $_.CommandLine -match "fullsource_3seed"
        }
}

function Get-ContinuationWatcher {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match "powershell" -and
            $_.CommandLine -match "-File\s+.*run_propagation_training_sufficiency_continue_after_fullsource_20260811\.ps1"
        }
}

function Get-PrematureLaterStage {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match "python" -and
            ($_.CommandLine -match "benchmark\.same_protocol_full_run_baselines" -or $_.CommandLine -match "benchmark\.run_benchmark")
        }
}

function Start-GuardedContinuation {
    Write-GuardLog "Starting checkpoint-aware guarded continuation."
    Start-Process -FilePath powershell.exe `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ContinuationScript) `
        -WindowStyle Hidden | Out-Null
}

Write-GuardLog "Fullsource guard started."

while ($true) {
    if (Test-FullSourceComplete) {
        Write-GuardLog "Fullsource is complete and fair; guard finished."
        break
    }

    $Premature = @(Get-PrematureLaterStage)
    if ($Premature.Count -gt 0) {
        $Pids = ($Premature | ForEach-Object { $_.ProcessId }) -join ","
        Write-GuardLog "Stopping premature public/temporal stage before fullsource completion. pids=$Pids"
        foreach ($Proc in $Premature) {
            Stop-Process -Id $Proc.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    $Training = @(Get-FullSourceTraining)
    $Watchers = @(Get-ContinuationWatcher)
    $FullSourceRows = Get-FullSourceRowCount
    if ($FullSourceRows -gt 0 -and $Training.Count -gt 0 -and -not (Test-FullSourceComplete)) {
        $NonCheckpointTraining = @(
            $Training | Where-Object { $_.CommandLine -notmatch "--training_checkpoint_dir" }
        )
        if ($NonCheckpointTraining.Count -gt 0) {
            $Pids = ($NonCheckpointTraining | ForEach-Object { $_.ProcessId }) -join ","
            Write-GuardLog "Fullsource has rows=$FullSourceRows/18; stopping non-checkpoint fullsource training pids=$Pids before the next row."
            foreach ($Proc in $NonCheckpointTraining) {
                Stop-Process -Id $Proc.ProcessId -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Seconds 10
            continue
        }
    }

    if ($Training.Count -eq 0 -and $Watchers.Count -eq 0) {
        Write-GuardLog "No fullsource training or continuation watcher is active; starting guarded continuation."
        Start-GuardedContinuation
        Start-Sleep -Seconds 30
        continue
    }

    if ($Training.Count -eq 0 -and $Watchers.Count -gt 0) {
        Start-Sleep -Seconds 10
        $TrainingAfterGrace = @(Get-FullSourceTraining)
        if ($TrainingAfterGrace.Count -eq 0 -and -not (Test-FullSourceComplete)) {
            $WatcherPidsToStop = ($Watchers | ForEach-Object { $_.ProcessId }) -join ","
            Write-GuardLog "Fullsource incomplete and no active training after grace period; replacing continuation watcher pids=$WatcherPidsToStop."
            foreach ($Proc in $Watchers) {
                Stop-Process -Id $Proc.ProcessId -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Seconds 5
            Start-GuardedContinuation
            Start-Sleep -Seconds 30
            continue
        }
    }

    $TrainingPids = if ($Training.Count -gt 0) { ($Training | ForEach-Object { $_.ProcessId }) -join "," } else { "none" }
    $WatcherPids = if ($Watchers.Count -gt 0) { ($Watchers | ForEach-Object { $_.ProcessId }) -join "," } else { "none" }
    Write-GuardLog "Guard heartbeat; fullsource incomplete; training=$TrainingPids watcher=$WatcherPids"
    Start-Sleep -Seconds 300
}
