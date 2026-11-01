$ErrorActionPreference = "Continue"

$Root = "G:\CISCN\CogGuard\subsystems\cogguard_dev"
$Benchmark = Join-Path $Root "benchmark"
$LogDir = Join-Path $Benchmark "logs"
$StatusPath = Join-Path $Benchmark "propagation_sota_stable_20260810_status.json"
$Python = "python"
$SequenceSource = "G:\CISCN\CogGuard\.worktrees\refactor-system\system\research\propagation_analysis\benchmark\sequence_vs_minds_sample_300c_5ep_3seed.json"
$SequenceTarget = Join-Path $Benchmark "propagation_sota_sequence_vs_minds_stable_20260810.json"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Root

function Write-Status {
    param(
        [string]$Status,
        [array]$Results
    )
    [ordered]@{
        status = $Status
        updated_at = (Get-Date).ToString("o")
        evidence_level = "resource_bounded_stable_matrix"
        boundary = "This run completes the multi-dataset method matrix with local resource caps; it does not replace strict uncapped full validation."
        results = $Results
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatusPath -Encoding UTF8
}

function Run-Step {
    param(
        [string]$Name,
        [string]$Log,
        [array]$StepArgs
    )
    $Start = Get-Date
    $CommandLine = "$Python " + (($StepArgs | ForEach-Object { if ($_ -match "\s") { '"' + $_ + '"' } else { $_ } }) -join " ")
    "[$($Start.ToString("s"))] START $Name" | Tee-Object -FilePath $Log -Append | Out-Host
    $CommandLine | Tee-Object -FilePath $Log -Append | Out-Host
    & $Python @StepArgs *>&1 | Tee-Object -FilePath $Log -Append | Out-Host
    $ExitCode = $LASTEXITCODE
    $End = Get-Date
    return [ordered]@{
        name = $Name
        command = $CommandLine
        log = $Log
        started_at = $Start.ToString("o")
        ended_at = $End.ToString("o")
        elapsed_seconds = [math]::Round(($End - $Start).TotalSeconds, 1)
        exit_code = $ExitCode
    }
}

$Results = @()
Write-Status -Status "running" -Results $Results

$StartReuse = Get-Date
$ReuseLog = Join-Path $LogDir "propagation_sota_sequence_vs_minds_stable_20260810.log"
if (Test-Path -LiteralPath $SequenceSource) {
    Copy-Item -LiteralPath $SequenceSource -Destination $SequenceTarget -Force
    "[$($StartReuse.ToString("s"))] REUSE sequence_vs_minds from $SequenceSource" | Tee-Object -FilePath $ReuseLog -Append
    $Results += [ordered]@{
        name = "sequence_joint_vs_minds_stable_reused"
        command = "Copy-Item $SequenceSource $SequenceTarget"
        log = $ReuseLog
        source = $SequenceSource
        output = $SequenceTarget
        started_at = $StartReuse.ToString("o")
        ended_at = (Get-Date).ToString("o")
        elapsed_seconds = [math]::Round(((Get-Date) - $StartReuse).TotalSeconds, 1)
        exit_code = 0
    }
} else {
    $SequenceArgs = @(
        "-u", "-m", "benchmark.kt2_minds_comparison",
        "--datasets", "douban,twitter,memetracker",
        "--seeds", "42,43,44",
        "--forest_data_root", "G:\CISCN\dataset\forest-data",
        "--minds_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\MINDS",
        "--max_minds_cascades", "300",
        "--minds_epochs", "200",
        "--minds_batch_size", "16",
        "--minds_emb_dim", "64",
        "--minds_max_seq_length", "200",
        "--minds_reproduction_level", "public_code_adapter",
        "--kt2_epochs", "200",
        "--kt2_batch_size", "64",
        "--kt2_hidden_dim", "64",
        "--kt2_max_train_cascades", "300",
        "--kt2_max_test_cascades", "100",
        "--kt2_max_sequence_len", "200",
        "--kt2_obs_ratios", "0.1,0.3,0.5",
        "--out", "benchmark\propagation_sota_sequence_vs_minds_stable_20260810.json",
        "--config_id", "propagation-sota-sequence-vs-minds-stable-20260810",
        "--device", "cuda",
        "--timeout", "2400",
        "--resume"
    )
    $Results += Run-Step -Name "sequence_joint_vs_minds_stable" -Log $ReuseLog -StepArgs $SequenceArgs
}
Write-Status -Status "running" -Results $Results

$PrimaryArgs = @(
    "-u", "-m", "benchmark.same_protocol_full_run_baselines",
    "--datasets", "douban,twitter,memetracker",
    "--seeds", "42,43,44",
    "--models", "FOREST,CasFT",
    "--forest_data_root", "G:\CISCN\dataset\forest-data",
    "--forest_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST",
    "--casft_repo", "G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT",
    "--out", "benchmark\propagation_sota_primary_stable_20260810.json",
    "--config_id", "propagation-sota-primary-stable-20260810",
    "--device", "cuda",
    "--timeout", "1200",
    "--forest_epochs", "200",
    "--forest_batch_size", "16",
    "--forest_d_model", "64",
    "--forest_max_train_batches", "0",
    "--forest_max_eval_batches", "0",
    "--forest_rl_epochs", "0",
    "--forest_rl_max_batches", "0",
    "--forest_rl_rollout_len", "0",
    "--casft_max_events", "0",
    "--casft_max_epoch", "200",
    "--casft_interval_num", "12",
    "--casft_timesteps", "1000"
)
$Results += Run-Step -Name "primary_forest_casft_stable" -Log (Join-Path $LogDir "propagation_sota_primary_stable_20260810.log") -StepArgs $PrimaryArgs
Write-Status -Status "running" -Results $Results

$FrontierArgs = @(
    "-u", "-m", "benchmark.run_benchmark",
    "--datasets", "douban", "twitter", "memetracker",
    "--models", "dyglib", "tgn",
    "--forest_dir", "G:\CISCN\dataset\forest-data",
    "--dyglib_dir", "G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib",
    "--tgn_dir", "G:\CISCN\CogGuard\subsystems\kt2_repos\tgn",
    "--frontier_export_dir", "benchmark\propagation_sota_frontier_stable_exports_20260810",
    "--frontier_max_cascades", "0",
    "--frontier_epochs", "200",
    "--frontier_num_runs", "5",
    "--frontier_batch_size", "64",
    "--frontier_timeout", "86400",
    "--frontier_gpu", "0",
    "--run_external_frontier",
    "--device", "cuda",
    "--output", "benchmark\propagation_sota_frontier_temporal_stable_20260810.json"
)
$Results += Run-Step -Name "frontier_temporal_stable" -Log (Join-Path $LogDir "propagation_sota_frontier_temporal_stable_20260810.log") -StepArgs $FrontierArgs
Write-Status -Status "running" -Results $Results

$ReportArgs = @(
    "-u", "benchmark\summarize_propagation_sota_stable_20260810.py",
    "--primary", "benchmark\propagation_sota_primary_stable_20260810.json",
    "--sequence", "benchmark\propagation_sota_sequence_vs_minds_stable_20260810.json",
    "--frontier", "benchmark\propagation_sota_frontier_temporal_stable_20260810.json",
    "--strict-primary", "benchmark\propagation_sota_primary_full_20260810.json",
    "--out-md", "G:\CISCN\CogGuard\.worktrees\refactor-system\system\doc\research\propagation_paper_deep_reads\propagation_sota_stable_matrix_report_20260810.md",
    "--out-json", "benchmark\propagation_sota_stable_matrix_summary_20260810.json"
)
$Results += Run-Step -Name "stable_matrix_report" -Log (Join-Path $LogDir "propagation_sota_stable_matrix_report_20260810.log") -StepArgs $ReportArgs

$FinalStatus = if (($Results | Where-Object { $_.exit_code -ne 0 }).Count -eq 0) { "finished" } else { "finished_with_step_errors" }
Write-Status -Status $FinalStatus -Results $Results
