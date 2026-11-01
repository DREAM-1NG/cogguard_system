$ErrorActionPreference = "Continue"

$Root = "G:\CISCN\CogGuard\subsystems\cogguard_dev"
$Benchmark = Join-Path $Root "benchmark"
$LogDir = Join-Path $Benchmark "logs"
$DocDir = "G:\CISCN\CogGuard\.worktrees\refactor-system\system\doc\research\propagation_paper_deep_reads"
$StatusPath = Join-Path $Benchmark "propagation_training_sufficiency_200ep_full_20260811_status.json"
$ContinuationLog = Join-Path $LogDir "propagation_training_sufficiency_continue_after_fullsource_20260811.log"
$Python = "python"

$FullSourceOut = Join-Path $Benchmark "propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811.json"
$PublicOut = Join-Path $Benchmark "propagation_training_sufficiency_public_baselines_200ep_20260811.json"
$TemporalOut = Join-Path $Benchmark "propagation_training_sufficiency_temporal_graph_200ep_20260811.json"
$FullSourceCheckpointDir = Join-Path $Benchmark "checkpoints\propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $DocDir | Out-Null
New-Item -ItemType Directory -Force -Path $FullSourceCheckpointDir | Out-Null
Set-Location $Root

function Write-ContinuationLog {
    param([string]$Message)
    "[$((Get-Date).ToString("s"))] $Message" | Tee-Object -FilePath $ContinuationLog -Append
}

function Read-StatusResults {
    if (-not (Test-Path -LiteralPath $StatusPath)) {
        return @()
    }
    try {
        $StatusPayload = Get-Content -LiteralPath $StatusPath -Raw | ConvertFrom-Json
        if ($null -eq $StatusPayload.results) {
            return @()
        }
        return @($StatusPayload.results)
    }
    catch {
        Write-ContinuationLog "Unable to parse existing status JSON: $($_.Exception.Message)"
        return @()
    }
}

