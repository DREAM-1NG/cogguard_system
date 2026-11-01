$ErrorActionPreference = "Continue"

$Root = "G:\CISCN\CogGuard\subsystems\cogguard_dev"
$Benchmark = Join-Path $Root "benchmark"
$LogDir = Join-Path $Benchmark "logs"
$DocDir = "G:\CISCN\CogGuard\.worktrees\refactor-system\system\doc\research\propagation_paper_deep_reads"
$StatusPath = Join-Path $Benchmark "propagation_training_sufficiency_200ep_full_20260811_status.json"
$Python = "python"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $DocDir | Out-Null
Set-Location $Root

function Write-Status {
    param(
        [string]$Status,
        [object[]]$Results,
        [string]$CurrentStep = ""
    )
    [ordered]@{
        schema = "cogguard.propagation.training_sufficiency_queue.v1"
        status = $Status
        current_step = $CurrentStep
        updated_at = (Get-Date).ToString("o")
        results = $Results
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

function Update-SummaryReport {
    $SummaryLog = Join-Path $LogDir "propagation_training_sufficiency_200ep_summary_20260811.log"
    $Start = Get-Date
    "[$($Start.ToString("s"))] UPDATE summary" | Tee-Object -FilePath $SummaryLog -Append
    & $Python -m benchmark.summarize_propagation_training_sufficiency_20260811 *>&1 | Tee-Object -FilePath $SummaryLog -Append
    if ($LASTEXITCODE -ne 0) {
        "[$((Get-Date).ToString("s"))] summary update failed with exit code $LASTEXITCODE" |
            Tee-Object -FilePath $SummaryLog -Append
    }
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
    "[$($Start.ToString("s"))] START $Name" | Tee-Object -FilePath $Log -Append
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

$Results = @()
Write-Status -Status "queued" -CurrentStep "" -Results $Results

# Phase 1: same-protocol trainable models, paper-like capacity, resource-bounded cascades.
$Results = Invoke-Step `
    -Name "sequence_joint_200ep_h64_seq200_300c_3seed" `
    -Log (Join-Path $LogDir "propagation_training_sufficiency_sequence_200ep_h64_seq200_300c_3seed_20260811.log") `
    -Results $Results `
    -CommandArgs @(
        "-u", "-m", "benchmark.propagation_training_adequacy_20260810",
        "--datasets", "douban,twitter,memetracker",
        "--seeds", "42,43,44",
        "--models", "Ours,MINDS",
        "--epoch_grid", "200",
        "--train_cascades", "300",
        "--eval_cascades", "100",
        "--hidden_dims", "64",
        "--max_sequence_lens", "200",
        "--batch_size", "32",
        "--device", "cuda",
        "--out", "benchmark\propagation_training_sufficiency_sequence_200ep_h64_seq200_300c_3seed_20260811.json",
        "--report", (Join-Path $DocDir "propagation_training_sufficiency_sequence_200ep_h64_seq200_300c_3seed_20260811.md"),
        "--progress_interval", "5",
        "--resume"
    )

# Phase 2: same-protocol trainable models on full available train/test splits.
$Results = Invoke-Step `
    -Name "sequence_joint_200ep_h64_seq200_fullsource_3seed" `
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
        "--resume"
    )

# Phase 3: public-code macro/micro and macro-only baselines with paper-level epochs where local dependencies allow.
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

# Phase 4: temporal graph models keep their native link-prediction task; results are not cascade Top-K until a learned scorer is wired.
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

Write-Status -Status "finished" -CurrentStep "" -Results $Results
Update-SummaryReport