function Write-Status {
    param(
        [string]$Status,
        [string]$CurrentStep,
        [object[]]$Results
    )
    [ordered]@{
        schema = "cogguard.propagation.training_sufficiency_queue.v1"
        status = $Status
        current_step = $CurrentStep
        updated_at = (Get-Date).ToString("o")
        results = $Results
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

function Test-JsonRows {
    param(
        [string]$Path,
        [int]$ExpectedRows,
        [switch]$RequireFairProtocol
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    try {
        $Payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $Rows = @()
        if ($null -ne $Payload.rows) {
            $Rows = @($Payload.rows)
        }
        elseif ($null -ne $Payload.results) {
            $Rows = @($Payload.results)
        }
        elseif ($Payload -is [array]) {
            $Rows = @($Payload)
        }
        $StatusOk = ($null -eq $Payload.status) -or ($Payload.status -eq "ok") -or ($Payload.status -eq "completed")
        if (-not ($StatusOk -and $Rows.Count -ge $ExpectedRows)) {
            return $false
        }
        if ($RequireFairProtocol) {
            $Audit = $Payload.protocol_audit
            if ($null -eq $Audit) {
                return $false
            }
            return (
                $Audit.passed -eq $true -and
                [int]$Audit.row_count -ge $ExpectedRows -and
                [int]$Audit.fair_ok_count -ge $ExpectedRows -and
                [int]$Audit.requested_count -eq $ExpectedRows
            )
        }
        return $true
    }
    catch {
        Write-ContinuationLog "Unable to parse result JSON $Path`: $($_.Exception.Message)"
        return $false
    }
}

function Get-JsonProgress {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return [ordered]@{
            exists = $false
            status = "missing"
            row_count = 0
            fair_ok_count = 0
            requested_count = 0
        }
    }
    try {
        $Payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $Rows = @()
        if ($null -ne $Payload.rows) {
            $Rows = @($Payload.rows)
        }
        elseif ($null -ne $Payload.results) {
            $Rows = @($Payload.results)
        }
        elseif ($Payload -is [array]) {
            $Rows = @($Payload)
        }
        $Audit = $Payload.protocol_audit
        return [ordered]@{
            exists = $true
            status = [string]$Payload.status
            row_count = $Rows.Count
            fair_ok_count = if ($null -ne $Audit) { [int]$Audit.fair_ok_count } else { 0 }
            requested_count = if ($null -ne $Audit) { [int]$Audit.requested_count } else { 0 }
        }
    }
    catch {
        Write-ContinuationLog "Unable to inspect result JSON $Path`: $($_.Exception.Message)"
        return [ordered]@{
            exists = $true
            status = "parse_error"
            row_count = 0
            fair_ok_count = 0
            requested_count = 0
        }
    }
}

function Wait-ForFullSourceProcess {
    while ($true) {
        $Running = Get-CimInstance Win32_Process |
            Where-Object {
                $_.Name -match "python" -and
                $_.CommandLine -match "benchmark\.propagation_training_adequacy_20260810" -and
                $_.CommandLine -match "fullsource_3seed"
            } |
            Select-Object ProcessId,CreationDate,CommandLine
        if (-not $Running) {
            Write-ContinuationLog "No active fullsource Python process found."
            break
        }
        $Pids = ($Running | ForEach-Object { $_.ProcessId }) -join ","
        Write-ContinuationLog "Waiting for active fullsource process pid=$Pids"
        Start-Sleep -Seconds 300
    }
    Start-Sleep -Seconds 10
}

function Update-SummaryReport {
    $SummaryLog = Join-Path $LogDir "propagation_training_sufficiency_200ep_summary_20260811.log"
    Write-ContinuationLog "Updating summary report."
    & $Python -m benchmark.summarize_propagation_training_sufficiency_20260811 *>&1 |
        Tee-Object -FilePath $SummaryLog -Append
}

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$CommandArgs,
        [string]$Log,
        [object[]]$Results
    )
    $Start = Get-Date
    $CommandLine = "$Python " + (($CommandArgs | ForEach-Object { if ($_ -match "\s") { '"' + $_ + '"' } else { $_ } }) -join " ")
    Write-Status -Status "running" -CurrentStep $Name -Results $Results
    Write-ContinuationLog "START $Name"
    $CommandLine | Tee-Object -FilePath $Log -Append
    & $Python @CommandArgs *>&1 | Tee-Object -FilePath $Log -Append
    $ExitCode = $LASTEXITCODE
    $End = Get-Date
    $Results += [ordered]@{
        name = $Name
        command = $CommandLine
        log = $Log
        started_at = $Start.ToString("o")
        ended_at = $End.ToString("o")
        elapsed_seconds = [math]::Round(($End - $Start).TotalSeconds, 1)
        exit_code = $ExitCode
    }
    Write-Status -Status "running" -CurrentStep $Name -Results $Results
    Update-SummaryReport
    return $Results
}

Write-ContinuationLog "Continuation watcher started."
$Results = Read-StatusResults

Wait-ForFullSourceProcess

while (-not (Test-JsonRows -Path $FullSourceOut -ExpectedRows 18 -RequireFairProtocol)) {
    $Progress = Get-JsonProgress -Path $FullSourceOut
    Write-ContinuationLog "Fullsource output incomplete; rows=$($Progress.row_count)/18 fair=$($Progress.fair_ok_count)/18 status=$($Progress.status). Resuming one row."
    $Results = Invoke-Step `
        -Name "sequence_joint_200ep_h64_seq200_fullsource_3seed_next_row" `
        -Log (Join-Path $LogDir "propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811.log") `
        -Results $Results `
        -CommandArgs @(
            "-u", "-m", "benchmark.propagation_training_adequacy_20260810",
            "--datasets", "douban,twitter,memetracker",
            "--seeds", "42,43,44",
            "--models", "Ours,MINDS",
            "--epoch_grid", "200",
            "--train_cascades", "0",
            "--eval_cascades", "0",
            "--hidden_dims", "64",
            "--max_sequence_lens", "200",
            "--batch_size", "32",
            "--device", "cuda",
            "--out", "benchmark\propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811.json",
            "--report", (Join-Path $DocDir "propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811.md"),
            "--progress_interval", "5",
            "--max_new_runs", "1",
            "--training_checkpoint_dir", $FullSourceCheckpointDir,
            "--training_checkpoint_interval", "5",
            "--resume"
        )
    if (-not (Test-JsonRows -Path $FullSourceOut -ExpectedRows 18 -RequireFairProtocol)) {
        $Progress = Get-JsonProgress -Path $FullSourceOut
        Write-ContinuationLog "Fullsource guard continuing; rows=$($Progress.row_count)/18 fair=$($Progress.fair_ok_count)/18 status=$($Progress.status)."
    }
}
Write-ContinuationLog "Fullsource output is complete and fair; rows=18/18. Continuing to public baselines."
Update-SummaryReport

if (-not (Test-JsonRows -Path $PublicOut -ExpectedRows 27)) {
    $Results = Invoke-Step `
        -Name "public_baselines_200ep" `
        -Log (Join-Path $LogDir "propagation_training_sufficiency_public_baselines_200ep_20260811.log") `
        -Results $Results `
        -CommandArgs @(
            "-u", "-m", "benchmark.same_protocol_full_run_baselines",
            "--datasets", "douban,twitter,memetracker",
            "--seeds", "42,43,44",
            "--models", "MINDS,FOREST,CasFT",
            "--forest_data_root", "G:\CISCN\dataset\forest-data",
            "--minds_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS",
            "--forest_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST",
            "--casft_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT",
            "--out", "benchmark\propagation_training_sufficiency_public_baselines_200ep_20260811.json",
            "--config_id", "propagation-training-sufficiency-public-baselines-200ep-20260811",
            "--device", "cuda",
            "--timeout", "86400",
            "--max_minds_cascades", "0",
            "--minds_epochs", "200",
            "--minds_batch_size", "16",
            "--minds_emb_dim", "64",
            "--minds_step_split", "8",
            "--forest_epochs", "200",
            "--forest_batch_size", "16",
            "--forest_d_model", "64",
            "--forest_max_train_batches", "0",
            "--forest_max_eval_batches", "0",
            "--forest_rl_epochs", "200",
            "--forest_rl_max_batches", "0",
            "--forest_rl_rollout_len", "5",
            "--casft_max_events", "0",
            "--casft_max_epoch", "200",
            "--casft_timesteps", "1000",
            "--resume"
        )
}
else {
    Write-ContinuationLog "Public baseline output is complete; skipping public_baselines_200ep."
}

if (-not (Test-JsonRows -Path $TemporalOut -ExpectedRows 6)) {
    $Results = Invoke-Step `
        -Name "temporal_graph_native_200ep" `
        -Log (Join-Path $LogDir "propagation_training_sufficiency_temporal_graph_200ep_20260811.log") `
        -Results $Results `
        -CommandArgs @(
            "-u", "-m", "benchmark.run_benchmark",
            "--datasets", "douban", "twitter", "memetracker",
            "--models", "dyglib", "tgn",
            "--forest_dir", "G:\CISCN\dataset\forest-data",
            "--dyglib_dir", "G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib",
            "--tgn_dir", "G:\CISCN\CogGuard\subsystems\kt2_repos\tgn",
            "--frontier_export_dir", "benchmark\propagation_training_sufficiency_frontier_exports_200ep_20260811",
            "--frontier_max_cascades", "0",
            "--frontier_epochs", "200",
            "--frontier_num_runs", "5",
            "--frontier_batch_size", "64",
            "--frontier_timeout", "86400",
            "--frontier_gpu", "0",
            "--run_external_frontier",
            "--device", "cuda",
            "--output", "benchmark\propagation_training_sufficiency_temporal_graph_200ep_20260811.json"
        )
}
else {
    Write-ContinuationLog "Temporal graph output is complete; skipping temporal_graph_native_200ep."
}

Write-Status -Status "finished" -CurrentStep "" -Results $Results
Update-SummaryReport
Write-ContinuationLog "Continuation watcher finished."
